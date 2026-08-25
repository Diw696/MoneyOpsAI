# MoneyOps AI — System Architecture

**Tagline:** *"When money doesn't add up, MoneyOps finds out why."*

MoneyOps AI is an **AI-native financial incident investigation and response platform** built for digital payment operations. Modern payment platforms generate millions of interconnected events: Merchants, Orders, Payments, Refunds, Settlements, Disputes, and Webhooks. MoneyOps sits above basic transaction reconciliation to autonomously detect anomalies, traverse cross-entity relationships, retrieve institutional case precedents, and recommend governed operational actions.

---

## 1. High-Level Architecture Diagram

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

## 2. Core Architectural Subsystems

### 1. Data Ingestion & Normalization (`event_pipeline.py`)
- Standardizes diverse external formats (Razorpay Webhooks, Synthetic Events, Simulator) into an immutable `CanonicalEvent` representation.
- Enforces structural validation and financial consistency before persistence.

### 2. Relational Source of Truth (`database.py`)
- SQLite in Write-Ahead Logging (`WAL`) mode with 13 relational tables and foreign keys.
- Guaranteed relational integrity across `merchants`, `customers`, `orders`, `payments`, `refunds`, `settlements`, `disputes`, `webhook_events`, `canonical_events`, `incidents`, `historical_cases`, `investigations`, and `audit_logs`.

### 3. Merchant Behavioral Memory (`merchant_memory.py`)
- Continuously aggregates rolling payment success rates, refund frequencies, retry patterns, and gateway distribution via SQL window queries.
- Dynamically flags behavioral baseline deviations.

### 4. Unsupervised ML Anomaly Detection (`anomaly_detector.py`)
- Scikit-learn `IsolationForest` pipeline evaluating 8 engineered financial features.
- Produces calibrated anomaly scores $[0, 1]$ and explicit signal contribution attribution.

### 5. Cross-Entity Money Graph (`money_graph.py`)
- NetworkX directed graph built directly from SQLite records.
- Traverses multi-hop entity clusters (`Payment → Order → Customer`, `Payment → Refunds → Webhooks`) and computes cross-merchant gateway blast radius.

### 6. Semantic Vector Case Memory (`case_memory.py`)
- Generates 384-dimensional dense neural embeddings using `SentenceTransformer ("all-MiniLM-L6-v2")`.
- Calculates pure mathematical cosine similarity to match new incident symptoms with historical incident precedents.

### 7. AI Investigation Agent (`agent.py`, `llm_provider.py`)
- Provider-agnostic LLM interface supporting Anthropic, local OpenAI-compatible models (Ollama, vLLM, LMStudio), and a high-fidelity local deterministic reasoner.
- Executes dynamic multi-turn ReAct loops against 7 investigative tools and outputs validated `InvestigationReport` schemas.

### 8. Action Governor & Immutable Audit Ledger (`governor.py`)
- Enforces strict 3-tier policy model (Green Observe, Yellow Recommend, Red Execute).
- Requires explicit operator authorization for destructive or state-mutating actions and logs immutable audit records with unique IDs.
