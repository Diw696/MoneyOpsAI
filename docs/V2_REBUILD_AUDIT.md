# MoneyOps AI V2 — System Audit & Clean Rebuild Plan

**Audit Date:** August 2026  
**Objective:** Transition from an over-engineered, visually noisy prototype into a **clean, modular, production-grade AI Financial Incident Investigator** powered by **Razorpay Test Mode + Google Gemini API**.

---

## 1. Executive Summary & V2 Product Definition

### What MoneyOps AI Is:
> **"An AI financial incident investigator for Razorpay payment operations."**

It answers three fundamental operational questions:
1. **WHAT HAPPENED?** (Blast radius, error surge, financial exposure)
2. **WHY DID IT HAPPEN?** (Upstream bank timeout, webhook acknowledgement drop, retry race condition)
3. **WHAT SHOULD WE DO?** (Governed remediation recommendation based on historical incident memory)

### Core Architectural Flow:
```text
Razorpay Test Mode (API & Webhooks)
        ↓
Data Ingestion (Sync & Webhook Ingestion)
        ↓
SQLite Database (9 Clean Relational Tables)
        ↓
Financial Analysis & Feature Engine
        ↓
Isolation Forest Anomaly Detection
        ↓
AI Investigation Agent (Google Gemini Tool-Calling Loop)
        ↓
Governed Recommendation (3-Tier Safety Policy)
        ↓
Human Operator Approval
        ↓
Immutable Audit Log
```

---

## 2. Comprehensive Inventory of Current Subsystems

### A. Current Structure
```text
c:\Users\asus\Desktop\RzorPayInternProj\
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py              # REST API endpoints
│   │   ├── core/
│   │   │   └── config.py              # Settings & environment variables
│   │   ├── engine/
│   │   │   ├── agent.py               # AI Agent ReAct loop & deterministic fallback
│   │   │   ├── anomaly_detector.py    # Scikit-learn Isolation Forest
│   │   │   ├── case_memory.py         # SentenceTransformer semantic case retrieval
│   │   │   ├── database.py            # SQLite database schema (14 tables)
│   │   │   ├── event_pipeline.py      # Canonical ingestion pipeline & raw event store
│   │   │   ├── event_stream.py        # Async streaming queue
│   │   │   ├── governor.py            # 3-tier action policy & audit logger
│   │   │   ├── llm_provider.py        # LLM provider abstraction (Anthropic/Local)
│   │   │   ├── merchant_memory.py     # SQL rolling merchant baselines
│   │   │   ├── money_graph.py         # NetworkX directed graph
│   │   │   └── seed_data.py           # Synthetic data generator
│   │   ├── integrations/
│   │   │   └── razorpay/              # Razorpay client, models, mapper, exceptions
│   │   ├── jobs/                      # Standalone developer CLI jobs
│   │   ├── models/
│   │   │   └── schemas.py             # Pydantic data schemas
│   │   └── main.py                    # FastAPI application initialization
│   └── tests/                         # 7 test modules (20 unit/integration tests)
└── frontend/
    ├── src/
    │   ├── components/                # 10 React components (Heavy UI & visualizers)
    │   ├── App.jsx                    # Main frontend state coordinator
    │   └── index.css                  # Design system tokens & CSS styling
    ├── package.json
    └── vite.config.js
```

---

## 3. Reusable Components vs. Broken / Over-Engineered Components

