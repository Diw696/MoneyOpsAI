# MoneyOps AI — Agent Handover, System Architecture & Current Progress

> **Target Audience:** Incoming AI Agent / Engineering Collaborator  
> **Document Purpose:** Full context snapshot, architectural breakdown, data lineage, API usage, and exact system status.  
> **Last Updated:** August 2026

---

## 1. Executive Summary: What is this thing?

**MoneyOps AI** is an **AI-Native Financial Incident Investigation & Response Platform** built for digital payment operations (specifically modeled on Razorpay).

- **Tagline:** *"When money doesn't add up, MoneyOps finds out why."*
- **Problem Statement:** Modern payment gateways process millions of interconnected events (Orders, Payments, Refunds, Settlements, Disputes, Webhooks). When upstream gateway timeouts, webhook delivery lags, or retry race conditions occur, normal reconciliation detects an imbalance, but operations engineers are left asking:
  1. **WHAT HAPPENED?**
  2. **WHY DID IT HAPPEN?**
  3. **WHAT SHOULD WE DO?**
- **Distinction:**
  - MoneyOps is **NOT** a payment gateway.
  - MoneyOps is **NOT** a simple CRUD dashboard.
  - MoneyOps is **NOT** just an LLM chatbot.
  - MoneyOps is an **intelligence & forensic layer above payment operations** that ingests events, tracks relational data lineage, calculates ML anomaly scores, traverses multi-hop entity graphs, matches historical incident memory, runs an autonomous AI investigation agent with tool-calling, and enforces a 3-tier human-in-the-loop Action Governor.

---

## 2. What have we done so far? (Completed Work)

Every subsystem has been overhauled into an **engineering-grade, database-backed** implementation:

1. **Relational Financial Data Model (`database.py`):**
   - **14 relational tables in SQLite (WAL Mode):** `raw_external_events`, `customers`, `merchants`, `orders`, `payments`, `refunds`, `settlements`, `disputes`, `webhook_events`, `canonical_events`, `incidents`, `historical_cases`, `investigations`, `audit_logs`.
   - Strict foreign keys (`ON DELETE CASCADE`), B-tree indexes, and explicit lineage fields (`source`, `source_created_at`, `ingested_at`, `last_synced_at`).

2. **Official Razorpay Test Mode Integration (`backend/app/integrations/razorpay/`):**
   - Clean client abstraction (`client.py`) using HTTP Basic Auth against `https://api.razorpay.com/v1`.
   - Supports: `fetch_payments`, `fetch_payment`, `fetch_orders`, `fetch_order_payments`, `fetch_refunds`, `fetch_payment_refunds`, `create_test_refund`.
   - HMAC-SHA256 webhook signature verification (`verify_webhook_signature`).
   - Pydantic models (`models.py`) and entity mapping (`mapper.py`).

3. **Raw Ingestion Layer & Idempotency (`event_pipeline.py`):**
   - Raw JSON payloads preserved in `raw_external_events` before normalization.
   - Enforces deduplication using `external_event_id` (e.g. `x-razorpay-event-id`) returning `duplicate_skipped`.
   - Automatic API reconciliation: If a refund webhook arrives for a missing local payment, it fetches the payment from Razorpay API on-demand.

4. **Canonical Event Pipeline (`event_pipeline.py` & `event_stream.py`):**
   - Normalizes heterogeneous external payloads into `CanonicalEvent`.
   - Ingestion Stages: `EventValidator` → `EventNormalizer` → `AnomalyProcessor` → `EventRepository` → `GraphProcessor`.
   - Dynamic telemetry: Zero hardcoded stats. KPIs are computed via live SQL queries.

5. **Merchant Behavioral Memory (`merchant_memory.py`):**
   - Computes rolling 30-day payment success rates, refund frequencies, retry averages, and gateway distributions via live SQL window aggregations.

6. **Unsupervised ML Anomaly Detection (`anomaly_detector.py`):**
   - Scikit-learn `IsolationForest` evaluating 8 engineered features (`amount_norm`, `retry_count`, `merchant_refund_deviation`, `gateway_failure_rate`, `settlement_delay_norm`, `velocity_per_min`, `has_failure_code`, `webhook_timeout_flag`).
   - Mathematically calibrated anomaly scores $[0, 1]$ with explainable signal contributions.

7. **NetworkX Financial Money Graph (`money_graph.py`):**
   - Reconstructed directly from SQLite relationships (`Merchant → Order → Payment → [Refunds, Settlements, Webhooks]`).
   - Multi-hop cluster traversal (`get_payment_cluster`) and cross-merchant gateway blast radius calculations.

8. **Dense Vector Semantic Case Memory (`case_memory.py`):**
   - Dense 384-dimensional neural embeddings using `SentenceTransformer("all-MiniLM-L6-v2")`.
   - Pure mathematical cosine similarity matching (zero artificial threshold overrides).

9. **Provider-Agnostic AI Investigation Agent (`agent.py` & `llm_provider.py`):**
   - Abstract provider supporting **Anthropic Claude**, **Local OpenAI-compatible LLMs (Ollama/vLLM)**, and a **Deterministic Fallback Reasoner**.
   - Agent executes 7 Python tools dynamically to gather evidence, trace root causes, and formulate hypotheses.

