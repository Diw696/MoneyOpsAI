# MONEYOPS AI V2 — COMPLETE AGENT HANDOVER & SYSTEM STATE

> **Repository:** `https://github.com/Diw696/MoneyOpsAI` (Branch: `main`)  
> **Architecture Level:** Clean V2 Engineering Rebuild (Phases 1 through Phase C Complete)  
> **Database:** PostgreSQL 18.1 (`moneyops_v2` on `127.0.0.1:5432`)  
> **Last Updated:** August 26, 2026

---

## 1. Executive Product Definition

**MoneyOps AI** is an **AI-assisted financial incident investigator for Razorpay digital payment operations**.

When payment anomalies, failure spikes, refund velocity deviations, or settlement rejections occur, MoneyOps answers:
1. **WHAT HAPPENED?** (Blast radius, failure volume, affected merchants, potential financial exposure)
2. **WHY DID IT HAPPEN?** (Root cause identification, banking gateway timeout signatures, error code concentration)
3. **WHAT SHOULD WE DO?** (Actionable mitigation recommendations, traffic diversion, and governed operations execution)

### 🚨 Core Philosophy & Non-Negotiable Invariants:
```text
SOURCE ──► INGEST ──► STORE ──► PROCESS ──► DETECT ──► INVESTIGATE ──► RECOMMEND
```
- **NO Hardcoded Incidents:** The system never fabricates incidents or fake AI narratives.
- **NO Bypassing the Pipeline:** Real Razorpay data and Incident Lab simulations pass through the exact same `CanonicalEvent` $\to$ `IngestionPipeline` $\to$ PostgreSQL path.
- **NO Fake AI Fallbacks:** If `GEMINI_API_KEY` is not present, the system explicitly reports `AI_NOT_CONFIGURED` / `AI OFFLINE`.
- **Auditable Provenance:** Every record carries explicit provenance: `source = 'razorpay_test'`, `source = 'razorpay_webhook'`, or `source = 'incident_lab'`.

---

## 2. End-to-End System Architecture

```text
┌─────────────────────────┐
│ Real Razorpay REST API  │──► [Razorpay Mapper] ──┐
└─────────────────────────┘                        │
                                                   │
┌─────────────────────────┐                        │
│ Real Razorpay Webhooks  │──► [Webhook Adapter] ──┼──► [CanonicalEvent]
└─────────────────────────┘                        │            │
                                                   │            ▼
┌─────────────────────────┐                        │   [IngestionPipeline]
│ Incident Lab Generator  │──► [Lab Adapter] ──────┘            │
└─────────────────────────┘                                     ▼
                                                       [PostgreSQL 18 Database]
                                                           (moneyops_v2)
                                                                │
                                                                ▼
                                                        [Feature Engine]
                                                        (Dynamic SQL Metrics)
                                                                │
                                                                ▼
                                                       [IsolationForest ML]
                                                        (Unsupervised Outlier)
                                                                │
                                                                ▼
                                                      [Incidents Table] (INC-0001)
                                                                │
                                                                ▼
                                                    [Google Gemini 2.0 Agent]
                                                  (Multi-Turn Tool Calling Loop)
                                                                │
                                        ┌───────────────────────┴───────────────────────┐
                                        ▼                                               ▼
                           [7 PostgreSQL Forensic Tools]                      [InvestigationStudio UI]
                           - get_incident                                     - What Happened
                           - get_gateway_metrics                              - Why (Root Cause)
                           - get_failed_payments                              - Impact & Exposure
                           - get_affected_merchants                           - Evidence Cards
                           - get_payment_context                              - Action Recommendation
                           - get_webhook_activity                             - Auditable Tool Trace
                           - find_similar_incidents
```

---

## 3. Work Completed Till Now (Phases Breakdown)

### Phase 1–4: Foundation & Live Razorpay REST Connectivity
- Connected live Razorpay Test Mode account (`rzp_test_TU6z7jmcjJLP4N`).
- Implemented authenticated REST client (`fetch_orders`, `fetch_payments`, `fetch_refunds`).
- Verified real HTTP request $\to$ actual Razorpay JSON response $\to$ database persistence.

### Phase 5: Live Webhook Ingestion & HMAC-SHA256 Verification
- Implemented `POST /api/webhooks/razorpay`.
- Enforced cryptographic signature verification (`X-Razorpay-Signature`) and idempotency via `x-razorpay-event-id`.

### Phase 5.5: SQLite $\to$ PostgreSQL 18 Migration
- Migrated primary persistence from SQLite to PostgreSQL 18 (`moneyops_v2`).
- Recreated clean 9-table schema with foreign keys (`ON DELETE CASCADE`) and performance indexes.
- Archived legacy SQLite databases into `archive/moneyops_v1_sqlite/`.

