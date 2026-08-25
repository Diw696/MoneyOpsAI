# MoneyOps AI — Implementation Status & Subsystem Audit

**Document Version:** 1.0.0  
**Audit Date:** August 2026  
**Auditor:** Antigravity AI Engineering Suite  
**Benchmark:** Pipeone Engineering Quality Reference  

---

## 1. Subsystem Implementation Map

| Subsystem | Classification | Primary File(s) | Persisted? | Tested? | Summary & Findings |
| :--- | :---: | :--- | :---: | :---: | :--- |
| **Relational Database & Schema** | `REAL` | `backend/app/engine/database.py` | Yes (SQLite WAL) | Yes | 11 relational tables with foreign keys and indexes. Clean SQLite implementation. |
| **Synthetic Event & Baseline Generator** | `PARTIAL` | `backend/app/engine/seed_data.py` | Yes (SQLite) | Yes | Generates 25 merchants, 300 customers, 2,500+ normal transactions, and 4 known golden incidents. **Need:** Explicit CLI argument parsing (`--seed 42`) and dynamic anomaly feature calculations. |
| **Event Ingestion & Processing Pipeline** | `PARTIAL` | `backend/app/engine/event_stream.py` | Partial | Partial | Uses `asyncio.Queue`. **Audit Finding:** Had static initial counters (`12482`, `38`, `3.36M`) in memory. Must calculate stats directly from live SQLite relations. Needs canonical event schema (`CanonicalEvent`). |
| **Merchant Behavioral Memory** | `REAL` | `backend/app/engine/merchant_memory.py` | Yes (Dynamic SQL) | Yes | Calculates rolling payment success rate, refund rate, retry averages, and gateway distributions via dynamic SQL queries over payment history. |
| **Unsupervised ML Anomaly Detection** | `REAL` | `backend/app/engine/anomaly_detector.py` | Yes | Yes | Scikit-learn `IsolationForest` pipeline trained on 8 engineered features (amount, retries, refund deviation, gateway error, etc.). Output calibrated to [0, 1]. |
| **NetworkX Money Graph** | `REAL` | `backend/app/engine/money_graph.py` | In-Memory (Built from DB) | Yes | Directed graph constructed directly from SQLite relations. Supports `get_payment_cluster()`, `get_gateway_blast_radius()`, and visual subgraph export. |
| **Dense Semantic Case Memory** | `PARTIAL` | `backend/app/engine/case_memory.py` | Yes (SQLite + Dense Vectors) | Yes | Dense 384-d vector embeddings using `SentenceTransformer("all-MiniLM-L6-v2")`. **Audit Finding:** Had legacy domain threshold overrides (`max(raw_score, 0.912)`). Must rely exclusively on pure cosine similarity mathematical calculation. |
| **AI Investigation Agent & Tool Calling** | `PARTIAL` | `backend/app/engine/agent.py`, `llm_provider.py` | Yes | Yes | Provider-agnostic interface (`AnthropicProvider`, `OpenAICompatibleProvider`, `DeterministicFallbackProvider`). **Audit Finding:** Deterministic fallback branch had hardcoded summary numbers (`pot_exp = 3140000.0`, `aff_merch = 17`). Must calculate these dynamically from the tool responses (`get_gateway_telemetry`). |
| **Action Governor & Policy Engine** | `REAL` | `backend/app/engine/governor.py` | Yes (SQLite `audit_logs`) | Yes | 3-tier policy model (Green/Yellow/Red) enforcing operator authorization for sensitive recovery actions and logging immutable audit entries. |
| **Razorpay Test Mode Webhook Receiver** | `REAL` | `backend/app/api/routes.py`, `config.py` | Yes (SQLite) | Yes | `POST /api/webhooks/razorpay` verifies HMAC-SHA256 signatures (`X-Razorpay-Signature`), ingests payment/refund events, and updates SQLite + Money Graph in real-time. |
| **REST API Layer** | `REAL` | `backend/app/api/routes.py` | Yes | Yes | Clean FastAPI endpoints returning dynamic database and model state. |
| **Operations Control Center UI** | `PARTIAL` | `frontend/src/` | Visual Layer | Yes | React 18 + Vite dashboard. **Audit Finding:** A few static fallback text strings in `OperationsKPIs.jsx` (e.g. `+480/min`). Needs 100% dynamic status binding. |

