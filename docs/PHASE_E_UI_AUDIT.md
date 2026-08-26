# MONEYOPS AI V2 — PHASE E UI & ARCHITECTURE AUDIT

> **Document Status:** Comprehensive Frontend & API Architecture Review  
> **Goal:** Plan the productization into a minimalist 3-view FinOps Incident Control Center (`OVERVIEW`, `DATA`, `INVESTIGATION`).  
> **Rule:** Strict audit only — no UI code modified until approved.

---

## 1. Current Frontend Architecture

### Technology Stack:
- **Build Tool / Bundler:** Vite 8.2.2 with React 18.3.1.
- **Styling:** Vanilla CSS with modern dark mode tokens in `src/index.css`.
- **API Client:** Native `fetch` HTTP client in `src/api.js` pointing to `http://localhost:8000/api`.
- **Current Layout Structure:** Single-page dashboard (`App.jsx`) with a sticky `Header.jsx`, a 2-column workspace (`340px` Left Queue + `1fr` Right Studio), and interval polling (5s).

---

## 2. Existing Routes & Navigation

Currently, the frontend does not use multi-page routing (e.g. `react-router-dom`). Everything is mounted in a single screen:
- **Current View:** Split layout with active incident queue on the left and `InvestigationStudio` on the right.
- **Target View Structure (Phase E Requirement):**
  A clean 3-tab primary navigation bar in the header:
  1. **`OVERVIEW`** ("What is happening right now?")
  2. **`DATA`** ("Where did this evidence come from?")
  3. **`INVESTIGATION`** ("What happened, why, and what should we do?")

---

## 3. Existing API Endpoints & Frontend Consumption

All backend endpoints are live in `backend/app/api/routes.py` and backed by PostgreSQL 18:

| Endpoint | Method | Purpose | Frontend Status in `api.js` |
| :--- | :---: | :--- | :--- |
| `/api/health` | `GET` | System health, DB connection, Razorpay/Gemini config flags | Implemented |
| `/api/stats` | `GET` | Live PostgreSQL row counts (`merchants`, `orders`, `payments`, `refunds`, `webhooks`, `incidents`) | Implemented (`fetchStats`) |
| `/api/stats/sources` | `GET` | Breakdown by source (`razorpay_test`, `razorpay_webhook`, `incident_lab`) | Implemented (`fetchSourceStats`) |
| `/api/razorpay/sync` | `POST` | Live Razorpay Test Mode REST sync | Implemented (`syncRazorpay`) |
| `/api/incident-lab/generate` | `POST` | Reproducible Incident Lab data generator | Implemented (`generateLabData`) |
| `/api/anomalies/detect` | `POST` | IsolationForest unsupervised ML scan across PostgreSQL | Implemented (`triggerAnomalyDetection`) |
| `/api/payments` | `GET` | Filterable payment records with provenance source | Implemented (`fetchPayments`) |
| `/api/orders` | `GET` | Filterable order records with provenance source | Implemented (`fetchOrders`) |
| `/api/refunds` | `GET` | Filterable refund records with provenance source | Implemented (`fetchRefunds`) |
| `/api/webhooks` | `GET` | Received webhook logs with signatures and payloads | Implemented (`fetchWebhooks`) |
| `/api/incidents` | `GET` | Active & historical incidents | Implemented (`fetchIncidents`) |
| `/api/incidents/{id}` | `GET` | Single incident detail with evidence breakdown | Implemented (`fetchIncidentDetail`) |
| `/api/ai/status` | `GET` | Gemini connection status & active model name | Implemented (`fetchAIStatus`) |
| `/api/incidents/{id}/investigate` | `POST` | Multi-turn Gemini tool-calling investigation | Implemented (`runInvestigation`) |
| `/api/investigations/{id}` | `GET` | Stored forensic investigation report | Implemented (`fetchInvestigation`) |
| `/api/investigations/{id}/steps` | `GET` | Stored tool-calling trace steps & latencies | Implemented (`fetchInvestigationSteps`) |
| `/api/actions/propose` | `POST` | Proposed governed action with risk policy | Implemented (`proposeAction`) |
| `/api/actions/{id}/approve` | `POST` | Human operator authorization | Implemented (`approveAction`) |
| `/api/actions/{id}/reject` | `POST` | Human operator rejection | Implemented (`rejectAction`) |
| `/api/actions/{id}/execute` | `POST` | Safe demonstration simulation executor | Implemented (`executeAction`) |
| `/api/incidents/{id}/actions` | `GET` | List of governed actions for an incident | Implemented (`fetchIncidentActions`) |
| `/api/audit-logs` | `GET` | Immutable append-only audit trail logs | Implemented (`fetchAuditLogs`) |