### Phase A: Unified Data Ingestion Foundation
- Created centralized `CanonicalEvent` validation contract ([`pipeline.py`](file:///c:/Users/asus/Desktop/RzorPayInternProj/backend/app/engine/pipeline.py)) and transactional batch ingestion engine.
- Created `IncidentLabGenerator` ([`incident_lab.py`](file:///c:/Users/asus/Desktop/RzorPayInternProj/backend/app/engine/incident_lab.py)) generating reproducible multi-merchant financial lifecycles with controllable anomaly modes (`gateway_spike`, `refund_spike`, `duplicate_refund`, `webhook_retry`).
- Added observability endpoints `GET /api/stats` and `GET /api/stats/sources`.

### Phase B: Feature Engine & Isolation Forest Anomaly Detection
- Built explainable feature engine ([`feature_engine.py`](file:///c:/Users/asus/Desktop/RzorPayInternProj/backend/app/engine/feature_engine.py)) computing failure rates, peer gateway baselines, error code concentrations, and exposure.
- Fitted unsupervised `sklearn.ensemble.IsolationForest` ([`anomaly_detector.py`](file:///c:/Users/asus/Desktop/RzorPayInternProj/backend/app/engine/anomaly_detector.py)) without hardcoded gateway rules.
- Discovered anomaly on **`Gateway_X`** (**19.08% failure rate vs 3.52% peer baseline**, 87 rejections, 74 `GATEWAY_TIMEOUT` errors).
- Created structured incident **`INC-0001`** in PostgreSQL with INR 158,842.85 potential exposure.
- Verified second-run deduplication and healthy-dataset zero-anomaly verification.

### Phase C: Real AI Investigation Engine & Gemini Tool Calling
- ### Phase D: Restrained Action Governor & Human-in-the-Loop Approval (Completed)
- Built centralized `ActionGovernor` ([`action_governor.py`](file:///c:/Users/asus/Desktop/RzorPayInternProj/backend/app/engine/action_governor.py)) with strict 3-tier risk policy (`GREEN`, `YELLOW`, `RED`).
- Enforced mandatory human operator authorization for high-stakes operational changes (e.g. `reroute_gateway_traffic` classified as `RED`).
- Implemented state machine transitions: `pending_approval` -> `approved` / `rejected` -> `executed (SIMULATION)`.
- Enforced safe simulation execution (`real_razorpay_payments_modified: 0`) blocking all destructive real Razorpay modifications.
- Built immutable append-only audit trail persisting every transition in PostgreSQL `audit_logs`.
- Added Action Governor UI controls to `InvestigationStudio.jsx` clearly demarcating recommended, approved, rejected, and simulated states.
- 39/39 automated tests passing across the entire test suite.

---

## 4. Everything Updated, Changed, and Archived

| Category | Component | Status / Changes Made |
| :--- | :--- | :--- |
| **Database** | PostgreSQL 18.1 (`moneyops_v2`) | Active primary database replacing legacy SQLite. |
| **Archived DB** | `archive/moneyops_v1_sqlite/` | Archived `moneyops.db` and `moneyops_v2.db`. |
| **Archived Tests** | `archive/legacy_v1_tests/` | Moved legacy V1 test scripts (`test_agent.py`, `test_case_memory.py`, `test_money_graph.py`, etc.). |
| **Ingestion** | `backend/app/engine/pipeline.py` | Centralized `CanonicalEvent` and `IngestionPipeline`. |
| **ML Detector** | `backend/app/engine/anomaly_detector.py` | Unsupervised `IsolationForest` with PostgreSQL feature matrix. |
| **AI Agent** | `backend/app/engine/gemini_agent.py` | Google Gemini 2.0/3.0 tool-calling agent. |
| **Tool Registry** | `backend/app/engine/investigation_tools.py` | 7 PostgreSQL parameterized forensic tools. |
| **Action Governor**| `backend/app/engine/action_governor.py` | 3-tier risk-governed human-in-the-loop authorization & safe simulation. |
| **Frontend** | `frontend/src/` | Minimalist investigation studio with collapsible auditable trace and action controls. |

---

## 5. Active PostgreSQL Database State (`moneyops_v2`)

| Table Name | Active Row Count | Primary Key | Key Relationships / Purpose |
| :--- | :---: | :--- | :--- |
| **`merchants`** | **10** | `merchant_id` | Master merchant directory with category & baseline refund rates. |
| **`orders`** | **2,500** | `order_id` | Orders with status and amount in decimal INR. |
| **`payments`** | **2,500** | `payment_id` | Payments with gateway, method, failure code, and timestamps. |
| **`refunds`** | **30** | `refund_id` | Processed refunds with speed, reason, and merchant FKs. |
| **`webhook_events`** | **2,500** | `event_id` | Validated webhook logs with raw payloads and delivery status. |
| **`incidents`** | **1** | `incident_id` | **`INC-0001`** (`Gateway_X Failure Spike`, ₹158,842.85 exposure). |
| **`ai_investigations`** | **Dynamic** | `investigation_id` | Stored forensic investigation reports from Gemini. |
| **`ai_investigation_steps`** | **Dynamic** | `step_id` | Auditable tool-calling execution trace with arguments and latencies. |
| **`governed_actions`** | **Dynamic** | `action_id` | Governed actions with risk level, approval status, and simulation results. |
| **`audit_logs`** | **Dynamic** | `audit_id` | Immutable append-only audit trail of all authorizations & simulations. |

---

## 6. Live Forensic Tool Registry (Gemini Accessible)

1. **`get_incident(incident_id: str)`** -> Metadata, severity, anomaly score from `incidents`.
2. **`get_gateway_metrics(gateway: str)`** -> Failure rate (19.08%), peer rate (3.52%), top error (`GATEWAY_TIMEOUT`), exposure.
3. **`get_failed_payments(gateway: str, limit: int)`** -> Transaction logs with failure codes and timestamps.
4. **`get_affected_merchants(gateway: str)`** -> Cross-merchant failure aggregation and exposure breakdown.
5. **`get_payment_context(payment_id: str)`** -> Relational graph: `payment` -> `order` -> `merchant` -> `refunds` -> `webhooks`.
6. **`get_webhook_activity(gateway: str, limit: int)`** -> Webhook event delivery logs and signatures.
7. **`find_similar_incidents(incident_type: str)`** -> Historical precedent lookup.

---

## 7. Active Services & Ports

| Service | Technology | Address / Port |
| :--- | :--- | :--- |
| **PostgreSQL Database** | PostgreSQL 18.1 | `127.0.0.1:5432` (DB: `moneyops_v2`) |
| **Backend API Server** | FastAPI / Uvicorn | `http://127.0.0.1:8000` |
| **Frontend UI Dev Server** | Vite / React 18 | `http://127.0.0.1:5173` |

---

## 8. CLI Commands Quick Reference

```powershell
# 1. Run Complete Automated Test Suite (39 tests)
$env:PYTHONPATH="backend"
.\venv\Scripts\python -m pytest backend/tests/ -v

# 2. View Real PostgreSQL Row Counts & Source Provenance
$env:PYTHONPATH="backend"
.\venv\Scripts\python -m app.jobs.db_stats

# 3. Trigger Unsupervised ML Anomaly Detection
$env:PYTHONPATH="backend"
.\venv\Scripts\python -m app.jobs.detect_anomalies

# 4. Run AI Investigation CLI (INC-0001)
$env:PYTHONPATH="backend"
.\venv\Scripts\python -m app.jobs.investigate_incident --incident INC-0001
```icorn | `http://127.0.0.1:8000` | `task-1262` |
| **Frontend UI Dev Server** | Vite / React 18 | `http://127.0.0.1:5173` | `task-1291` |

---

## 8. CLI Commands Quick Reference

```powershell
# 1. Run Complete Automated Test Suite (32 tests)
$env:PYTHONPATH="backend"
.\venv\Scripts\python -m pytest backend/tests/ -v

# 2. View Real PostgreSQL Row Counts & Source Provenance
$env:PYTHONPATH="backend"
.\venv\Scripts\python -m app.jobs.db_stats

# 3. Trigger Unsupervised ML Anomaly Detection
$env:PYTHONPATH="backend"
.\venv\Scripts\python -m app.jobs.detect_anomalies

# 4. Run AI Investigation CLI (INC-0001)
$env:PYTHONPATH="backend"
.\venv\Scripts\python -m app.jobs.investigate_incident --incident INC-0001

# 5. Generate Controlled Incident Lab Dataset
$env:PYTHONPATH="backend"
.\venv\Scripts\python -m app.jobs.generate_incident_lab --seed 42 --payments 2500 --anomaly gateway_spike
```

---

## 9. Next Planned Phase: Phase D (Action Governor)

When approved, **Phase D** will implement:
- Three-tier Action Governor:
  - **Tier 1 (Green / Observe):** Safe read-only diagnostics.
  - **Tier 2 (Yellow / Recommend):** Traffic shifting recommendations.
  - **Tier 3 (Red / High-Stakes Action):** Automatic merchant refund pauses, gateway traffic cutover, requiring explicit human operator cryptographic approval.
- Immutable PostgreSQL `audit_logs` persistence for every action attempt.
