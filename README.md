# MoneyOps AI ⚡

### *AI-Native Financial Incident Investigation & Response Platform*

> **Tagline:** *"When money doesn't add up, MoneyOps finds out why."*

Built by **Diwakar Kaushik (BTech AI & Data Engineering)** for the **Razorpay Internship — Open Track AI Selection**.

---

## 📌 Executive Summary

Modern digital payment platforms process millions of interconnected financial events across **Merchants**, **Orders**, **Payments**, **Refunds**, **Settlements**, **Disputes**, and **Webhooks**. When upstream gateway timeouts or webhook acknowledgement drops occur, standard reconciliation flags a mismatch, but operations teams must answer:
- *What actually happened?*
- *Which merchants and transactions are affected (blast radius)?*
- *How much financial exposure is at risk?*
- *Has this incident pattern occurred before?*
- *What governed remediation action should be executed?*

**MoneyOps AI** sits above basic reconciliation as an autonomous **AI-Powered Incident Investigator**.

---

## 🏛️ System Architecture

```text
               SYNTHETIC WORLD                      RAZORPAY TEST MODE
          (generate_data.py --seed 42)            (POST /api/webhooks/razorpay)
                     │                                         │
                     └────────────────────┬────────────────────┘
                                          ▼
                               CANONICAL INGESTION PIPELINE
                     ┌─────────────────────────────────────────┐
                     │ 1. EventValidator                       │
                     │ 2. EventNormalizer → CanonicalEvent     │
                     │ 3. FeatureProcessor                     │
                     │ 4. AnomalyProcessor (Isolation Forest)  │
                     │ 5. EventRepository                      │
                     └────────────────────┬────────────────────┘
                                          ▼
                              SQLITE RELATIONAL DATABASE
                            (13 Tables, WAL Mode, FKs)
                                          │
            ┌─────────────────────────────┼─────────────────────────────┐
            ▼                             ▼                             ▼
   MERCHANT BEHAVIORAL MEMORY        NETWORKX MONEY GRAPH          CASE MEMORY ENGINE
 (Rolling Baselines & Deviations)  (Entity Traversal & Blast)   (384-d Dense Neural Embeddings)
            │                             │                             │
            └─────────────────────────────┼─────────────────────────────┘
                                          ▼
                             FINANCIAL INVESTIGATION AGENT
                              (Provider-Agnostic LLM ReAct)
                       ┌───────────────────────────────────────┐
                       │ 7 Investigative Python Tools:         │
                       │ - get_incident                        │
                       │ - get_payment / get_payment_graph     │
                       │ - get_gateway_telemetry               │
                       │ - get_merchant_profile                │
                       │ - get_anomaly_features                │
                       │ - find_similar_incidents              │
                       └──────────────────┬────────────────────┘
                                          ▼
                             STRUCTURED INVESTIGATION REPORT
                                (Root Cause & Evidence)
                                          ▼
                                ACTION GOVERNOR (3-Tier)
                                          │
                         ┌────────────────┴────────────────┐
                         ▼                                 ▼
                 [GREEN: Observe]                  [RED: Human Approval]
                         │                                 │
                         └────────────────┬────────────────┘
                                          ▼
                            IMMUTABLE AUDIT LOG (SQLite)
                                          ▼
                         OPERATIONS CONTROL CENTER FRONTEND
                             (React 18 + SVG Money Graph)
```

---

## 🚀 Key Engineering Pillars

1. **Relational Source of Truth:** 13 SQLite tables (`WAL` mode) with explicit foreign keys and query indexes.
2. **Reproducible Data Generation:** `python generate_data.py --seed 42` generates 25 merchants, 300 customers, 2,500+ normal transaction lifecycles, and 4 known golden demo anomalies.
3. **Canonical Event Pipeline:** Heterogeneous events normalize to `CanonicalEvent` and pass through unified validation, anomaly scoring, persistence, and graph updates.
4. **Merchant Behavioral Memory:** Computes rolling payment success rates, refund rates, and baseline deviations via SQL window aggregations.
5. **Unsupervised ML Anomaly Detection:** Scikit-learn `IsolationForest` pipeline trained on 8 engineered financial features.
6. **Cross-Entity Money Graph:** NetworkX directed graph modeling multi-hop payment lifecycles and cross-merchant gateway blast radius.
7. **Dense Vector Semantic Case Memory:** Dense 384-dimensional neural embeddings (`SentenceTransformer all-MiniLM-L6-v2`) computing pure mathematical cosine similarity to match past incident precedents.
8. **Provider-Agnostic AI Agent:** Autonomous ReAct tool-calling loop supporting Anthropic Claude, Local LLMs (Ollama/vLLM), and a deterministic fallback that derives exposure from live query results.
9. **Three-Tier Action Governor:** Enforces policy safety (Green/Yellow/Red) requiring explicit human authorization for state-mutating recovery actions.
10. **Immutable Audit Ledger:** Automatically records forensic evidence, actor authorization, and simulated outcomes with unique audit IDs (e.g. `ACT-5B0A49B6`).
11. **Real Razorpay Test Mode Ingestion:** Validates HMAC-SHA256 signatures (`X-Razorpay-Signature`) and routes live webhooks into the canonical pipeline.