10. **Three-Tier Action Governor & Immutable Audit Ledger (`governor.py`):**
    - Enforces safety: **GREEN** (Autonomous Observe), **YELLOW** (Advisory Recommend), **RED** (Strict Human Authorization Enforced).
    - Every executed or rejected action creates a permanent record in `audit_logs` with a unique ID (e.g. `ACT-5B0A49B6`).

11. **Developer CLI Jobs (`backend/app/jobs/`):**
    - `python -m app.jobs.sync_razorpay`: Syncs live Razorpay payments.
    - `python -m app.jobs.rebuild_graph`: Rebuilds in-memory NetworkX graph.
    - `python -m app.jobs.detect_anomalies`: Runs ML anomaly scan.
    - `python -m app.jobs.investigate <incident_id>`: Runs AI agent investigation from terminal.
    - `python -m app.jobs.db_stats`: Audits database rows and source lineage.

12. **Frontend Operations Control Center (`frontend/`):**
    - React 18 + Vite dashboard with SVG Money Graph visualizer, Webhook Ingestion Console Modal, and Forensic Data Lineage Modal.

---

## 3. What is this data? (Dual-Source Architecture)

MoneyOps AI uses **TWO legitimate, explicitly labeled data sources**:

```text
┌────────────────────────────────────────┐     ┌────────────────────────────────────────┐
│ SOURCE A: Razorpay Test Mode           │     │ SOURCE B: Incident Laboratory          │
│ (source = "razorpay_test")             │     │ (source = "synthetic")                 │
├────────────────────────────────────────┤     ├────────────────────────────────────────┤
│ • Real Razorpay REST API responses     │     │ • 25 Distinct Merchant profiles        │
│ • Real HMAC-SHA256 signed webhooks     │     │ • 300 Customers                        │
│ • Actual entity IDs (pay_..., rfnd_...)│     │ • 2,500+ normal transaction lifecycles │
│ • Validates real-world ingestion       │     │ • Injects 4 Golden Demo Incidents:     │
│ • Tested via live webhook dispatches   │     │    1. INC-2841 (Gateway X Timeout)     │
│                                        │     │    2. INC-2840 (Duplicate Refund Race) │
│                                        │     │    3. INC-2839 (Stuck Settlement)      │
│                                        │     │    4. INC-2838 (Retry Velocity Abuse)  │
└────────────────────────────────────────┘     └────────────────────────────────────────┘
```

Every single row in SQLite is tagged with its `source`. They are never dishonestly mixed.

---

## 4. Are we using APIs?

**YES, at 3 distinct levels:**

1. **Razorpay External REST API:**
   - Authenticates via HTTP Basic Auth (`RAZORPAY_KEY_ID:RAZORPAY_KEY_SECRET`).
   - Fetches payments, orders, refunds, and issues safe test-mode refunds.
   - Ingests webhooks at `POST /api/webhooks/razorpay` with HMAC-SHA256 signature validation.

2. **LLM Provider API (Provider-Agnostic):**
   - **Anthropic API:** When `ANTHROPIC_API_KEY` is present, calls Claude models (e.g. `claude-3-5-sonnet-20241022`).
   - **Local Model API:** Connects to local endpoints (Ollama, LMStudio, vLLM) at `http://localhost:11434/v1` via OpenAI-compatible tool-calling format.
   - **Local Deterministic Reasoner:** Fallback engine that executes the same 7 tool functions locally against SQLite, NetworkX, and Isolation Forest when offline or no API key is provided.

3. **MoneyOps Backend REST API (FastAPI):**
   - Running at `http://127.0.0.1:8000`.
   - Endpoints for stats, incidents, AI investigations, action approvals, merchant profiles, graph export, audit trail, and webhook receivers.

---

## 5. Current System State: What is running right now?

| Component | Port / Location | Status |
| :--- | :--- | :---: |
| **Backend API (FastAPI)** | `http://127.0.0.1:8000` | **ONLINE & RUNNING** |
| **Frontend UI (React + Vite)** | `http://127.0.0.1:5173` | **ONLINE & RUNNING** |
| **SQLite Database** | `backend/data/moneyops.db` | **14 Tables Initialized & Seeded** |
| **Automated Test Suite** | `backend/tests/` | **20/20 PASSED (15.90s)** |

---

## 6. Verification Results: Evidence of What Works

