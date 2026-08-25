# MoneyOps AI — Razorpay Integration Status & System Audit

**Audit Date:** August 2026  
**Focus:** Transitioning from Internal Prototype to Real Razorpay Test Mode + Synthetic Lab Architecture  

---

## 1. Subsystem Integration Status Map

| Subsystem | Status | Current Implementation | Target Real Implementation |
| :--- | :---: | :--- | :--- |
| **Razorpay API Client** | `MISSING` | None (`config.py` had placeholder key strings) | Official REST API client (`/v1/payments`, `/v1/orders`, `/v1/refunds`) with HTTP Basic Auth, retry/timeout handling, and pagination in `backend/app/integrations/razorpay/`. |
| **Raw Event Storage Layer** | `MISSING` | None (Direct write to `canonical_events`) | Dedicated `raw_external_events` table storing raw JSON bodies, `external_event_id`, `received_at`, processing status, and error logs before normalization. |
| **HMAC Webhook Ingestion** | `PARTIAL` | Endpoint `/api/webhooks/razorpay` verifies `X-Razorpay-Signature` with HMAC-SHA256 | Enhance with `x-razorpay-event-id` deduplication, raw event persistence, out-of-order event handling, and asynchronous event streaming. |
| **API + Webhook Reconciliation** | `MISSING` | Webhooks assumed entities already existed or created basic rows | On-demand API lookup when a webhook arrives for a missing entity (e.g. `refund.processed` before local payment exists). |
| **Data Lineage Tracking** | `PARTIAL` | Entities stored timestamp & IDs | Explicit `source` (`"razorpay_test"` vs `"synthetic"`), `raw_event_id`, `source_created_at`, and `last_synced_at` across all relational tables. |
| **Relational Database** | `REAL` | 13 SQLite tables with foreign keys and WAL mode | Add `raw_external_events` table and source metadata columns. |
| **Synthetic Anomaly Lab** | `REAL` | `generate_data.py --seed 42` (25 merchants, 2500+ tx, 4 golden incidents) | Retain as controlled laboratory for testing rare, severe anomalies not naturally occurring in Test Mode. |
| **ML Anomaly Detection** | `REAL` | Scikit-learn `IsolationForest` on 8 engineered features | Evaluates both real Razorpay transactions and synthetic lab events. |
| **NetworkX Money Graph** | `REAL` | Reconstructed from SQLite relations | Connects real Razorpay entities (`Merchant → Order → Payment → Refund → Webhook`) and synthetic clusters. |
| **Dense Case Memory** | `REAL` | `SentenceTransformer ("all-MiniLM-L6-v2")` 384-d dense cosine similarity | Retain pure mathematical vector search over historical resolved cases. |
| **AI Investigation Agent** | `REAL` | Provider-agnostic ReAct tool-calling loop (Anthropic/Local/Deterministic) | Enforce strict separation between observed facts from tool queries vs root-cause inferences. |
| **Action Governor & Audit** | `REAL` | 3-tier policy model (Green/Yellow/Red) + immutable `audit_logs` | Enable safe bounded test-mode actions (e.g. test refund creation after approval) and simulated mitigations. |
| **Developer CLI Jobs** | `PARTIAL` | `generate_data.py` exists | Add `app.jobs.sync_razorpay`, `app.jobs.rebuild_graph`, `app.jobs.detect_anomalies`, `app.jobs.investigate`, `app.jobs.db_stats`. |
| **Frontend UI** | `REAL` | React 18 + Vite dashboard | Add Data Lineage viewer and explicit Data Source badges (`RAZORPAY TEST MODE` vs `SYNTHETIC LAB`). |

---

## 2. Dual Data Source Architecture

MoneyOps AI now explicitly separates its two valid data sources:

1. **Source A: Razorpay Test Mode (`source="razorpay_test"`)**
   - Real external source providing real payments, orders, refunds, and HMAC-signed webhook payloads.
   - Proves real-world payment gateway integration and ingestion reliability.

2. **Source B: Controlled Incident Laboratory (`source="synthetic"`)**
   - Reproducible baseline dataset (`--seed 42`) injecting complex multi-merchant cascading failures (`INC-2841` Gateway X Spike, `INC-2840` Duplicate Refund Race, `INC-2839` Stuck Settlement, `INC-2838` Retry Velocity).
   - Proves AI agent reasoning, graph traversals, and ML anomaly detection on high-severity operational crises.
