import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import numpy as np
from sklearn.ensemble import IsolationForest
from app.core.config import settings
from app.engine.database import get_db_connection
from app.engine.feature_engine import FeatureEngine

class AnomalyDetector:
    """
    Unsupervised ML Anomaly Detection Engine using Scikit-Learn IsolationForest.
    Operates on explainable business features extracted dynamically from PostgreSQL.
    Zero hardcoded gateway or merchant rules.
    """

    def __init__(self, contamination: float = 0.05, threshold: float = 0.65, random_state: int = 42):
        self.contamination = contamination
        self.threshold = threshold
        self.random_state = random_state
        self.feature_names = [
            "failure_rate",
            "failure_rate_ratio",
            "top_failure_code_share",
            "failed_payments_volume"
        ]

    def _prepare_feature_matrix(self, features_list: List[Dict[str, Any]]) -> np.ndarray:
        """Constructs and normalizes the feature matrix X for Isolation Forest."""
        X_rows = []
        for f in features_list:
            row = [
                float(f.get("failure_rate", 0.0)),
                float(f.get("failure_rate_ratio", 1.0)),
                float(f.get("top_failure_code_share", 0.0)),
                float(np.log1p(f.get("failed_payments", 0)))
            ]
            X_rows.append(row)
        return np.array(X_rows, dtype=np.float64)

    def run_detection(self) -> Dict[str, Any]:
        """
        Executes end-to-end anomaly detection on PostgreSQL data:
        1. Extracts gateway and merchant feature vectors.
        2. Fits Isolation Forest on the population.
        3. Normalizes decision function into [0.0, 1.0] anomaly scores.
        4. Identifies entities exceeding threshold.
        5. Computes business evidence and persists incidents to PostgreSQL.
        """
        gateway_features = FeatureEngine.extract_gateway_features()
        merchant_features = FeatureEngine.extract_merchant_features()

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as cnt FROM payments;")
        total_payments_analyzed = c.fetchone()["cnt"]
        c.close()
        conn.close()

        if not gateway_features:
            return {
                "status": "success",
                "records_analyzed": 0,
                "anomalies_detected": 0,
                "incidents_created": [],
                "gateway_scores": []
            }

        # 1. Build Feature Matrix
        X = self._prepare_feature_matrix(gateway_features)

        # 2. Fit Isolation Forest Model
        # When population is small (e.g. 5 gateways), IsolationForest is trained with adjusted contamination
        clf = IsolationForest(
            n_estimators=100,
            contamination=self.contamination,
            random_state=self.random_state
        )
        clf.fit(X)

        # 3. Compute Normalized Anomaly Score
        # decision_function gives negative values for outliers, positive for inliers
        raw_scores = clf.decision_function(X)
        # Normalize: raw_scores typically range in [-0.5, 0.5].
        # We map more negative -> higher anomaly score [0.0, 1.0]
        min_s = float(np.min(raw_scores))
        max_s = float(np.max(raw_scores))
        
        normalized_scores = []
        for s in raw_scores:
            if max_s > min_s:
                norm_score = 1.0 - ((float(s) - min_s) / (max_s - min_s))
            else:
                norm_score = 0.0
            normalized_scores.append(round(float(norm_score), 4))

        # 4. Evaluate Threshold & Create Incidents
        incidents_created = []
        gateway_evaluations = []

        conn = get_db_connection()
        cursor = conn.cursor()
        now_str = datetime.utcnow().isoformat()

        for idx, g in enumerate(gateway_features):
            score = float(normalized_scores[idx])
            gw_name = str(g["entity_id"])
            failure_rate = float(g["failure_rate"])
            ratio = float(g["failure_rate_ratio"])

            gateway_evaluations.append({
                "gateway": gw_name,
                "anomaly_score": score,
                "failure_rate": failure_rate,
                "peer_failure_rate": float(g["peer_failure_rate"]),
                "failed_payments": int(g["failed_payments"]),
                "potential_exposure": float(g["potential_exposure"]),
                "is_anomalous": bool(score >= self.threshold and failure_rate >= 0.08)
            })

            # Check if entity is anomalous
            # Conditions: score >= threshold AND failure_rate >= 8% (to ensure statistical business materiality)
            if score >= self.threshold and failure_rate >= 0.08:
                severity = "medium"
                if g["potential_exposure"] >= 100000.0 or (failure_rate >= 0.15 and g["affected_merchants"] >= 3):
                    severity = "critical"
                elif g["potential_exposure"] >= 50000.0 or failure_rate >= 0.10:
                    severity = "high"

                incident_type = "gateway_failure_spike"
                title = f"{gw_name} Payment Failure Spike ({round(failure_rate * 100, 1)}%)"
                primary_signal = f"Gateway failure rate ({round(failure_rate * 100, 2)}%) is {ratio}x peer gateway baseline ({round(g['peer_failure_rate'] * 100, 2)}%). Top error: {g['top_failure_code']} ({g['top_failure_code_count']} occurrences)."
                
                evidence = {
                    "entity_type": "gateway",
                    "entity_id": gw_name,
                    "failure_rate_pct": round(failure_rate * 100, 2),
                    "peer_failure_rate_pct": round(float(g["peer_failure_rate"]) * 100, 2),
                    "failure_rate_ratio": ratio,
                    "top_failure_code": str(g["top_failure_code"]),
                    "top_failure_code_count": int(g["top_failure_code_count"]),
                    "top_failure_code_share": float(g["top_failure_code_share"]),
                    "failed_payments_count": int(g["failed_payments"]),
                    "total_payments_count": int(g["total_payments"]),
                    "affected_merchants_count": int(g["affected_merchants"]),
                    "affected_orders_count": int(g["affected_orders"]),
                    "potential_exposure_inr": float(g["potential_exposure"]),
                    "ml_model": "IsolationForest",
                    "ml_anomaly_score": score,
                    "ml_contamination": float(self.contamination)
                }

                description = f"Automated ML Anomaly Detection identified elevated payment rejection velocity on banking gateway node {gw_name}. {g['failed_payments']} payments failed out of {g['total_payments']} total attempts, creating ₹{g['potential_exposure']:,.2f} in potential unresolved merchant exposure."

                # 5. Idempotent Deduplication (Check if open incident exists for this entity)
                cursor.execute("""
                    SELECT incident_id, status FROM incidents 
                    WHERE target_entity_type = 'gateway' AND target_entity_id = %s AND status = 'open';
                """, (gw_name,))
                existing_inc = cursor.fetchone()

                if existing_inc:
                    # Update existing open incident with latest metrics
                    inc_id = existing_inc["incident_id"]
                    cursor.execute("""
                        UPDATE incidents SET
                            affected_merchants = %s,
                            affected_payments = %s,
                            potential_exposure = %s,
                            anomaly_score = %s,
                            primary_signal = %s,
                            evidence_json = %s,
                            description = %s,
                            detected_at = %s
                        WHERE incident_id = %s;
                    """, (
                        int(g["affected_merchants"]), int(g["failed_payments"]),
                        float(g["potential_exposure"]), float(score), str(primary_signal),
                        json.dumps(evidence), str(description), now_str, inc_id
                    ))
                else:
                    # Generate clean Sequential ID
                    cursor.execute("SELECT COUNT(*) as cnt FROM incidents;")
                    inc_num = cursor.fetchone()["cnt"] + 1
                    inc_id = f"INC-{inc_num:04d}"

                    cursor.execute("""
                        INSERT INTO incidents (
                            incident_id, title, type, target_entity_type, target_entity_id,
                            severity, status, affected_merchants, affected_payments,
                            potential_exposure, anomaly_score, primary_signal,
                            evidence_json, source, detected_at, description
                        ) VALUES (%s, %s, %s, 'gateway', %s, %s, 'open', %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """, (
                        inc_id, title, incident_type, gw_name, severity,
                        int(g["affected_merchants"]), int(g["failed_payments"]),
                        float(g["potential_exposure"]), float(score), str(primary_signal),
                        json.dumps(evidence), str(g["source"]), now_str, str(description)
                    ))

                incidents_created.append({
                    "incident_id": inc_id,
                    "title": title,
                    "target_entity": gw_name,
                    "anomaly_score": score,
                    "severity": severity,
                    "failure_rate": f"{round(failure_rate * 100, 2)}%",
                    "peer_failure_rate": f"{round(float(g['peer_failure_rate']) * 100, 2)}%",
                    "failed_payments": int(g["failed_payments"]),
                    "potential_exposure": float(g["potential_exposure"]),
                    "primary_signal": primary_signal,
                    "source": str(g["source"])
                })

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "status": "success",
            "records_analyzed": total_payments_analyzed,
            "gateways_evaluated": len(gateway_features),
            "anomalies_detected": len(incidents_created),
            "incidents": incidents_created,
            "gateway_evaluations": gateway_evaluations
        }

anomaly_detector = AnomalyDetector(
    contamination=settings.ISOLATION_FOREST_CONTAMINATION,
    threshold=settings.ANOMALY_THRESHOLD
)
