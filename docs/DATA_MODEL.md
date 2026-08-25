# MoneyOps AI — Relational Data Model Specification

The SQLite database (`backend/data/moneyops.db`) serves as the single source of truth for the entire platform.

---

## 1. Relational Schema & Table Definitions

### 1. `merchants`
Stores merchant metadata, category, and historical operational baselines.
- `merchant_id` (TEXT, PK): Unique merchant identifier (e.g. `merch_Nova_Store`).
- `name` (TEXT): Business trading name.
- `category` (TEXT): Category (`ecommerce`, `saas`, `travel`, `gaming`, etc.).
- `baseline_refund_rate` (REAL): Normal 30-day baseline refund frequency (e.g. `0.012` for 1.2%).
- `baseline_retry_count` (REAL): Expected average retry attempts per payment.
- `baseline_settlement_latency_hrs` (REAL): SLA settlement target in hours.
- `created_at` (TEXT): ISO 8601 creation timestamp.

### 2. `customers`
- `customer_id` (TEXT, PK): Unique customer identifier (e.g. `cust_0001`).
- `name` (TEXT): Customer full name.
- `email` (TEXT): Customer email address.
- `phone` (TEXT): Contact number.
- `created_at` (TEXT): Creation timestamp.

### 3. `orders`
- `order_id` (TEXT, PK): Unique order identifier.
- `merchant_id` (TEXT, FK → `merchants.merchant_id`).
- `customer_id` (TEXT, FK → `customers.customer_id`).
- `amount` (REAL): Order financial value in INR.
- `currency` (TEXT): Currency code (`INR`).
- `status` (TEXT): Order status (`created`, `paid`, `cancelled`).
- `created_at` (TEXT): Timestamp.

### 4. `payments`
- `payment_id` (TEXT, PK): Unique payment identifier (e.g. `pay_P19283`).
- `order_id` (TEXT, FK → `orders.order_id`).
- `merchant_id` (TEXT, FK → `merchants.merchant_id`).
- `customer_id` (TEXT, FK → `customers.customer_id`).
- `amount` (REAL): Transaction value in INR.
- `currency` (TEXT): Currency code.
- `status` (TEXT): `captured`, `failed`, `authorized`.
- `method` (TEXT): `card`, `netbanking`, `upi`.
- `gateway` (TEXT): Processing gateway (`Gateway_X`, `Gateway_HDFC`, `Gateway_ICICI`, `Gateway_Axis`).
- `created_at` (TEXT): Payment attempt timestamp.
- `captured_at` (TEXT, NULLABLE): Capture timestamp.
- `failure_code` (TEXT, NULLABLE): Gateway error code (e.g. `R-104`, `ERR_3DS_TIMEOUT`).
- `error_description` (TEXT, NULLABLE): Descriptive error message.
- `retry_count` (INTEGER): Authorization retry counter.

### 5. `refunds`
- `refund_id` (TEXT, PK): Unique refund identifier (e.g. `rfnd_R8821`).
- `payment_id` (TEXT, FK → `payments.payment_id`).
- `merchant_id` (TEXT, FK → `merchants.merchant_id`).
- `amount` (REAL): Refund value in INR.
- `status` (TEXT): `processed`, `failed`, `pending`.
- `speed` (TEXT): `instant` or `normal`.
- `created_at` (TEXT): Refund initiation timestamp.
- `processed_at` (TEXT, NULLABLE): Completion timestamp.
- `failure_reason` (TEXT, NULLABLE): Timeout or gateway drop explanation.

### 6. `settlements`
- `settlement_id` (TEXT, PK): Unique settlement batch identifier (e.g. `set_STUCK_991`).
- `merchant_id` (TEXT, FK → `merchants.merchant_id`).
- `payment_id` (TEXT, FK → `payments.payment_id`).
- `amount` (REAL): Settlement value in INR.
- `utr` (TEXT, NULLABLE): Bank Unique Transaction Reference.
- `status` (TEXT): `settled`, `pending`, `stuck`.
- `settled_at` (TEXT, NULLABLE): Bank settlement timestamp.
- `due_at` (TEXT): SLA cutoff timestamp.
- `delay_hours` (REAL): Delay elapsed past due SLA.

### 7. `disputes`
- `dispute_id` (TEXT, PK): Unique dispute identifier.
- `payment_id` (TEXT, FK → `payments.payment_id`).
- `merchant_id` (TEXT, FK → `merchants.merchant_id`).
- `phase` (TEXT): `chargeback`, `retrieval`.
- `status` (TEXT): `open`, `under_review`, `won`, `lost`.
- `reason` (TEXT): Dispute chargeback reason.
- `amount` (REAL): Disputed amount in INR.
- `created_at` (TEXT): Created timestamp.
- `deadline` (TEXT): Evidence submission deadline.