### Reusable Components (Keep & Adapt for V2):
1. **Razorpay Client (`backend/app/integrations/razorpay/`):**
   - [`client.py`](file:///c:/Users/asus/Desktop/RzorPayInternProj/backend/app/integrations/razorpay/client.py): Clean HTTP Basic Auth against `https://api.razorpay.com/v1`, official endpoints (`/payments`, `/orders`, `/refunds`), HMAC-SHA256 signature verification, error handling.
   - [`models.py`](file:///c:/Users/asus/Desktop/RzorPayInternProj/backend/app/integrations/razorpay/models.py) & [`mapper.py`](file:///c:/Users/asus/Desktop/RzorPayInternProj/backend/app/integrations/razorpay/mapper.py): Clean normalization into canonical internal models.
2. **ML Anomaly Detector (`backend/app/engine/anomaly_detector.py`):**
   - Scikit-learn `IsolationForest` evaluating engineered features (`amount_norm`, `retry_count`, `refund_deviation`, `gateway_failure_rate`, etc.).
   - Pure mathematical score $[0, 1]$ and signal contributions.
3. **Semantic Case Memory (`backend/app/engine/case_memory.py`):**
   - `SentenceTransformer("all-MiniLM-L6-v2")` computing 384-dimensional dense neural embeddings and pure cosine similarity against resolved incident precedents.
4. **Action Governor (`backend/app/engine/governor.py`):**
   - 3-tier policy model (`GREEN_OBSERVE`, `YELLOW_RECOMMEND`, `RED_EXECUTE_WITH_APPROVAL`) and audit record creation.

### Broken / Over-Engineered Components (To Discard or Drastically Simplify):
1. **NetworkX Money Graph as Homepage Centerpiece (`money_graph.py`, `MoneyGraphVisualizer.jsx`):**
   - 10,500+ node in-memory graph rendered on the main dashboard caused visual clutter and confusion. In V2, entity relationships will be queried directly via clean SQL joins and presented as clear tabular/list evidence in the Investigation view.
2. **Information-Dense Multi-Card UI (`OperationsKPIs.jsx`, `SystemArchitectureModal.jsx`):**
   - 8 decorative KPI cards, complex architecture modals, and excessive tabs distract from the core product flow.
3. **Complex Async Streaming Queue (`event_stream.py`):**
   - Async background event loop simulating live ticks is replaced with direct, predictable HTTP endpoints (`POST /api/razorpay/sync` and `POST /api/webhooks/razorpay`).

---

## 4. Current Database vs. Target V2 Database

### Current Database (14 Tables — Too Wide):
`raw_external_events`, `customers`, `merchants`, `orders`, `payments`, `refunds`, `settlements`, `disputes`, `webhook_events`, `canonical_events`, `incidents`, `historical_cases`, `investigations`, `audit_logs`.

### Target V2 Database (9 Clean Tables Only):
1. **`merchants`**: `merchant_id`, `name`, `category`, `baseline_refund_rate`, `created_at`
2. **`orders`**: `order_id`, `merchant_id`, `amount`, `currency`, `status`, `source`, `created_at`
3. **`payments`**: `payment_id`, `order_id`, `merchant_id`, `amount`, `currency`, `status`, `method`, `gateway`, `failure_code`, `retry_count`, `source`, `created_at`, `ingested_at`
4. **`refunds`**: `refund_id`, `payment_id`, `merchant_id`, `amount`, `status`, `speed`, `failure_reason`, `source`, `created_at`
5. **`webhook_events`**: `event_id`, `external_event_id`, `event_type`, `entity_id`, `payload_json`, `signature_valid`, `delivery_status`, `source`, `received_at`
6. **`incidents`**: `incident_id`, `title`, `type`, `severity`, `status`, `affected_merchants`, `affected_payments`, `potential_exposure`, `anomaly_score`, `source`, `detected_at`, `description`
7. **`ai_investigations`**: `investigation_id`, `incident_id`, `provider`, `model`, `what_happened`, `why_it_happened`, `evidence_json`, `recommendation`, `confidence`, `started_at`, `completed_at`, `status`
8. **`ai_investigation_steps`**: `step_id`, `investigation_id`, `step_number`, `tool_name`, `input_json`, `output_json`, `timestamp`
9. **`audit_logs`**: `audit_id`, `investigation_id`, `incident_id`, `actor`, `action_name`, `action_tier`, `approval_status`, `operator_notes`, `timestamp`

---

## 5. AI Reasoning: Moving to Real Google Gemini Tool-Calling

### Current Status:
- Uses an abstraction that fell back to a local deterministic reasoner when no Anthropic key was configured.
- Steps were generated internally by hardcoded tool sequences.

### Target V2 Implementation:
- **Primary AI Provider:** **Google Gemini API** (`gemini-2.0-flash` or `gemini-1.5-pro`) using the official `google-genai` / `google-generativeai` SDK.
- **Provider Abstraction:** Gemini primary, optional Anthropic/OpenAI, and an explicitly labeled `DETERMINISTIC FALLBACK` when offline.
- **Genuine Tool-Calling Loop:**
  The Gemini model is provided 7 structured tools:
  - `get_incident(incident_id)`
  - `get_payment(payment_id)`
  - `get_order(order_id)`
  - `get_refunds(payment_id)`
  - `get_webhook_history(entity_id)`
  - `get_merchant_activity(merchant_id)`
  - `search_previous_incidents(query)`
- The model autonomously determines which tools to call in sequence.
- Every real execution is written to `ai_investigation_steps` and streamed/polled by the UI.
- If AI API is unreachable, UI displays: `AI Unavailable (Offline)` or `Deterministic Fallback (Simulation)`.

---

## 6. Target V2 API Routes

```text
# Health & Status
GET  /api/health

# Razorpay Test Mode Ingestion & Sync
POST /api/razorpay/sync
POST /api/webhooks/razorpay

# Financial Data Entities
GET  /api/payments
GET  /api/orders
GET  /api/refunds
GET  /api/webhooks

# Incident Operations
GET  /api/incidents
GET  /api/incidents/{incident_id}

# Real AI Investigation
POST /api/ai/investigate/{incident_id}
GET  /api/ai/investigations/{investigation_id}

# Governed Action Approval
POST /api/actions/{action_id}/approve
POST /api/actions/{action_id}/reject
GET  /api/audit
```

---

## 7. Target V2 Minimalist Frontend (3 Clean Pages Only)

Delete the cluttered dashboard. Replace with 3 focused pages:

### Page 1: Overview
- **Header Badge:** `Razorpay Test Mode ● Connected` | Last sync timestamp.
- **Minimal KPIs (4 numbers only):** Total Payments, Total Refunds, Active Incidents, Total Exposure.
- **Incident Cards:** Clean cards showing title, severity badge, affected counts, exposure, and a single `[ Investigate ]` button.

### Page 2: Data
- **Header:** `[ Sync Now ]` button (calls `POST /api/razorpay/sync`).
- **Entity Tables:** Tabbed view of `Payments`, `Orders`, `Refunds`, and `Webhook Events`.
- Every row explicitly shows `Source` (`RAZORPAY TEST MODE` vs `SYNTHETIC LAB`) and timestamps.

### Page 3: Investigation (The Core Product View)
- **Top:** Incident ID, Title, Severity, Financial Exposure.
- **Structured Findings:**
  1. **WHAT HAPPENED** (Factual summary of anomalies & affected entities)
  2. **WHY DID IT HAPPEN** (Root-cause hypothesis from evidence)
  3. **EVIDENCE** (Granular records returned by tools)
  4. **RECOMMENDATION** (Governed action with risk tier & approval button)
- **Real AI Investigation Trace (Drawer/Timeline):**
  - Displays each actual tool call recorded in `ai_investigation_steps`.
  - Expandable to view raw tool Input JSON, Output JSON, and Model Name.

---

## 8. V2 Rebuild Phased Execution Plan

```text
Phase 1: Audit Only (Complete — docs/V2_REBUILD_AUDIT.md)
  ↓ [Wait for Approval]
Phase 2: Clean 9-Table Database Schema + Razorpay Client
  ↓ [Verify & Report]
Phase 3: Real POST /api/razorpay/sync Endpoint
  ↓ [Verify & Report]
Phase 4: Verify Real Razorpay Data in SQLite
  ↓ [Verify & Report]
Phase 5: Real POST /api/webhooks/razorpay Ingestion with HMAC-SHA256
  ↓ [Verify & Report]
Phase 6: Feature Engine & Isolation Forest Anomaly Detection
  ↓ [Verify & Report]
Phase 7: Google Gemini AI Provider Integration (Official SDK)
  ↓ [Verify & Report]
Phase 8: Multi-Turn Tool-Calling Investigation Agent + Step Logging
  ↓ [Verify & Report]
Phase 9: Action Governor & Immutable Audit Ledger
  ↓ [Verify & Report]
Phase 10: 3-Page Minimalist Frontend (Overview, Data, Investigation)
  ↓ [Verify & Report]
Phase 11: End-to-End Test Suite & Verification
```

---

## 9. Next Action

Phase 0 Audit is complete. We are stopped and awaiting explicit approval before executing Phase 2.
