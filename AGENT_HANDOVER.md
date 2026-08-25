# MoneyOps AI — Agent Handover & Quick Reference

> **Full Documentation:** See [`docs/AGENT_HANDOVER_AND_STATUS.md`](file:///c:/Users/asus/Desktop/RzorPayInternProj/docs/AGENT_HANDOVER_AND_STATUS.md) for exhaustive architectural specifications, mathematical models, and database schema dictionaries.

---

## ⚡ Quick Answers for Any Incoming AI Agent

### 1. What is the whole thing? (Product Definition)
**MoneyOps AI** is an **AI-native financial incident investigator** for digital payment platforms (Razorpay).  
When payment/refund/settlement anomalies occur, MoneyOps answers:
1. **WHAT HAPPENED?** (Blast radius, affected merchants, exposure)
2. **WHY DID IT HAPPEN?** (Cross-entity graph traversal, retry races, gateway timeout root cause)
3. **WHAT SHOULD WE DO?** (Dense vector case memory matching + Governed action recommendation)

### 2. What have we done?
- **14 SQLite Tables (WAL Mode):** Full relational schema with foreign keys, query indexes, and a dedicated `raw_external_events` table.
- **Official Razorpay Test Mode Client:** Authenticated REST client (`fetch_payments`, `fetch_orders`, `fetch_refunds`, `create_test_refund`) with HMAC-SHA256 webhook signature validation.
- **Raw Layer & Idempotency:** Raw JSON persistence, `x-razorpay-event-id` deduplication, and on-demand parent entity reconciliation.
- **Canonical Event Pipeline:** Ingests external streams into `CanonicalEvent` with pure database-derived operational KPIs.
- **Merchant Behavioral Memory:** Rolling 30-day baseline deviations computed via live SQL window queries.
- **Unsupervised ML Anomaly Detection:** Scikit-learn `IsolationForest` pipeline on 8 engineered financial features.
- **NetworkX Money Graph:** Graph traversal modeling `Merchant → Order → Payment → [Refunds, Settlements, Webhooks]`.
- **Dense Case Memory:** 384-dimensional dense neural embeddings (`SentenceTransformer all-MiniLM-L6-v2`) with pure mathematical cosine similarity.
- **Provider-Agnostic Agent:** Multi-turn ReAct tool-calling loop (Anthropic Claude, Local Ollama/vLLM, or Local Deterministic Reasoner).
- **Three-Tier Action Governor:** Green (Observe), Yellow (Recommend), Red (Human Authorization Enforced) with immutable SQLite `audit_logs`.
- **20 Automated Tests:** 100% passing test suite in `backend/tests/`.
- **React 18 Dashboard:** Live Operations Control Center with SVG Money Graph, Webhook Simulator, and Forensic Data Lineage view.

### 3. What is this data? (Dual Data Source)
1. **`source="razorpay_test"` (Razorpay Test Mode):** Live REST API payloads and HMAC-SHA256 signed webhooks.
2. **`source="synthetic"` (Incident Laboratory):** Generated via `python generate_data.py --seed 42` (25 merchants, 300 customers, 2,500+ normal txs, and 4 injected golden anomalies).

### 4. Are we using APIs?
- **Razorpay REST API:** (`https://api.razorpay.com/v1`) with HTTP Basic Auth.
- **LLM APIs:** Anthropic Claude API / Local OpenAI-compatible API (`http://localhost:11434/v1`) / Local Deterministic Reasoner.
- **MoneyOps Backend API:** FastAPI on `http://127.0.0.1:8000`.

### 5. What is running right now?
- **Backend API:** `http://127.0.0.1:8000` (Running in background task-570)
- **Frontend UI:** `http://127.0.0.1:5173` (Running in background task-129)
- **Database:** `backend/data/moneyops.db` (Initialized & Seeded)

---

## 🛠️ Key Commands to Run / Inspect

```powershell
# 1. Run all tests
$env:PYTHONPATH="backend"
.\venv\Scripts\python -m pytest backend/tests/ -v

# 2. Inspect Database Lineage & Row Counts
python -m app.jobs.db_stats

# 3. Run Isolation Forest Anomaly Scan
python -m app.jobs.detect_anomalies

# 4. Rebuild Money Graph from SQLite
python -m app.jobs.rebuild_graph

# 5. Run AI Investigation Agent via CLI
python -m app.jobs.investigate INC-2841

# 6. Re-seed Synthetic Incident Lab
python generate_data.py --seed 42 --transactions 2500
```