### 8. `webhook_events`
- `event_id` (TEXT, PK): Webhook event delivery identifier.
- `event_type` (TEXT): Webhook topic (`payment.captured`, `refund.processed`, `refund.failed`).
- `entity_id` (TEXT): Targeted payment/refund ID.
- `merchant_id` (TEXT, FK → `merchants.merchant_id`).
- `timestamp` (TEXT): Delivery attempt timestamp.
- `delivery_attempt` (INTEGER): Attempt count.
- `signature_valid` (INTEGER): `1` if HMAC-SHA256 valid, `0` otherwise.
- `delivery_status` (TEXT): `delivered`, `failed`, `timed_out`.
- `http_status` (INTEGER): HTTP status code (`200`, `504`, `500`).
- `response_time_ms` (INTEGER): Latency in milliseconds.

### 9. `canonical_events`
- `canonical_id` (TEXT, PK): Canonical ingestion log ID.
- `event_source` (TEXT): `synthetic`, `razorpay_webhook`, `simulator`.
- `event_type` (TEXT): Standard event topic.
- `entity_type` (TEXT): `payment`, `refund`, `settlement`.
- `entity_id` (TEXT): Entity ID.
- `merchant_id` (TEXT): Merchant ID.
- `amount` (REAL): Transaction value in INR.
- `status` (TEXT): Processing outcome.
- `payload_json` (TEXT): Raw normalized JSON payload.
- `ingested_at` (TEXT): Ingestion timestamp.
- `is_anomaly` (INTEGER): `1` if flagged by Isolation Forest, `0` otherwise.
- `anomaly_score` (REAL): Model anomaly score $[0, 1]$.

### 10. `incidents`
- `incident_id` (TEXT, PK): Financial incident ID (e.g. `INC-2841`).
- `title` (TEXT): Incident summary title.
- `type` (TEXT): Incident taxonomy category.
- `severity` (TEXT): `critical`, `high`, `medium`, `low`.
- `status` (TEXT): `open`, `investigating`, `resolved`, `closed`.
- `affected_merchants` (INTEGER): Count of affected merchants.
- `affected_transactions` (INTEGER): Count of affected payment/refund lifecycles.
- `potential_exposure` (REAL): Financial amount at risk in INR.
- `recoverable_exposure` (REAL): Recoverable exposure via governed action.
- `primary_gateway` (TEXT, NULLABLE): Isolated gateway node.
- `error_code` (TEXT, NULLABLE): Isolated error code.
- `anomaly_score` (REAL): ML anomaly score.
- `detected_at` (TEXT): Detection timestamp.
- `description` (TEXT): Detailed symptom narrative.
- `target_entity_id` (TEXT, NULLABLE): Linked target payment/entity ID.

### 11. `historical_cases`
- `incident_id` (TEXT, PK): Historical case ID (e.g. `INC-1282`).
- `title` (TEXT): Historical incident title.
- `type` (TEXT): Incident type.
- `gateway` (TEXT, NULLABLE): Gateway.
- `symptoms_json` (TEXT): List of symptom strings.
- `root_cause` (TEXT): Technical root cause summary.
- `resolution` (TEXT): Precedent remediation resolution.
- `financial_exposure` (REAL): Historical exposure value.
- `outcome` (TEXT): Quantified recovery outcome.
- `summary_text` (TEXT): Dense semantic embedding corpus string.

### 12. `investigations`
- `investigation_id` (TEXT, PK): Investigation report ID.
- `incident_id` (TEXT, FK → `incidents.incident_id`).
- `report_json` (TEXT): Structured JSON matching `InvestigationReport`.
- `status` (TEXT): `pending`, `resolved`, `closed`.
- `created_at` (TEXT): Investigation execution timestamp.

### 13. `audit_logs`
- `audit_id` (TEXT, PK): Unique immutable audit identifier (e.g. `ACT-5B0A49B6`).
- `investigation_id` (TEXT): Linked investigation ID.
- `incident_id` (TEXT): Linked incident ID.
- `timestamp` (TEXT): Execution timestamp.
- `actor` (TEXT): Authorizing actor identity (e.g. `Diwakar_Kaushik (Lead FinOps)`).
- `action_name` (TEXT): Action name (e.g. `pause_gateway_refund_retries`).
- `action_tier` (TEXT): Enforced tier (`red_execute`, `yellow_recommend`, `green_observe`).
- `evidence_summary_json` (TEXT): JSON array of supporting evidence.
- `tools_called_json` (TEXT): JSON array of tools executed during investigation.
- `anomaly_score` (REAL): Anomaly score.
- `ai_confidence` (REAL): Confidence score.
- `root_cause` (TEXT): Root cause summary.
- `recommended_action` (TEXT): Recommended action.
- `approval_status` (TEXT): `approved` or `rejected`.
- `human_approval` (INTEGER): `1` if human approved, `0` if rejected or autonomous.
- `simulated_action_result` (TEXT): Simulated state outcome.
- `financial_exposure` (REAL): Protected financial exposure value.
