# MONEYOPS AI V2 — INTERACTIVE DEMONSTRATION SCRIPT

This step-by-step demonstration showcases how **MoneyOps AI V2** discovers, investigates, and safely remediates payment anomalies across live Razorpay integrations and high-volume merchant networks.

---

## Prerequisites & Quick Start

Ensure the system is active:

```powershell
# Terminal 1: Backend Server
$env:PYTHONPATH="backend"
.\venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2: Frontend Control Center
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173` in your browser.

---

## 10-Step End-to-End Demonstration Script

### Step 1: Open Overview View & Inspect System Health
- **What to look for:**
  - Status indicators in the top bar: `Razorpay: Test Mode`, `PostgreSQL: 2,500 txs`, `AI: Gemini (gemini-3.5-flash-lite)`.
  - The 4 Core Operational Metrics:
    - `Total Transactions`: **2,500**
    - `Failed Payments`: **87**
    - `Active Incidents`: **1**
    - `Potential Exposure`: **₹158,842.85**
  - The Active Incident card for **`INC-0001`** (`Gateway_X Payment Failure Spike`).
- **Narrative:** *"MoneyOps AI continuously ingests payment lifecycles and monitors telemetry without relying on static thresholds."*

---

### Step 2: Trigger Live Unsupervised Anomaly Detection
- Click **`[ ↻ Run Anomaly Scan ]`** in the Overview view.
- **What happens:**
  - The backend executes `anomaly_detector.run_detection()`, extracting multi-dimensional features from PostgreSQL and executing Scikit-Learn `IsolationForest`.
  - A green notification banner confirms: `✓ Detection scan complete. 1 anomalies evaluated across 2500 PostgreSQL records.`
- **Narrative:** *"The anomaly detector has zero hardcoded knowledge of Gateway_X. It dynamically discovered that Gateway_X exhibited a 19.08% failure rate compared to the 3.52% peer baseline (5.42x deviation)."*

---

### Step 3: Navigate to Data Provenance Ledger
- Click the **`[ 📦 Data ]`** tab in the top navigation bar.
- **What to look for:**
  - **REAL RAZORPAY TEST MODE:** Shows exact counts ingested from live Razorpay REST/Webhook endpoints (`source: razorpay_test / webhook`).
  - **INCIDENT LAB (SIMULATION):** Shows exact counts ingested from laboratory datasets (`source: incident_lab`).
  - Click between **`Payments`**, **`Orders`**, **`Refunds`**, and **`Webhooks`** tabs.
  - Filter by `Real (razorpay_test)` or `Simulation (incident_lab)`.
- **Narrative:** *"Every single record in MoneyOps AI carries immutable provenance. We never mix or disguise synthetic simulation data as live production payments."*

---

### Step 4: Test Live Razorpay Synchronization
- Click **`[ ⚡ Sync Live Razorpay Test Mode ]`**.
- **What happens:**
  - The backend calls official Razorpay REST APIs (`https://api.razorpay.com/v1/payments`, `orders`, `refunds`), converts raw payloads to `CanonicalEvent` objects, and upserts them atomically into PostgreSQL.
  - A notification confirms live synchronization.

---

### Step 5: Open Forensic Investigation Studio
- Click the **`[ 🔍 Investigation ]`** tab in the header (or click **`[ ⚡ Investigate Incident ]`** on the `INC-0001` card in Overview).
- **What to look for:**
  - Incident header with `CRITICAL` severity, Target `Gateway_X`, and detection timestamp.
  - Section 1: **What Happened?** (Plain-language summary of 87 failed payments out of 456 attempts).
  - Section 2: **Why Did It Happen?** (Root cause identification).
  - Section 3: **4 Evidence Cards** (`19.08% Failure Rate`, `3.52% Peer Baseline`, `74 / 87 Timeout Failures`, `₹158,842.85 Potential Exposure`).
  - Section 4: **Affected Merchants** (Click `▼ View Affected Merchants` to see breakdown across 10 merchants).

---

### Step 6: Trigger Autonomous Gemini Investigation
- Click **`[ ⚡ Investigate with Gemini ]`**.
- **What happens:**
  - The autonomous Gemini Agent initiates a multi-turn tool-calling conversation with Google Generative Language v1beta API.
  - Gemini autonomously selects and executes 4 parameterized tools against PostgreSQL:
    1. `get_incident({"incident_id": "INC-0001"})`
    2. `get_gateway_metrics({"gateway": "Gateway_X"})`
    3. `get_failed_payments({"gateway": "Gateway_X", "limit": 25})`
    4. `get_affected_merchants({"gateway": "Gateway_X"})`
  - Gemini analyzes the relational evidence and outputs a root-cause report and operational recommendation with 99% confidence.

---

### Step 7: Inspect Collapsible AI Tool Execution Trace
- Scroll to Section 7: **`🛠️ AI Investigation Trace`** and expand it.
- **What to look for:**
  - Click on **Step 1**, **Step 2**, **Step 3**, and **Step 4**.
  - Inspect the exact JSON arguments Gemini provided, the real PostgreSQL dataset returned, and the execution latency in milliseconds.
- **Narrative:** *"This inspectable trace proves Gemini is performing genuine database forensics rather than fabricating generative text."*

---

### Step 8: Observe Action Governor Safety Block
- Scroll to Section 6: **`Action Governor & Human-in-the-Loop`**.
- **What to look for:**
  - Badge: `RISK: RED • HUMAN AUTHORIZATION REQUIRED`.
  - State: `PENDING APPROVAL`.
  - Action description: `Reroute traffic away from Gateway_X to backup partner nodes (SBI / ICICI / HDFC)`.
- **Narrative:** *"Because rerouting traffic is a high-stakes financial operation, the Action Governor classifies it as RED. AI cannot execute this action autonomously."*

---

### Step 9: Human Operator Authorization
- Click **`[ ✓ APPROVE ACTION ]`**.
- **What happens:**
  - The state transitions to `APPROVED BY HUMAN`.
  - A new button appears: **`[ ⚡ EXECUTE SAFE SIMULATION ]`**.
  - An immutable transition record is appended to PostgreSQL `audit_logs`.

---

### Step 10: Execute Safe Demonstration Simulation & Audit Confirmation
- Click **`[ ⚡ EXECUTE SAFE SIMULATION ]`**.
- **What happens:**
  - State transitions to `EXECUTED — SIMULATION`.
  - Execution confirmation displays:
    - `✓ Approved by human • ✓ Safe simulation executed • ✓ Audit recorded`
    - `"0 live Razorpay payments modified."`
    - `"Simulated traffic diversion away from degraded node Gateway_X. Zero live banking records modified."`
- **Narrative:** *"The entire remediation lifecycle is proven, authorized, safely simulated, and permanently audited in PostgreSQL."*
