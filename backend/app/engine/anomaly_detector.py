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

    # Below this many payment attempts, a failure-rate percentage is not a reliable
    # signal: with e.g. 2 attempts, one failure already reads as 50-100%, which looks
    # identical to a genuine outage but is really just small-sample noise. 20 is the
    # point where a single additional failure moves the rate by at most ~5 percentage
    # points, keeping the peer-ratio comparison statistically meaningful.
    MIN_SAMPLE_SIZE = 20

    # Business-materiality floor on the raw failure rate (existing check).
    MIN_FAILURE_RATE = 0.08

    @staticmethod
    def wilson_lower_bound(failures: int, total: int, z: float = 1.645) -> float:
        """
        One-sided 95% Wilson score lower bound on a failure rate (z=1.645, not the
        two-sided 1.96 — we only ever ask "how bad could this plausibly NOT be",
        a single tail, so the two-sided value would be needlessly conservative).
        A raw rate like 3/20 = 15% can still be a wide, unreliable estimate right
        at the sample-size floor; this lower bound is what actually gets compared
        against MIN_FAILURE_RATE, not the raw percentage. Returns 0.0 for an empty
        sample (never a signal).
        """
        if total <= 0:
            return 0.0
        phat = failures / total
        denom = 1.0 + (z ** 2) / total
        center = phat + (z ** 2) / (2 * total)
        margin = z * ((phat * (1 - phat) / total + (z ** 2) / (4 * total ** 2)) ** 0.5)
        return max(0.0, (center - margin) / denom)

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

    def evaluate_gateways(self) -> List[Dict[str, Any]]:
        """
        Read-only: extracts gateway features, fits IsolationForest, and returns a
        per-gateway evaluation (score, sample-size sufficiency, Wilson lower bound,
        is_anomalous) — with NO database writes and no incidents created or updated.
        Exists so a sub-floor / statistically-insignificant gateway is never just
        silently dropped: this is what the "below confidence threshold" list on the
        Overview page and `evaluate_gateways()`-based tests read from, independent
        of whether anyone has clicked "Run Anomaly Scan" (which does write incidents).
        """
        gateway_features = FeatureEngine.extract_gateway_features()
        if not gateway_features:
            return []

        # Fit and score only over gateways that clear the sample-size floor. A
        # tiny-sample gateway isn't just unreliable to flag itself (handled below);
        # left in the fitted population it also acts as an extreme outlier that
        # skews everyone else's population-relative normalized score, which would
        # let it suppress a real spike on a legitimate gateway without ever itself
        # being flagged. Excluding it from fitting, not just from the final
        # flagging decision, is what actually neutralizes that.
        scored_features = [g for g in gateway_features if int(g["total_payments"]) >= self.MIN_SAMPLE_SIZE]
        unscored_features = [g for g in gateway_features if int(g["total_payments"]) < self.MIN_SAMPLE_SIZE]

        normalized_by_entity: Dict[str, float] = {}
        if scored_features:
            X = self._prepare_feature_matrix(scored_features)

            # Fit Isolation Forest Model. When population is small (e.g. 5 gateways),
            # IsolationForest is trained with adjusted contamination
            clf = IsolationForest(
                n_estimators=100,
                contamination=self.contamination,
                random_state=self.random_state
            )
            clf.fit(X)

            # Compute Normalized Anomaly Score.
            # decision_function gives negative values for outliers, positive for inliers
            raw_scores = clf.decision_function(X)
            # Normalize: raw_scores typically range in [-0.5, 0.5].
            # We map more negative -> higher anomaly score [0.0, 1.0]
            min_s = float(np.min(raw_scores))
            max_s = float(np.max(raw_scores))

            for idx, s in enumerate(raw_scores):
                if max_s > min_s:
                    norm_score = 1.0 - ((float(s) - min_s) / (max_s - min_s))
                else:
                    norm_score = 0.0
                normalized_by_entity[str(scored_features[idx]["entity_id"])] = round(float(norm_score), 4)

        # Gateways below the sample-size floor never get a meaningful comparative
        # score — report 0.0 rather than implying they were fairly evaluated.
        for g in unscored_features:
            normalized_by_entity[str(g["entity_id"])] = 0.0

        gateway_evaluations = []
        for g in gateway_features:
            gw_name = str(g["entity_id"])
            score = float(normalized_by_entity[gw_name])
            failure_rate = float(g["failure_rate"])

            total_payments = int(g["total_payments"])
            failed_payments = int(g["failed_payments"])
            sample_size_sufficient = total_payments >= self.MIN_SAMPLE_SIZE
            wilson_lb = self.wilson_lower_bound(failed_payments, total_payments)
            statistically_significant = wilson_lb >= self.MIN_FAILURE_RATE
            is_anomalous = bool(
                score >= self.threshold
                and sample_size_sufficient
                and statistically_significant
            )

            gateway_evaluations.append({
                "gateway": gw_name,
                "anomaly_score": score,
                "failure_rate": failure_rate,
                "peer_failure_rate": float(g["peer_failure_rate"]),
                "failed_payments": failed_payments,
                "total_payments": total_payments,
                "source": str(g["source"]),
                "sample_size_sufficient": sample_size_sufficient,
                "min_sample_size": self.MIN_SAMPLE_SIZE,
                "wilson_lower_bound_pct": round(wilson_lb * 100, 2),
                "statistically_significant": statistically_significant,
                "is_anomalous": is_anomalous,
                "below_confidence_threshold": bool(not sample_size_sufficient or not statistically_significant),
                "potential_exposure": float(g["potential_exposure"])
            })

        return gateway_evaluations

    # Minimum count of distinct payments with a duplicate refund before it's worth
    # flagging — 1 duplicate in a huge merchant population is noise, not an incident.
    MIN_DUPLICATE_REFUND_PAYMENTS = 2
    # Minimum refund count before a refund-rate percentage is a reliable signal at
    # all (mirrors MIN_SAMPLE_SIZE's reasoning, applied to the refund population).
    MIN_REFUND_SAMPLE = 5

    def evaluate_merchants(self) -> List[Dict[str, Any]]:
        """
        Read-only, no database writes: evaluates every merchant for three distinct
        merchant-level incident signatures — refund-volume spike (vs that merchant's
        own historical baseline), duplicate-refund / retry-race activity, and webhook
        delivery degradation (vs peer merchants) — each backed by real PostgreSQL
        aggregates via FeatureEngine, not by re-reading the incident's own title.
        """
        from app.engine.feature_engine import FeatureEngine
        merchant_features = FeatureEngine.extract_merchant_features()
        webhook_features = {f["entity_id"]: f for f in FeatureEngine.extract_webhook_features()}
        dup_features = {f["merchant_id"]: f for f in FeatureEngine.extract_duplicate_refund_features()}

        evaluations = []
        for mf in merchant_features:
            merchant_id = mf["entity_id"]
            total_payments = int(mf["total_payments"])
            total_refunds = int(mf["total_refunds"])

            # --- Refund spike: actual refund rate vs merchant's own baseline ---
            sample_ok = total_payments >= self.MIN_SAMPLE_SIZE and total_refunds >= self.MIN_REFUND_SAMPLE
            wilson_lb = self.wilson_lower_bound(total_refunds, total_payments)
            baseline = float(mf["baseline_refund_rate"])
            ratio = float(mf["refund_rate_ratio"])
            # A flat percentage floor (e.g. the gateway detector's 8%) doesn't fit
            # here: merchant refund baselines are typically 0.2%-3.5%, so the floor
            # must scale with each merchant's own baseline rather than a shared
            # absolute cutoff — a merchant with a 0.5% baseline spiking to 3% is
            # just as real an incident as one with a 3% baseline spiking to 18%.
            # A purely relative floor (baseline * N) breaks down for the lowest-
            # baseline merchants though: once enough payment volume accumulates
            # across many Incident Lab batches, ordinary baseline noise alone can
            # drift a 0.2%-0.4% baseline merchant's observed rate past a tiny
            # relative bar (e.g. 2x of 0.4% is 0.8%) with no injected scenario at
            # all — which is exactly what let one low-baseline merchant dominate
            # detection results regardless of which scenario a given batch
            # actually injected. The added flat 2.5% absolute floor is well below
            # every genuinely-injected refund-spike severity this project uses,
            # but well above what baseline noise alone produces even after many
            # batches, so it filters noise without weakening real detection.
            refund_spike = bool(
                sample_ok
                and ratio >= 2.5
                and wilson_lb >= max(baseline * 3.0, 0.025)
            )

            # --- Duplicate refund: distinct payments refunded more than once ---
            dup = dup_features.get(merchant_id, {})
            dup_count = int(dup.get("duplicate_refund_payments") or 0)
            duplicate_refund = bool(dup_count >= self.MIN_DUPLICATE_REFUND_PAYMENTS)

            # --- Webhook delivery failure: vs peer merchant baseline ---
            wf = webhook_features.get(merchant_id)
            webhook_failure = False
            wh_wilson_lb = 0.0
            wh_total = wh_failed = 0
            wh_peer_rate = 0.0
            if wf:
                wh_total = int(wf["total_webhooks"])
                wh_failed = int(wf["failed_webhooks"])
                wh_peer_rate = float(wf["peer_failure_rate"])
                wh_sample_ok = wh_total >= self.MIN_SAMPLE_SIZE
                wh_wilson_lb = self.wilson_lower_bound(wh_failed, wh_total)
                webhook_failure = bool(
                    wh_sample_ok
                    and wh_wilson_lb >= self.MIN_FAILURE_RATE
                    and (wh_peer_rate <= 0 or (wh_failed / wh_total) >= wh_peer_rate * 2.5)
                )

            evaluations.append({
                "merchant_id": merchant_id,
                "merchant_name": mf["merchant_name"],
                "total_payments": total_payments,
                "total_refunds": total_refunds,
                "actual_refund_rate": mf["actual_refund_rate"],
                "baseline_refund_rate": baseline,
                "refund_rate_ratio": ratio,
                "refund_wilson_lower_bound_pct": round(wilson_lb * 100, 2),
                "refund_spike": refund_spike,
                "duplicate_refund_payments": dup_count,
                "duplicate_refund": duplicate_refund,
                "webhook_total": wh_total,
                "webhook_failed": wh_failed,
                "webhook_peer_failure_rate_pct": round(wh_peer_rate * 100, 2),
                "webhook_wilson_lower_bound_pct": round(wh_wilson_lb * 100, 2),
                "webhook_failure": webhook_failure,
                # Each scenario has its own financial-exposure definition — a
                # webhook problem's exposure has nothing to do with refund
                # totals, and a duplicate-refund incident's exposure is the
                # value tied up in the duplicated payments specifically, not
                # every ordinary refund this merchant has ever issued.
                "refund_exposure": mf["potential_exposure"],
                "duplicate_refund_exposure": round(float(dup.get("duplicate_refund_exposure") or 0), 2),
                "webhook_exposure": round(float(wf["webhook_exposure"]), 2) if wf else 0.0,
                "source": mf["source"]
            })
        return evaluations

    def run_detection(self) -> Dict[str, Any]:
        """
        Executes end-to-end anomaly detection on PostgreSQL data:
        1. Extracts gateway feature vectors and evaluates them (see evaluate_gateways).
        2. Computes business evidence and persists incidents to PostgreSQL for
           whichever gateways are anomalous.
        """
        gateway_evaluations = self.evaluate_gateways()
        gateway_features = {str(g["entity_id"]): g for g in FeatureEngine.extract_gateway_features()}

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as cnt FROM payments;")
        total_payments_analyzed = c.fetchone()["cnt"]
        c.close()
        conn.close()

        if not gateway_evaluations:
            return {
                "status": "success",
                "records_analyzed": 0,
                "anomalies_detected": 0,
                "incidents_created": [],
                "gateway_scores": []
            }

        incidents_created = []

        conn = get_db_connection()
        cursor = conn.cursor()
        now_str = datetime.utcnow().isoformat()

        for ge in gateway_evaluations:
            gw_name = ge["gateway"]
            g = gateway_features[gw_name]
            score = ge["anomaly_score"]
            failure_rate = ge["failure_rate"]
            ratio = float(g["failure_rate_ratio"])
            wilson_lb = ge["wilson_lower_bound_pct"] / 100.0
            is_anomalous = ge["is_anomalous"]

            # Reuses the exact `is_anomalous` computed by evaluate_gateways() —
            # never a separately-recomputed condition that could drift out of sync
            # with what the API reports as anomalous.
            if is_anomalous:
                severity = "medium"
                if g["potential_exposure"] >= 100000.0 or (failure_rate >= 0.15 and g["affected_merchants"] >= 3):
                    severity = "critical"
                elif g["potential_exposure"] >= 50000.0 or failure_rate >= 0.10:
                    severity = "high"

                incident_type = "gateway_failure_spike"

                # The title reflects which failure code actually dominates —
                # real, evidence-derived variety (a timeout concentration and
                # an auth-failure concentration are genuinely different
                # operational stories), not a random label. Concentration
                # requires a real majority share, not just being the top code
                # among many roughly-even ones.
                top_code = str(g["top_failure_code"])
                top_code_share_pct = float(g["top_failure_code_share"]) * 100
                if top_code_share_pct >= 50 and top_code == "GATEWAY_TIMEOUT":
                    scenario_label = "Timeout Concentration"
                elif top_code_share_pct >= 50 and top_code == "AUTH_FAILED":
                    scenario_label = "Authentication Failure Concentration"
                elif top_code_share_pct >= 50 and top_code == "BAD_REQUEST_ERROR":
                    scenario_label = "Request Validation Failure Concentration"
                else:
                    scenario_label = "Payment Failure Spike"
                title = f"{gw_name} {scenario_label} ({round(failure_rate * 100, 1)}%)"
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
                    "ml_contamination": float(self.contamination),
                    "wilson_lower_bound_pct": round(wilson_lb * 100, 2),
                    "min_sample_size": self.MIN_SAMPLE_SIZE
                }

                description = f"Automated ML Anomaly Detection identified elevated payment rejection velocity on banking gateway node {gw_name}. {g['failed_payments']} payments failed out of {g['total_payments']} total attempts, creating ₹{g['potential_exposure']:,.2f} in potential unresolved merchant exposure."

                # 5. Idempotent Deduplication (Check if open incident of this exact
                # type exists for this entity — scoped by type as well as entity so
                # a resolved-then-recurring issue opens a fresh incident rather than
                # silently reusing an old, already-closed one).
                cursor.execute("""
                    SELECT incident_id, status FROM incidents
                    WHERE target_entity_type = 'gateway' AND target_entity_id = %s AND type = %s AND status = 'open';
                """, (gw_name, incident_type))
                existing_inc = cursor.fetchone()

                if existing_inc:
                    # Update existing open incident with latest metrics
                    inc_id = existing_inc["incident_id"]
                    cursor.execute("""
                        UPDATE incidents SET
                            title = %s,
                            severity = %s,
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
                        str(title), str(severity),
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

        # 6. Merchant-level scenario detection (refund spike, duplicate refund,
        # webhook delivery failure) — a genuinely different detector family from
        # the gateway ML scorer above, so these incident types actually get
        # created rather than only existing as injected-but-never-flagged data.
        merchant_evaluations = self.evaluate_merchants()
        for me in merchant_evaluations:
            merchant_id = me["merchant_id"]
            merchant_name = me["merchant_name"]

            def _upsert_merchant_incident(incident_type, title, primary_signal, evidence, description, severity, affected_payments, exposure):
                cursor.execute("""
                    SELECT incident_id, status FROM incidents
                    WHERE target_entity_type = 'merchant' AND target_entity_id = %s AND type = %s AND status = 'open';
                """, (merchant_id, incident_type))
                existing = cursor.fetchone()
                if existing:
                    inc_id = existing["incident_id"]
                    cursor.execute("""
                        UPDATE incidents SET
                            title = %s, severity = %s, affected_payments = %s, potential_exposure = %s,
                            evidence_json = %s, description = %s, primary_signal = %s, detected_at = %s
                        WHERE incident_id = %s;
                    """, (title, severity, affected_payments, float(exposure), json.dumps(evidence), description, primary_signal, now_str, inc_id))
                else:
                    cursor.execute("SELECT COUNT(*) as cnt FROM incidents;")
                    inc_num = cursor.fetchone()["cnt"] + 1
                    inc_id = f"INC-{inc_num:04d}"
                    cursor.execute("""
                        INSERT INTO incidents (
                            incident_id, title, type, target_entity_type, target_entity_id,
                            severity, status, affected_merchants, affected_payments,
                            potential_exposure, anomaly_score, primary_signal,
                            evidence_json, source, detected_at, description
                        ) VALUES (%s, %s, %s, 'merchant', %s, %s, 'open', 1, %s, %s, %s, %s, %s, %s, %s, %s);
                    """, (
                        inc_id, title, incident_type, merchant_id, severity, affected_payments,
                        float(exposure), 0.9, primary_signal,
                        json.dumps(evidence), str(me["source"]), now_str, description
                    ))
                incidents_created.append({
                    "incident_id": inc_id,
                    "title": title,
                    "target_entity": merchant_id,
                    "severity": severity,
                    "primary_signal": primary_signal,
                    "source": str(me["source"])
                })

            if me["refund_spike"]:
                pct = round(me["actual_refund_rate"] * 100, 2)
                baseline_pct = round(me["baseline_refund_rate"] * 100, 2)
                severity = "critical" if me["refund_rate_ratio"] >= 6 else ("high" if me["refund_rate_ratio"] >= 4 else "medium")
                primary_signal = f"Refund rate ({pct}%) is {me['refund_rate_ratio']}x this merchant's own baseline ({baseline_pct}%), based on {me['total_refunds']} refunds across {me['total_payments']} payments."
                evidence = {
                    "entity_type": "merchant",
                    "entity_id": merchant_id,
                    "actual_refund_rate_pct": pct,
                    "baseline_refund_rate_pct": baseline_pct,
                    "refund_rate_ratio": me["refund_rate_ratio"],
                    "total_refunds": me["total_refunds"],
                    "total_payments": me["total_payments"],
                    "wilson_lower_bound_pct": me["refund_wilson_lower_bound_pct"],
                    "min_sample_size": self.MIN_SAMPLE_SIZE,
                    "potential_exposure_inr": float(me["refund_exposure"])
                }
                description = f"Merchant {merchant_name} ({merchant_id}) is refunding at {pct}% of payments, {me['refund_rate_ratio']}x its own historical baseline of {baseline_pct}%, concentrated across {me['total_refunds']} refund records."
                _upsert_merchant_incident("merchant_refund_spike", f"{merchant_name} Refund Rate Anomaly", primary_signal, evidence, description, severity, me["total_refunds"], me["refund_exposure"])

            if me["duplicate_refund"]:
                severity = "high" if me["duplicate_refund_payments"] >= 5 else "medium"
                primary_signal = f"{me['duplicate_refund_payments']} distinct payments received more than one refund attempt — a duplicate-refund / retry-race signature, not a volume spike."
                evidence = {
                    "entity_type": "merchant",
                    "entity_id": merchant_id,
                    "duplicate_refund_payments": me["duplicate_refund_payments"],
                    "total_refunds": me["total_refunds"],
                    "potential_exposure_inr": float(me["duplicate_refund_exposure"])
                }
                description = f"Merchant {merchant_name} ({merchant_id}) has {me['duplicate_refund_payments']} payments with duplicated refund attempts, consistent with a retry loop lacking idempotency protection."
                _upsert_merchant_incident("merchant_duplicate_refund", f"Duplicate Refund Activity — {merchant_name}", primary_signal, evidence, description, severity, me["duplicate_refund_payments"], me["duplicate_refund_exposure"])

            if me["webhook_failure"]:
                wh_rate_pct = round((me["webhook_failed"] / me["webhook_total"]) * 100, 2) if me["webhook_total"] else 0.0
                severity = "high" if wh_rate_pct >= 25 else "medium"
                primary_signal = f"Webhook delivery failure rate ({wh_rate_pct}%) is well above the peer merchant baseline ({me['webhook_peer_failure_rate_pct']}%), based on {me['webhook_total']} delivery attempts."
                evidence = {
                    "entity_type": "merchant",
                    "entity_id": merchant_id,
                    "webhook_failure_rate_pct": wh_rate_pct,
                    "peer_failure_rate_pct": me["webhook_peer_failure_rate_pct"],
                    "webhook_total": me["webhook_total"],
                    "webhook_failed": me["webhook_failed"],
                    "wilson_lower_bound_pct": me["webhook_wilson_lower_bound_pct"],
                    "min_sample_size": self.MIN_SAMPLE_SIZE,
                    "potential_exposure_inr": float(me["webhook_exposure"])
                }
                description = f"Merchant {merchant_name} ({merchant_id}) webhook notifications are failing at {wh_rate_pct}% ({me['webhook_failed']}/{me['webhook_total']}), versus a peer baseline of {me['webhook_peer_failure_rate_pct']}%."
                _upsert_merchant_incident("merchant_webhook_failure", f"Webhook Delivery Failure — {merchant_name}", primary_signal, evidence, description, severity, me["webhook_failed"], me["webhook_exposure"])

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "status": "success",
            "records_analyzed": total_payments_analyzed,
            "gateways_evaluated": len(gateway_features),
            "merchants_evaluated": len(merchant_evaluations),
            "anomalies_detected": len(incidents_created),
            "incidents": incidents_created,
            "gateway_evaluations": gateway_evaluations
        }

anomaly_detector = AnomalyDetector(
    contamination=settings.ISOLATION_FOREST_CONTAMINATION,
    threshold=settings.ANOMALY_THRESHOLD
)
