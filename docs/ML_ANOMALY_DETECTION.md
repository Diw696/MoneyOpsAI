# MoneyOps AI — Machine Learning Anomaly Detection

MoneyOps AI utilizes an unsupervised **Isolation Forest** pipeline from `scikit-learn` to detect statistical deviations across transaction lifecycles without requiring pre-labeled training data.

---

## 1. Feature Engineering

The detector extracts and normalizes 8 financial and operational features:

| Feature Name | Description | Normalization / Formula |
| :--- | :--- | :--- |
| `amount_norm` | Normalized transaction amount | $\frac{\text{amount}}{10000.0}$ |
| `retry_count` | Number of authorization attempts | Integer count ($0 \dots 15$) |
| `merchant_refund_deviation`| Deviation multiple from merchant 30-day baseline | $\frac{\text{current\_rate} - \text{baseline\_rate}}{\text{baseline\_rate}}$ |
| `gateway_failure_rate` | Real-time error rate for routed gateway | Float ($0.0 \dots 1.0$) |
| `settlement_delay_norm` | Settlement delay past merchant SLA in days | $\frac{\text{delay\_hours}}{24.0}$ |
| `velocity_per_min` | Card / IP retry velocity | Attempts per minute |
| `has_failure_code` | Boolean failure flag | $1.0$ if status is `failed` or error code present, else $0.0$ |
| `webhook_timeout_flag` | Webhook timeout delivery indicator | $1.0$ if delivery timed out (e.g. 504), else $0.0$ |

---

## 2. Model Architecture & Calibration

1. **Algorithm:** `IsolationForest(n_estimators=100, contamination=0.05, random_state=42)`
2. **Decision Function:** Outputs raw anomaly score $s \in [-0.3, +0.2]$, where negative values indicate severe tree isolation (anomalies).
3. **Linear Calibration:**
   $$\text{Score}_{\text{calibrated}} = \text{clip}\left(1.0 - \frac{s + 0.22}{0.42},\ 0.05,\ 0.99\right)$$
4. **Threshold:** Flagged as anomaly when $\text{Score}_{\text{calibrated}} \ge 0.65$.

---

## 3. Signal Attribution & Explainability

Along with the numeric score, the detector extracts human-readable contributing signals:
- *"Abnormal retry velocity: 14 attempts in short window"*
- *"Significant merchant baseline deviation (+3.8x normal)"*
- *"Elevated gateway failure rate (42% error spike)"*
- *"Webhook delivery acknowledgement timeout detected"*