---

## 2. End-to-End Value Trace (UI → Database)

To verify that numbers are mathematically traceable and not fabricated:

### Metric: "Potential Exposure" on Incident `INC-2840` (Duplicate Refund Race)
1. **Frontend Display:** `InvestigationStudio.jsx` displays **₹4,999** under "POTENTIAL FINANCIAL EXPOSURE".
2. **API Endpoint:** Fetched via `GET /api/incidents/INC-2840` from `routes.py`.
3. **Database Row:** Query `SELECT * FROM incidents WHERE incident_id = 'INC-2840'` in `moneyops.db` returns:
   - `incident_id`: `INC-2840`
   - `potential_exposure`: `4999.0`
   - `target_entity_id`: `pay_P19283`
4. **Underlying Financial Entities:**
   - Query `SELECT * FROM payments WHERE payment_id = 'pay_P19283'` → `amount: 4999.0`, `order_id: ord_O8821`.
   - Query `SELECT * FROM refunds WHERE payment_id = 'pay_P19283'` → Returns 2 rows:
     - `rfnd_R8821`: `amount: 4999.0`, `status: processed`
     - `rfnd_R8842`: `amount: 4999.0`, `status: processed`
   - Total refund amount issued: $4999.0 + 4999.0 = ₹9,998.0$ against a captured payment of ₹4,999.0.
   - Exact duplicate exposure calculated: $₹9,998 - ₹4,999 = ₹4,999.0$.
5. **Conclusion:** Traceable directly to database entity records.

---

## 3. Systematic Action Plan (Phases 1 — 15)

1. **Phase 1 (Data Model):** Add explicit canonical event table, enrich schema with foreign key constraints, and add database utility tests.
2. **Phase 2 (Data Generator):** Create dedicated `generate_data.py` CLI supporting `--seed` and deterministic generation of baseline and 4 injected anomaly scenarios with exact documentation.
3. **Phase 3 (Ingestion Pipeline):** Implement canonical event schema `CanonicalEvent` and clean pipeline boundaries (`EventSource` -> `EventNormalizer` -> `EventValidator` -> `EventRepository` -> `FeatureProcessor` -> `GraphProcessor` -> `AnomalyProcessor`). Remove all in-memory static counters from `event_stream.py`.
4. **Phase 4 (Merchant Memory):** Remove any remaining static assumptions; ensure all baseline rates and deviations are derived from SQL window aggregations.
5. **Phase 5 (Real ML):** Ensure Isolation Forest model is trained on real generated historical feature tables, outputs mathematical anomaly scores, and provides structured signal attribution.
6. **Phase 6 (Money Graph):** Verify all graph traversals (`get_payment_cluster`, `get_gateway_blast_radius`) execute purely on SQLite-derived NetworkX nodes and edges.
7. **Phase 7 (Semantic Case Memory):** Remove all domain override constants; rely 100% on mathematical cosine similarity of dense 384-d `all-MiniLM-L6-v2` embeddings.
8. **Phase 8 (AI Agent):** Remove any static numbers from the deterministic fallback reasoner; compute financial exposure, merchant count, and transaction count dynamically from tool outputs (`get_gateway_telemetry`).
9. **Phase 9 (Governor & Audit):** Ensure all actions are persisted in `audit_logs` and queryable via `/api/audit`.
10. **Phase 10 (Razorpay Webhooks):** Route incoming webhooks through the same canonical pipeline as synthetic events.
11. **Phase 11 (API Layer):** Ensure `/api/stats`, `/api/incidents`, `/api/merchants`, `/api/graph`, `/api/audit` only return database-backed computations.
12. **Phase 12 (Frontend Connection):** Remove all mock placeholders and bind telemetry directly to API responses.
13. **Phase 13 (Testing Suite):** Build comprehensive pytest suite covering all 11 modules independently.
14. **Phase 14 (Observability):** Implement structured operational telemetry logging.
15. **Phase 15 (Golden Demo & Documentation):** Update all docs in `docs/` and `README.md`.
