# MoneyOps AI ⚡ (V2)

### *Autonomous AI Financial Incident Investigator & Governed Remediation Platform*

> **Tagline:** *"When digital payment transactions fail, MoneyOps discovers why, investigates the database, and governs the response."*

Built for high-throughput payment gateway operations (Razorpay Test Mode / FinOps Payment Ops).

---

## 📌 Executive Summary

Modern payment operations teams at gateways and merchants process millions of financial events across **Merchants**, **Orders**, **Payments**, **Refunds**, and **Webhooks**. When upstream banking nodes degrade or timeout spikes occur, static threshold alerts trigger alert fatigue without explaining the root cause.

**MoneyOps AI V2** is an autonomous FinOps incident control platform built on top of **PostgreSQL 18**, **Scikit-Learn IsolationForest**, **Google Gemini Multi-Turn Tool Calling**, and a **Centralized Action Governor**:

```text
REAL RAZORPAY TEST MODE & INCIDENT LAB
                  │
                  ▼
   UNIFIED CANONICAL INGESTION PIPELINE (CanonicalEvent)
                  │
                  ▼
     POSTGRESQL 18 PRIMARY DATABASE (moneyops_v2)
                  │
                  ▼
   UNSUPERVISED ISOLATION FOREST ANOMALY DETECTION
                  │
                  ▼
         INCIDENT: INC-0001
                  │
                  ▼
 AUTONOMOUS GEMINI INVESTIGATION AGENT (SQL Tools)
                  │
                  ▼
    EVIDENCE-BACKED ROOT CAUSE & RECOMMENDATION
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│        ACTION GOVERNOR & HUMAN-IN-THE-LOOP              │
│                                                         │
│ Policy: RISK = RED (Routing Change)                     │
│ Unapproved Execution: ❌ BLOCKED (HTTP 400)             │
│ Human Operator:       ✅ AUTHORIZED                     │
│ Simulation Execution: ⚡ EXECUTED (0 real txs modified) │
└─────────────────────────────────────────────────────────┘
                  │
                  ▼
   IMMUTABLE APPEND-ONLY AUDIT TRAIL (audit_logs)
                  │
                  ▼
     MINIMALIST 3-VIEW CONTROL CENTER (React 18)
          [ OVERVIEW ]  [ DATA ]  [ INVESTIGATION ]
```

---

## 🏛️ Core Engineering Pillars

1. **Production PostgreSQL 18 Architecture:**
   - 10 structured tables (`merchants`, `orders`, `payments`, `refunds`, `webhook_events`, `incidents`, `ai_investigations`, `ai_investigation_steps`, `governed_actions`, `audit_logs`).
   - Decimal numeric financial precision (avoiding floating-point arithmetic errors).
2. **Unified Ingestion & Explicit Provenance:**
   - Single ingestion path for live Razorpay Test Mode REST calls, HMAC-SHA256 webhooks, and Incident Lab multi-merchant simulations.
   - Explicit provenance tags: `source: 'razorpay_test'`, `source: 'razorpay_webhook'`, and `source: 'incident_lab'`.
3. **Unsupervised ML Anomaly Discovery:**
   - Dynamic feature extraction calculating gateway failure rates, peer baselines, error concentrations, and financial exposures.
   - Scikit-Learn `IsolationForest` flags genuine anomalies (e.g. `Gateway_X` 19.08% failure rate vs 3.52% baseline, 5.42x deviation) with zero hardcoded scenario knowledge.
4. **Real AI Investigation with Google Gemini:**
   - Multi-turn tool-calling loop where Gemini queries PostgreSQL directly using 7 forensic SQL tools (`get_incident`, `get_gateway_metrics`, `get_failed_payments`, `get_affected_merchants`, `get_payment_context`, `get_webhook_activity`, `find_similar_incidents`).
   - Records every tool turn (arguments, raw database results, latency) into `ai_investigation_steps`.
5. **Action Governor & Human-in-the-Loop Safety:**
   - 3-tier risk classification policy (`GREEN`, `YELLOW`, `RED`).
   - High-stakes operations (`reroute_gateway_traffic`, `pause_settlements`) strictly require human operator authorization.
   - Safe demonstration simulations guarantee `real_razorpay_payments_modified: 0`.
6. **Immutable Append-Only Audit Trail:**
   - Every state transition (`proposed` $\to$ `approved` $\to$ `executed`) appends an immutable row to PostgreSQL `audit_logs`.
7. **Minimalist 3-View UX:**
   - **Overview:** 4 Key Metrics + Active Incident Queue.
   - **Data:** Explicit Real vs Simulation Provenance Breakdown + Tabbed Entity Ledgers.
   - **Investigation:** Structured telemetry (*What Happened?*, *Why?*, 4 Evidence Cards, Gemini Recommendation, Action Governor, Collapsible AI Tool Trace).

