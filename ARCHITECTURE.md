# MoneyOps AI — Technical Architecture & System Specification

## 1. System Overview

MoneyOps AI is architected as a modular, event-driven intelligence layer for fintech operations. It decouples high-throughput event ingestion from multi-hop relational graph traversals, unsupervised ML anomaly detection, vector similarity case memory retrieval, and governed agentic reasoning.

---

## 2. Component Specifications

### 2.1 Lean Event Streaming & Ingestion Engine (`backend/app/engine/event_stream.py`)
- Implements an asynchronous producer-consumer queue via Python's `asyncio.Queue`.
- Each event (`payment.captured`, `payment.failed`, `refund.processed`, `refund.failed`, `settlement.delayed`, etc.) is normalized to a canonical schema, validated, and concurrently dispatched to:
  1. The **Merchant Behavioral Memory** profiler.
  2. The **Money Graph** node/edge relationship builder.
  3. The **Isolation Forest Anomaly Detector**.

### 2.2 Merchant Behavioral Memory (`backend/app/engine/merchant_memory.py`)
- Standard anomaly detection fails in multi-merchant fintech environments because a 3% refund rate might be normal for a travel booking platform but catastrophic for a B2B SaaS platform.
- Merchant Behavioral Memory continuously computes rolling 30-day baseline vectors for each merchant:
  $$\text{Deviation}_{\text{merchant}} = \frac{\text{CurrentRate} - \mu_{\text{baseline}}}{\sigma_{\text{baseline}}}$$
- Metrics tracked: `baseline_refund_rate`, `baseline_retry_count`, `baseline_settlement_latency_hrs`, `failure_code_distribution`, `gateway_distribution`.

### 2.3 Unsupervised Anomaly Detection (`backend/app/engine/anomaly_detector.py`)
- Employs `scikit-learn`'s `IsolationForest` ($n_{\text{estimators}}=100, \text{contamination}=0.05$).
- Evaluates an 8-dimensional feature vector:
  $$\vec{x} = \begin{bmatrix} \text{amount\_norm}, \text{retry\_count}, \text{refund\_dev}, \text{gw\_fail\_rate}, \text{settle\_delay\_norm}, \text{velocity}, \text{fail\_code\_flag}, \text{timeout\_flag} \end{bmatrix}$$
- Outputs a normalized Anomaly Score $S \in [0.0, 1.0]$. Scores $>0.65$ trigger incident alerts; scores $>0.90$ trigger critical sentinel alerts.

### 2.4 In-Memory Money Graph (`backend/app/engine/money_graph.py`)
- Powered by `NetworkX` as a directed multi-edge graph ($G = (V, E)$).
- Node types: `Merchant`, `Customer`, `Order`, `Payment`, `Refund`, `Settlement`, `Dispute`, `Gateway`, `WebhookEvent`.
- Edge relations: `PLACED`, `FULFILLS`, `PAID_WITH`, `ROUTED_TO`, `REFUNDED_BY`, `SETTLED_IN`, `DISPUTED_IN`, `TRIGGERED_WEBHOOK`.
- Key Graph Operations:
  - `get_payment_cluster(payment_id)`: 2-hop bidirectional traversal extracting all linked refunds, settlements, and webhooks.
  - `get_gateway_blast_radius(gateway_name, error_code)`: Subgraph expansion calculating the cross-merchant impact radius.
  - `export_subgraph_for_vis(target_id)`: JSON export with computed 2D layout coordinates for visual UI rendering.

### 2.5 Vector Case Memory (`backend/app/engine/case_memory.py`)
- Provides institutional memory of past incident post-mortems and resolutions.
- Uses TF-IDF / character and n-gram vectorization with cosine similarity:
  $$\text{Sim}(Q, C_i) = \frac{\vec{q} \cdot \vec{c}_i}{\|\vec{q}\| \|\vec{c}_i\|}$$
- Pre-seeded with realistic fintech case precedents (e.g. Incident #1282 Gateway X timeout, Incident #840 Duplicate refund race, Incident #512 Settlement batch lag).

### 2.6 Multi-Stage AI Investigation Agent (`backend/app/engine/agent.py`)
- Encapsulates 4 sequential reasoning stages:
  1. **Sentinel Stage**: Ingests anomaly trigger and calculates impact blast radius.
  2. **Investigator Stage**: Traverses the Money Graph to isolate the exact technical trigger (e.g., 504 webhook timeout).
  3. **Analyst Stage**: Compares against merchant baselines and vector Case Memory to evaluate financial exposure and historical precedents.
  4. **Recovery Stage**: Synthesizes structured root-cause explanations and formulates a governed action proposal.

### 2.7 Action Governor & Audit Trail (`backend/app/engine/governor.py`)
- Enforces strict 3-tier access control:
  - **GREEN (Observe)**: Telemetry inspection, read-only graph queries, anomaly scoring.
  - **YELLOW (Recommend)**: Merchant advisory notices, non-critical parameter tuning.
  - **RED (Execute with Approval)**: Consequential financial state modifications (e.g., `pause_gateway_refund_retries`, `freeze_duplicate_refund_workflow`).
- Every approval/rejection is recorded in the `audit_logs` table with unique Audit ID, actor identity, timestamp, evidence payload, and simulated execution output.

---

## 3. Frontend Operations Control Center

- Built with **React 18 + Vite**, custom modern dark-mode fintech design system, and **Lucide Icons**.
- Interactive features:
  - Real-time Operations KPIs and throughput ticker.
  - Prioritized Active Incident Queue with severity badges and instant "Investigate" triggers.
  - Visual Money Graph SVG renderer with node details inspector.
  - Step-by-Step Agent Reasoning Activity Log with collapsible raw tool evidence.
  - Historical Case Memory precedent match card.
  - Action Governor console with one-click **[APPROVE & EXECUTE]** / **[REJECT]** controls and live audit confirmation.
  - Merchant Behavioral Memory explorer with baseline deviation filters.
  - Complete searchable Governed Audit Trail table.