---

## 4. Components Review: Reusable vs Obsolete

### Reusable Components (Keep & Refactor):
1. **`Header.jsx`:** Clean header bar with compact branding, system status indicators (`Razorpay`, `PostgreSQL`, `Gemini`), and tab navigation (`OVERVIEW`, `DATA`, `INVESTIGATION`).
2. **`InvestigationStudio.jsx`:** Refactor into the primary **`INVESTIGATION`** view with the exact structured hierarchy (Incident Header $\to$ What Happened $\to$ Why $\to$ Evidence Cards $\to$ Affected Merchants $\to$ AI Recommendation $\to$ Action Governor $\to$ Collapsible AI Tool Trace).

### Obsolete V1 Components (To Be Safely Removed or Replaced):
1. **`OperationsKPIs.jsx`:** Outdated 8+ KPI card widget with legacy SQLite assumptions.
2. **`MoneyGraphVisualizer.jsx`:** Obsolete V1 NetworkX SVG graph with synthetic node clustering.
3. **`MerchantBaselinesView.jsx`:** Unused standalone baseline view.
4. **`AuditTrailView.jsx`:** V1 modal view (now superseded by Action Governor in `InvestigationStudio`).
5. **`DataLineageModal.jsx`:** Obsolete modal with static SVG lineage.
6. **`SystemArchitectureModal.jsx`:** Obsolete architecture diagram modal.
7. **`WebhookSimulatorModal.jsx`:** Obsolete V1 simulator modal (now superseded by official webhook adapter).
8. **`IncidentQueue.jsx`:** Obsolete duplicate incident queue list.

---

## 5. Hardcoded / Mock Data Audit

During the audit, we inspected all frontend files for fake data, mock fallback objects, and decorative placeholders:
- **`Header.jsx`:** Had fallback values (`2501` payments, `2.0-flash` model). $\to$ Must strictly render live `stats.payments` and `aiStatus.model`.
- **`InvestigationStudio.jsx`:** Contained static fallback evidence cards when `incident.evidence` was absent. $\to$ Must strictly render live evidence from PostgreSQL or clean empty state.
- **`OperationsKPIs.jsx` & `MerchantBaselinesView.jsx`:** Contained hardcoded demo metrics. $\to$ Will be removed completely.
- **Provenance Rules:** In the new **`DATA`** view, explicitly show `REAL: source = razorpay_test / razorpay_webhook` vs `SIMULATION: source = incident_lab` with exact PostgreSQL counts.

---

## 6. Recommended Phase E Minimalist 3-View Structure

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ MONEYOPS AI  [ Overview ]  [ Data ]  [ Investigation ]       ● Razorpay ● PostgreSQL ● Gemini │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### View 1: `OVERVIEW` ("What is happening right now?")
1. **Top Status Indicators:** Compact indicators for `Razorpay Test Mode`, `PostgreSQL 18`, and `Google Gemini`.
2. **4 Core Operational Metrics:**
   - **Total Transactions** (`stats.payments`)
   - **Failed Payments** (`87` or sum of failed payments)
   - **Active Incidents** (`stats.incidents`)
   - **Potential Exposure** (`₹158,842.85`)