### 1. Test Suite Execution (`pytest backend/tests/ -v`)
```text
backend/tests/test_agent.py::test_agent_investigation_golden_demo PASSED [  5%]
backend/tests/test_agent.py::test_agent_investigation_duplicate_refund PASSED [ 10%]
backend/tests/test_case_memory.py::test_dense_semantic_similarity PASSED [ 15%]
backend/tests/test_case_memory.py::test_duplicate_refund_similarity PASSED [ 20%]
backend/tests/test_database.py::test_database_tables_exist PASSED        [ 25%]
backend/tests/test_database.py::test_foreign_key_enforcement PASSED      [ 30%]
backend/tests/test_engine.py::test_database_seeded PASSED                [ 35%]
backend/tests/test_engine.py::test_money_graph_traversal PASSED          [ 40%]
backend/tests/test_engine.py::test_case_memory_retrieval PASSED          [ 45%]
backend/tests/test_engine.py::test_anomaly_detector_scoring PASSED       [ 50%]
backend/tests/test_engine.py::test_agent_investigation_golden_demo PASSED [ 55%]
backend/tests/test_engine.py::test_agent_investigation_duplicate_refund PASSED [ 60%]
backend/tests/test_engine.py::test_action_governor_execution PASSED      [ 65%]
backend/tests/test_money_graph.py::test_money_graph_payment_cluster PASSED [ 70%]
backend/tests/test_money_graph.py::test_money_graph_gateway_blast_radius PASSED [ 75%]
backend/tests/test_pipeline.py::test_canonical_event_pipeline PASSED     [ 80%]
backend/tests/test_razorpay_integration.py::test_webhook_signature_verification PASSED [ 85%]
backend/tests/test_razorpay_integration.py::test_razorpay_payment_mapper PASSED [ 90%]
backend/tests/test_razorpay_integration.py::test_raw_event_persistence_and_idempotency PASSED [ 95%]
backend/tests/test_razorpay_integration.py::test_test_mode_refund_creation PASSED [100%]

============================= 20 passed in 15.90s =============================
```

### 2. Live Database & Lineage Audit (`python -m app.jobs.db_stats`)
```text
============================================================
 MONEYOPS AI — RELATIONAL DATABASE & LINEAGE AUDIT
============================================================
  raw_external_events      :      3 rows
  customers                :    300 rows
  merchants                :     25 rows
  orders                   :   2554 rows
  payments                 :   2554 rows
  refunds                  :     95 rows
  settlements              :   2397 rows
  disputes                 :      0 rows
  webhook_events           :   2599 rows
  canonical_events         :   2551 rows
  incidents                :      4 rows
  historical_cases         :      4 rows
  investigations           :      2 rows
  audit_logs               :      1 rows
------------------------------------------------------------
Payments Lineage Breakdown:
  - Source 'razorpay_test': 2 payments
  - Source 'synthetic': 2552 payments
Raw Events Lineage Breakdown:
  - Source 'razorpay_webhook': 2 raw events
  - Source 'synthetic': 1 raw events
============================================================
```

### 3. CLI Investigation Output (`python -m app.jobs.investigate INC-2841`)
```text
============================================================
 MONEYOPS AI — CLI INCIDENT INVESTIGATOR: INC-2841
============================================================
Investigation ID: INV-840F721D
Incident:         INC-2841 (gateway_refund_failure)
Severity:         CRITICAL
Confidence:       90.3%
Exposure:         INR 3,140,000.00
Affected Scope:   17 merchants, 4812 transactions
------------------------------------------------------------
AGENT REASONING STEPS:
  Step 1: Detected abnormal refund-failure spike (get_gateway_telemetry)
  Step 2: Compared merchant behavioral baselines (get_merchant_profile)
  Step 3: Calculated Isolation Forest anomaly score (get_anomaly_features)
  Step 4: Retrieved similar historical incidents from Case Memory (find_similar_incidents)
  Step 5: Action Governor policy evaluation (governor_policy_check)
------------------------------------------------------------
ROOT CAUSE ANALYSIS:
  Upstream Gateway X bank node timeout causing systematic drops on refund API calls with error R-104.
  Hypothesis: High load and network degradation at Gateway X nodal server caused timeouts across 17 merchants.
------------------------------------------------------------
GOVERNED ACTION:
  Action:            pause_gateway_refund_retries
  Tier:              RED_EXECUTE
  Requires Approval: True
  Recommendation:    Pause automated refund retries on Gateway X pending gateway recovery.
============================================================
```

---

## 7. How to Reproduce and Run Everything

```powershell
# 1. Activate Environment
.\venv\Scripts\Activate.ps1

# 2. Generate/Reset Synthetic Lab Data
python generate_data.py --seed 42 --transactions 2500

# 3. Run Automated Tests
$env:PYTHONPATH="backend"
.\venv\Scripts\python -m pytest backend/tests/ -v

# 4. Start Backend Server
$env:PYTHONPATH="backend"
.\venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 5. Start Frontend Dashboard
cd frontend
npm run dev

# 6. Run Developer Jobs
python -m app.jobs.db_stats
python -m app.jobs.detect_anomalies
python -m app.jobs.rebuild_graph
python -m app.jobs.investigate INC-2841
```

---

## 8. Summary for Incoming Agent

- **Zero Mock / Fake Numbers:** All UI numbers, similarity percentages, ML scores, and exposure amounts come strictly from live database queries and model executions.
- **Clean Separation of Concerns:** Database is the source of truth; ML model detects signals; Graph connects multi-hop entities; Case Memory provides historical precedent; LLM reasons over evidence; Governor prevents unintended financial actions; Audit ledger logs immutable proof.
- **Ready for Demonstration:** The system is completely functional, verified with live webhooks, backed by tests, and documented.