---

## 🛠️ Quick Start & Running Locally

### 1. Prerequisites
- Python 3.10+
- Node.js 18+

### 2. Generate Synthetic Data
```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Generate reproducible baseline dataset & golden demo incidents
python generate_data.py --seed 42 --transactions 2500
```

### 3. Run Automated Tests
```powershell
$env:PYTHONPATH="backend"
.\venv\Scripts\python -m pytest backend/tests/ -v
```

### 4. Start Backend Server
```powershell
$env:PYTHONPATH="backend"
.\venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
* Interactive API Documentation: **`http://127.0.0.1:8000/docs`**

### 5. Start Frontend Dashboard
```powershell
cd frontend
npm run dev
```
* Operations Control Center: **`http://127.0.0.1:5173/`**

---

## 🧪 Golden Demo Scenarios

### Golden Demo 1: Gateway X Refund Timeout Spike (`INC-2841`)
- **Root Cause:** Upstream Gateway X bank node timeout causing systematic drops (HTTP 504 / Error R-104).
- **Blast Radius:** 17 independent merchants, 48+ failing refund pipelines, ₹31.4L potential exposure.
- **Case Memory Precedent:** Matched `INC-1282` via dense vector cosine similarity.
- **Governed Action:** `pause_gateway_refund_retries` (RED Tier) → Human approval required → Executed in simulation → Immutable audit entry created.

### Golden Demo 2: Duplicate Instant Refund Race on P19283 (`INC-2840`)
- **Root Cause:** Dual instant refund execution (`rfnd_R8821` & `rfnd_R8842`) triggered by a 504 webhook acknowledgement timeout.
- **Blast Radius:** Single payment with ₹9,998 debited on a ₹4,999 order (₹4,999 excess exposure).
- **Case Memory Precedent:** Matched `INC-840`.
- **Governed Action:** `freeze_duplicate_refund_workflow` (RED Tier) → Operator approved → Duplicate ledger debit blocked.

---

## 📂 Documentation Directory

Detailed technical documents are available in the [`docs/`](file:///c:/Users/asus/Desktop/RzorPayInternProj/docs/) directory:
- [`docs/IMPLEMENTATION_STATUS.md`](file:///c:/Users/asus/Desktop/RzorPayInternProj/docs/IMPLEMENTATION_STATUS.md) — Subsystem audit & verification map.
- [`docs/ARCHITECTURE.md`](file:///c:/Users/asus/Desktop/RzorPayInternProj/docs/ARCHITECTURE.md) — Architectural design and subsystem interactions.
- [`docs/DATA_MODEL.md`](file:///c:/Users/asus/Desktop/RzorPayInternProj/docs/DATA_MODEL.md) — Relational schema and table dictionary.
- [`docs/DATA_PIPELINE.md`](file:///c:/Users/asus/Desktop/RzorPayInternProj/docs/DATA_PIPELINE.md) — Canonical ingestion pipeline and normalization.
- [`docs/AI_AGENT.md`](file:///c:/Users/asus/Desktop/RzorPayInternProj/docs/AI_AGENT.md) — Multi-turn ReAct agent and tool specifications.
- [`docs/ML_ANOMALY_DETECTION.md`](file:///c:/Users/asus/Desktop/RzorPayInternProj/docs/ML_ANOMALY_DETECTION.md) — Isolation Forest ML feature engine.
- [`docs/CASE_MEMORY.md`](file:///c:/Users/asus/Desktop/RzorPayInternProj/docs/CASE_MEMORY.md) — Dense neural embeddings and cosine similarity.
- [`docs/RAZORPAY_INTEGRATION.md`](file:///c:/Users/asus/Desktop/RzorPayInternProj/docs/RAZORPAY_INTEGRATION.md) — Webhook receiver and signature validation.
- [`docs/GOVERNANCE.md`](file:///c:/Users/asus/Desktop/RzorPayInternProj/docs/GOVERNANCE.md) — 3-tier action permissions and audit logs.
- [`docs/EVALUATION.md`](file:///c:/Users/asus/Desktop/RzorPayInternProj/docs/EVALUATION.md) — Production evolution & interview defense guide.