---

## 🛠️ Quick Start & Running Locally

### 1. Prerequisites
- **Python 3.11+**
- **Node.js 18+**
- **PostgreSQL 18** running on `127.0.0.1:5432`

### 2. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Ensure `.env` contains your PostgreSQL credentials and optional API keys:
```ini
DATABASE_URL=postgresql://postgres:password@127.0.0.1:5432/moneyops_v2
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
```

### 3. Backend Setup & Test Suite
```powershell
# Activate Python Virtual Environment
.\venv\Scripts\Activate.ps1

# Run the 39 Automated Backend Tests
$env:PYTHONPATH="backend"
python -m pytest backend/tests/ -v
```

### 4. Start Backend Server
```powershell
$env:PYTHONPATH="backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 5. Start Frontend Control Center
```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```
Open **`http://127.0.0.1:5173`** in your browser.

---

## 🧪 Comprehensive Verification & Test Results

### 1. Automated Test Suite (39/39 Passing)
Command: `pytest backend/tests/ -v`
```text
============================= test session starts =============================
collected 39 items

backend/tests/test_action_governor.py (7 tests) ................. PASSED [ 17%]
backend/tests/test_anomaly_detector.py (5 tests) ................ PASSED [ 30%]
backend/tests/test_gemini_agent.py (12 tests) ................... PASSED [ 61%]
backend/tests/test_pipeline.py (4 tests) ........................ PASSED [ 71%]
backend/tests/test_razorpay_sync.py (4 tests) ................... PASSED [ 82%]
backend/tests/test_webhooks.py (7 tests) ........................ PASSED [100%]

============================= 39 passed in 13.77s =============================
```

### 2. Frontend Production Build
Command: `npm run build` in `frontend/`
```text
✓ 21 modules transformed.
dist/index.html                   0.50 kB │ gzip:  0.33 kB
dist/assets/index-dCc8LGxO.css    4.07 kB │ gzip:  1.55 kB
dist/assets/index-Lh7Afyqu.js   241.64 kB │ gzip: 69.47 kB
✓ built in 149ms
```

---

## 📁 Repository Structure

```text
MoneyOpsAI/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py              # FastAPI REST Endpoints
│   │   ├── core/
│   │   │   └── config.py              # Pydantic Settings & Env Vars
│   │   ├── engine/
│   │   │   ├── action_governor.py     # 3-Tier Risk Policy & Safe Executor
│   │   │   ├── anomaly_detector.py    # Scikit-Learn IsolationForest Anomaly Engine
│   │   │   ├── database.py            # PostgreSQL Schema & Connection Pool
│   │   │   ├── gemini_agent.py        # Autonomous Multi-Turn Tool-Calling Agent
│   │   │   ├── incident_lab.py        # Reproducible Multi-Merchant Generator
│   │   │   ├── investigation_tools.py # 7 SQL Forensic Investigation Tools
│   │   │   ├── pipeline.py            # Canonical Ingestion Pipeline
│   │   │   └── webhook_service.py     # HMAC-SHA256 Webhook Processor
│   │   └── integrations/
│   │       └── razorpay/              # Official Razorpay REST & Webhook Adapters
│   └── tests/                         # 39 Comprehensive Pytest Tests
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.jsx             # 3-Tab Navigation & Live Status Badges
│   │   │   ├── OverviewView.jsx       # 4 Core Metrics & Active Incident Queue
│   │   │   ├── DataView.jsx           # Real vs Simulation Provenance & Ledgers
│   │   │   └── InvestigationView.jsx  # Structured Forensic Telemetry & Action Governor
│   │   ├── api.js                     # Centralized Fetch API Client
│   │   ├── App.jsx                    # Root Application Container & Tab Router
│   │   └── index.css                  # Dark Mode Design Tokens
│   └── package.json                   # React 18 + Vite Bundler
├── docs/
│   ├── ARCHITECTURE_DIAGRAM.md        # Complete ASCII / Mermaid Architecture Flow
│   ├── DEMO_WALKTHROUGH.md            # 10-Step Interactive Demonstration Script
│   ├── PROJECT_PRESENTATION_EXPLANATION.md # Technical Deep Dive & Interview Guide
│   └── PHASE_E_UI_AUDIT.md            # UI & Architecture Audit
├── .env.example                       # Clean Template for Configuration
└── README.md                          # Master Project Presentation
```

---

## 📄 License & Attribution

Developed as an advanced engineering submission for the **Razorpay Internship Selection**.  
Author: **Diwakar Kaushik (BTech AI & Data Engineering)**.
