import numpy as np
from typing import Dict, Any, List, Tuple
from sklearn.ensemble import IsolationForest
from app.models.schemas import AnomalySignal
from app.core.config import settings

class FinancialAnomalyDetector:
    """
    Unsupervised Anomaly Detection using scikit-learn Isolation Forest.
    Evaluates engineered financial transaction and merchant-context features
    to produce mathematically derived anomaly scores and granular signal contributors.
    """

    FEATURE_NAMES = [
        "amount_norm",
        "retry_count",
        "merchant_refund_deviation",
        "gateway_failure_rate",
        "settlement_delay_norm",
        "velocity_per_min",
        "has_failure_code",
        "webhook_timeout_flag"
    ]

    def __init__(self):
        self.model = IsolationForest(
            n_estimators=100,
            contamination=settings.ISOLATION_FOREST_CONTAMINATION,
            random_state=42
        )
        self.is_fitted = False
        self._bootstrap_model()

    def _bootstrap_model(self):
        """Pre-trains Isolation Forest on a synthetic baseline distribution of normal transactions."""
        np.random.seed(42)
        n_samples = 3000

        # Normal distributions
        amounts = np.random.exponential(scale=1500, size=n_samples) / 10000.0
        retries = np.random.poisson(lam=0.2, size=n_samples)
        refund_dev = np.random.normal(loc=0.0, scale=0.5, size=n_samples)
        gw_fail = np.random.beta(a=1, b=30, size=n_samples)
        set_delay = np.random.exponential(scale=2, size=n_samples) / 24.0
        velocity = np.random.poisson(lam=1.0, size=n_samples)
        has_fail = np.random.binomial(n=1, p=0.05, size=n_samples)
        wh_timeout = np.random.binomial(n=1, p=0.01, size=n_samples)

        X_normal = np.column_stack([
            amounts, retries, refund_dev, gw_fail, set_delay, velocity, has_fail, wh_timeout
        ])

        # Inject 3% baseline anomalies for boundary fitting
        n_anom = int(n_samples * 0.03)
        X_anom = np.column_stack([
            np.random.uniform(5.0, 15.0, size=n_anom),       # high amount
            np.random.randint(6, 15, size=n_anom),          # retry spike
            np.random.uniform(3.0, 8.0, size=n_anom),       # severe refund deviation
            np.random.uniform(0.6, 0.95, size=n_anom),      # high gateway failure
            np.random.uniform(3.0, 10.0, size=n_anom),      # severe delay
            np.random.randint(10, 25, size=n_anom),         # high velocity
            np.ones(n_anom),                                # failed
            np.ones(n_anom)                                 # timed out
        ])

        X = np.vstack([X_normal, X_anom])
        self.model.fit(X)
        self.is_fitted = True

    def extract_features(self, payload: Dict[str, Any]) -> Tuple[np.ndarray, Dict[str, float]]:
        """Extracts and normalizes features from a payment or incident payload."""
        amount = float(payload.get("amount", 1000.0)) / 10000.0
        retries = float(payload.get("retry_count", 0))
        refund_dev = float(payload.get("refund_deviation", 0.0))
        gw_fail = float(payload.get("gateway_failure_rate", 0.02))
        set_delay = float(payload.get("settlement_delay_hrs", 0.0)) / 24.0
        velocity = float(payload.get("velocity", 1.0))
        has_fail = 1.0 if payload.get("failure_code") or payload.get("status") == "failed" else 0.0
        wh_timeout = 1.0 if payload.get("webhook_status") in ["timed_out", "failed"] else 0.0

        raw_dict = {
            "amount_norm": round(amount, 3),
            "retry_count": retries,
            "merchant_refund_deviation": round(refund_dev, 3),
            "gateway_failure_rate": round(gw_fail, 3),
            "settlement_delay_norm": round(set_delay, 3),
            "velocity_per_min": velocity,
            "has_failure_code": has_fail,
            "webhook_timeout_flag": wh_timeout
        }

        feature_vector = np.array([[
            amount, retries, refund_dev, gw_fail, set_delay, velocity, has_fail, wh_timeout
        ]])

        return feature_vector, raw_dict

    def score_anomaly(self, entity_id: str, entity_type: str, payload: Dict[str, Any]) -> AnomalySignal:
        """Computes pure mathematical anomaly score from Isolation Forest decision function."""
        feat_vec, raw_dict = self.extract_features(payload)

        # Isolation forest decision_function: lower is more anomalous (typically -0.3 to +0.2)
        raw_score = self.model.decision_function(feat_vec)[0]
        
        # Linear min-max calibration to [0, 1] range where 1.0 is highest anomaly
        calibrated_score = float(np.clip(1.0 - (raw_score + 0.22) / 0.42, 0.05, 0.99))

        contributing = []
        if raw_dict["retry_count"] >= 3:
            contributing.append(f"Abnormal retry velocity: {int(raw_dict['retry_count'])} attempts in short window")
        if raw_dict["merchant_refund_deviation"] > 1.5:
            contributing.append(f"Significant merchant baseline deviation (+{raw_dict['merchant_refund_deviation']}x normal)")
        if raw_dict["gateway_failure_rate"] > 0.2:
            contributing.append(f"Elevated gateway failure rate ({int(raw_dict['gateway_failure_rate']*100)}% error spike)")
        if raw_dict["settlement_delay_norm"] > 2.0:
            contributing.append("Settlement delay exceeded SLA threshold (>48h backlog)")
        if raw_dict["webhook_timeout_flag"] == 1.0:
            contributing.append("Webhook delivery acknowledgement timeout detected")
        if raw_dict["has_failure_code"] == 1.0 and payload.get("failure_code"):
            contributing.append(f"Recurring failure code: {payload.get('failure_code')}")

        is_anom = calibrated_score >= settings.ANOMALY_THRESHOLD

        return AnomalySignal(
            entity_id=entity_id,
            entity_type=entity_type,
            anomaly_score=round(calibrated_score, 3),
            is_anomaly=is_anom,
            contributing_signals=contributing,
            raw_features=raw_dict
        )

anomaly_detector = FinancialAnomalyDetector()
