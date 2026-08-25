# MoneyOps AI — Razorpay Test Mode & Webhook Integration

MoneyOps AI integrates with **Razorpay Test Mode** as its primary real external data source, combining real REST API lookups with HMAC-SHA256 authenticated webhook stream ingestion.

---

## 1. Supported Razorpay REST API Endpoints

Implemented in [`backend/app/integrations/razorpay/client.py`](file:///c:/Users/asus/Desktop/RzorPayInternProj/backend/app/integrations/razorpay/client.py):

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `fetch_payments()` | `GET /v1/payments` | Fetches payments with pagination and timestamp range filtering. |
| `fetch_payment(id)` | `GET /v1/payments/{id}` | Fetches individual payment details. |
| `fetch_orders()` | `GET /v1/orders` | Fetches orders from Razorpay API. |
| `fetch_order_payments(id)` | `GET /v1/orders/{id}/payments` | Fetches all payments associated with an order. |
| `fetch_refunds()` | `GET /v1/refunds` | Fetches all refunds. |
| `fetch_payment_refunds(id)` | `GET /v1/payments/{id}/refunds` | Fetches all refunds issued against a specific payment. |
| `create_test_refund(id, amt)`| `POST /v1/payments/{id}/refund` | Creates a test-mode refund as a Governed Action. |

---

## 2. Webhook Ingestion & Idempotency Pipeline

- **Endpoint:** `POST /api/webhooks/razorpay`
- **Security:** HMAC-SHA256 validation of raw request body against `X-Razorpay-Signature`.
- **Idempotency:** Checks `x-razorpay-event-id` in `raw_external_events` table before processing. Duplicate deliveries return HTTP 200 with `status="duplicate_skipped"`.
- **Out-of-Order Reconciliation:** If a refund webhook arrives before the local payment entity exists, MoneyOps queries the Razorpay Payments API on-demand to fetch and persist the parent payment before completing normalization.

---

## 3. Developer Jobs & CLI Tooling

MoneyOps provides standalone CLI commands for pipeline synchronization and testing:

```powershell
# 1. Synchronize payments from Razorpay Test Mode API
python -m app.jobs.sync_razorpay --count 20

# 2. Rebuild NetworkX Money Graph from SQLite
python -m app.jobs.rebuild_graph

# 3. Run Isolation Forest ML anomaly scan across payments
python -m app.jobs.detect_anomalies

# 4. Run AI Agent multi-turn investigation for an incident
python -m app.jobs.investigate INC-2841

# 5. Print complete relational database tables and source lineage
python -m app.jobs.db_stats
```
