# MONEYOPS AI V2 — ARCHITECTURE & DATA FLOW SPECIFICATION

> **System Overview:** Autonomous Financial Incident Investigator for High-Throughput Payment Gateways  
> **Core Principle:** `SOURCE → INGEST → STORE → DETECT → INVESTIGATE → RECOMMEND → APPROVE → EXECUTE (SIMULATED) → AUDIT`

---

## 1. End-to-End System Flow Architecture

```mermaid
flowchart TD
    subgraph SOURCING ["1. Provenance Sources"]
        RP_REST["Live Razorpay Test Mode REST API<br/>(source: razorpay_test)"]
        RP_WH["Live Razorpay Webhooks (HMAC-SHA256)<br/>(source: razorpay_webhook)"]
        LAB["Incident Lab Controlled Generator<br/>(source: incident_lab)"]
    end

    subgraph INGESTION ["2. Canonical Ingestion Pipeline"]
        MAPPER["RazorpayMapper & Invariant Validator"]
        CE["CanonicalEvent (Pydantic Model)"]
        INGEST["IngestionPipeline (Atomic PostgreSQL Upsert)"]
    end

    subgraph STORAGE ["3. Primary PostgreSQL 18 Database (moneyops_v2)"]
        T_MERCHANTS["merchants (10 rows)"]
        T_ORDERS["orders (2,500 rows)"]
        T_PAYMENTS["payments (2,500 rows)"]
        T_REFUNDS["refunds (30 rows)"]
        T_WEBHOOKS["webhook_events (2,500 rows)"]
        T_INCIDENTS["incidents (INC-0001)"]
        T_INVESTIGATIONS["ai_investigations"]
        T_STEPS["ai_investigation_steps"]
        T_ACTIONS["governed_actions"]
        T_AUDIT["audit_logs (Immutable Append-Only)"]
    end

    subgraph DETECTION ["4. Unsupervised ML Anomaly Detection"]
        FEAT["PostgreSQL Feature Matrix Extractor<br/>(failure rates, peer deviation, exposure)"]
        IFOREST["IsolationForest (Unsupervised Scikit-Learn)<br/>contamination=0.05"]
        INC_GEN["Incident Generator (INC-0001 Flagged)"]
    end

    subgraph AI_AGENT ["5. Autonomous Gemini Tool-Calling Agent"]
        LLM["Google Gemini Model<br/>(gemini-3.5-flash-lite)"]
        TOOLS["PostgreSQL Forensic Tool Registry<br/>• get_incident<br/>• get_gateway_metrics<br/>• get_failed_payments<br/>• get_affected_merchants<br/>• get_payment_context<br/>• get_webhook_activity<br/>• find_similar_incidents"]
    end

    subgraph GOVERNOR ["6. Action Governor & Human-in-the-Loop"]
        POLICY["Risk Classifier Policy<br/>• GREEN: Safe / Read-Only<br/>• YELLOW: Operational Confirmation<br/>• RED: Financial / Routing (Mandatory Human Approval)"]
        PENDING["State: pending_approval"]
        HUMAN["Human Operator Authorization<br/>[ Approve ] / [ Reject ]"]
        SIM["Safe Demonstration Simulation<br/>(real_razorpay_payments_modified: 0)"]
    end

    subgraph CONTROL_CENTER ["7. Minimalist Control Center (React 18)"]
        V_OVERVIEW["Overview View (4 Core Metrics + Incident Queue)"]
        V_DATA["Data View (Real vs Simulation Provenance + Ledgers)"]
        V_INVESTIGATION["Investigation View (Telemetry + Trace + Actions)"]
    end

    RP_REST --> MAPPER
    RP_WH --> MAPPER
    LAB --> MAPPER
    MAPPER --> CE --> INGEST --> STORAGE

    STORAGE --> FEAT --> IFOREST --> INC_GEN --> T_INCIDENTS
    T_INCIDENTS --> LLM
    LLM <--> TOOLS
    TOOLS <--> STORAGE
    LLM --> T_INVESTIGATIONS & T_STEPS

    T_INVESTIGATIONS --> POLICY --> PENDING --> HUMAN --> SIM --> T_ACTIONS & T_AUDIT

    STORAGE --> CONTROL_CENTER
```