3. **Active Incident Cards:**
   - Clean card for **`INC-0001`**: Severity `CRITICAL`, Title `Gateway_X Payment Failure Spike`, Metrics `19.08% failure rate (5.42x baseline)`, `87 failed payments`, `₹158,842 exposure`, and **`[ ⚡ Investigate Incident ]`** button transitioning directly to View 3.
   - If 0 incidents: "✓ All systems operating normally within standard operational baselines."

### View 2: `DATA` ("Where did this evidence come from?")
1. **Top Action:** `[ ⚡ Sync Razorpay Test Mode ]` button.
2. **Provenance Summary Cards:**
   - **REAL RAZORPAY:** Orders count, Payments count, Refunds count (`source = 'razorpay_test' / 'razorpay_webhook'`).
   - **INCIDENT LAB (SIMULATION):** Orders count (2,500), Payments count (2,500), Refunds count (30) (`source = 'incident_lab'`).
3. **Clean Tabular Explorers:**
   - **Payments:** `ID`, `Order ID`, `Amount (INR)`, `Status`, `Gateway`, `Source`, `Created At`.
   - **Orders:** `ID`, `Amount (INR)`, `Status`, `Source`, `Created At`.
   - **Refunds:** `ID`, `Payment ID`, `Amount (INR)`, `Status`, `Source`, `Created At`.
   - **Webhooks:** `Event ID`, `Event Type`, `Signature Verified`, `Source`, `Received At`.

### View 3: `INVESTIGATION` ("What happened, why, and what should we do?")
1. **Incident Header:** Title, Target Entity (`Gateway_X`), Severity (`CRITICAL`), Failure Rate (`19.08%`), Peer Baseline (`3.52%`), Potential Exposure (`₹158,842.85`).
2. **What Happened?** Plain-language explanation from PostgreSQL/Gemini.
3. **Why Did It Happen?** Root cause finding (`GATEWAY_TIMEOUT` 85.06% share).
4. **4 Evidence Cards:**
   - `19.08% Failure Rate`
   - `3.52% Peer Baseline (5.42x deviation)`
   - `74 / 87 Timeout Failures`
   - `₹158,842.85 Potential Exposure`
5. **Affected Merchants:** Compact counter (`10 merchants affected`) with toggleable list.
6. **AI Recommendation:** Gemini's generated operational recommendation + Confidence (`99%`).
7. **Action Governor & Human Approval:**
   - `Risk: RED (Human Authorization Mandatory)`
   - State indicators: `RECOMMENDED` $\to$ `APPROVED BY HUMAN` $\to$ `EXECUTED (SIMULATION)`.
   - Controls: `[ Approve Action ]`, `[ Reject Action ]`, `[ Execute Safe Simulation ]`.
   - Explicit confirmation: *"0 live Razorpay payments modified."*
8. **AI Tool Trace (Collapsed by Default):**
   - Step 1: `get_incident`
   - Step 2: `get_gateway_metrics`
   - Step 3: `get_failed_payments`
   - Step 4: `get_affected_merchants`
   - Expandable arguments, database output JSON, and latency.

---

## 7. Action Plan for Phase E Implementation

1. **Clean up obsolete components:** Delete `AuditTrailView.jsx`, `DataLineageModal.jsx`, `IncidentQueue.jsx`, `MerchantBaselinesView.jsx`, `MoneyGraphVisualizer.jsx`, `OperationsKPIs.jsx`, `SystemArchitectureModal.jsx`, `WebhookSimulatorModal.jsx`.
2. **Create 3 focused view components in `src/components/`:**
   - `OverviewView.jsx`
   - `DataView.jsx`
   - `InvestigationView.jsx`
3. **Update `Header.jsx` & `App.jsx`:** Add 3-tab navigation state and clean transition logic.
4. **End-to-End Verification:** Verify all 3 pages against live PostgreSQL, test human approval and safe simulation flow, verify 39/39 backend tests pass.

---

**AUDIT COMPLETE.** Awaiting approval to proceed with Phase E UI implementation.