---

## 2. 7-Stage Pipeline Breakdown

### Stage 1: Data Ingestion & Source Provenance
- **Razorpay REST Adapter:** Queries official Razorpay endpoints (`/v1/orders`, `/v1/payments`, `/v1/refunds`), maps JSON payloads into unified `CanonicalEvent` models, and tags provenance as `source: 'razorpay_test'`.
- **Razorpay Webhooks:** Verifies HMAC-SHA256 signatures with constant-time equality check, enforces event idempotency via `event_id` uniqueness, and tags provenance as `source: 'razorpay_webhook'`.
- **Incident Lab:** Generates high-volume multi-merchant synthetic lifecycles (2,500 transactions across 10 merchants) with seed reproducibility (`seed=42`) and tags provenance as `source: 'incident_lab'`.

### Stage 2: Unified Ingestion Engine
- Converts all entities to immutable `CanonicalEvent` representations.
- Enforces decimal financial precision (never float math).
- Executes idempotent upserts against PostgreSQL 18 with relational integrity (`merchants` $\to$ `orders` $\to$ `payments` $\to$ `refunds`).

### Stage 3: Unsupervised Feature Extraction & Isolation Forest
- **No hardcoding:** The detector possesses zero prior knowledge of `Gateway_X` or injected anomaly types.
- Feature vectors calculate:
  $$\text{Failure Rate} = \frac{\text{Failed Payments}}{\text{Total Attempts}}$$
  $$\text{Peer Deviation} = \frac{\text{Gateway Failure Rate}}{\text{Peer Gateway Baseline}}$$
- `IsolationForest` scans 5-dimensional feature matrices and discovers anomalies with negative anomaly scores.
- Persists structured incident records in `incidents` with severity, financial exposure, and baseline metrics.

### Stage 4: Generative AI Investigation Engine (Google Gemini)
- Triggers multi-turn autonomous tool-calling loop.
- The LLM receives the incident ID and inspects PostgreSQL via parameterized SQL forensic tools:
  1. `get_incident(incident_id)`: Fetches detected anomaly parameters.
  2. `get_gateway_metrics(gateway)`: Computes statistical failure rates, baseline comparisons, and error distributions.
  3. `get_failed_payments(gateway, limit)`: Samples actual transaction failure codes (`GATEWAY_TIMEOUT`).
  4. `get_affected_merchants(gateway)`: Aggregates merchant-specific volume and financial exposure.
- Stores every tool turn (tool name, arguments, database result, latency) into `ai_investigation_steps`.
- Persists final evidence-backed findings into `ai_investigations`.

### Stage 5: Action Governor & Human-in-the-Loop
- Evaluates risk classification for proposed recommendations:
  - `reroute_gateway_traffic` $\to$ **`RED`** (Human approval mandatory).
- Enforces state machine invariants:
  - `pending_approval` $\to$ `approved` (by human operator) $\to$ `executed (SIMULATION)`.
  - Blocks any attempt to execute unapproved actions (HTTP 400).
  - Enforces safe simulation invariant: `real_razorpay_payments_modified: 0`.

### Stage 6: Immutable Append-Only Audit Trail
- Every state transition appends an immutable record into PostgreSQL `audit_logs`:
  - `audit_id`
  - `action_id`
  - `incident_id`
  - `previous_status` $\to$ `new_status`
  - `actor` (e.g. `Gemini_Agent`, `Human_Operator`)
  - `reason` & `execution_result`
  - `timestamp`

### Stage 7: Minimalist FinOps Control Center
- High-signal 3-view UX:
  - **Overview:** 4 Key Metrics (Transactions, Failed Payments, Active Incidents, Exposure) + Active Incident Queue.
  - **Data:** Explicit Real vs Simulation Provenance Breakdown + Tabbed Entity Ledgers.
  - **Investigation:** Structured telemetry (What Happened $\to$ Why $\to$ 4 Evidence Cards $\to$ AI Recommendation $\to$ Action Governor $\to$ Collapsible AI Tool Trace).
