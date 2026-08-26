# MONEYOPS AI V2 — PROJECT ARCHITECTURE & INTERVIEW EXPLANATION

> **Executive Pitch:**  
> *"MoneyOps AI V2 transforms payment operations from reactive, threshold-based alerts into an autonomous, evidence-backed AI investigation and governed remediation platform. Built on PostgreSQL 18, Scikit-Learn IsolationForest, Google Gemini tool calling, and an immutable Action Governor."*

---

## 1. The Core Problem: Why Traditional Payment Monitoring Fails

In modern payment platforms like Razorpay, Stripe, or Adyen, payment operations teams face three critical challenges:

1. **Static Threshold Alert Fatigue:**
   - Traditional APM tools use static alert thresholds (e.g., *"trigger alert if failure rate > 5%"*).
   - In high-volume e-commerce (e.g., flash sales or peak hours), normal baseline variance triggers hundreds of false alarms, while insidious node-specific degradation gets buried.

2. **The "Investigation Bottleneck" (MTTI):**
   - When a payment failure spike occurs, engineers spend 30–90 minutes manually writing SQL queries across payments, orders, refunds, gateway logs, and webhook delivery tables to answer:
     - *Which gateway or bank node is failing?*
     - *Which failure codes dominate (`GATEWAY_TIMEOUT` vs `INSUFFICIENT_FUNDS`)?*
     - *Which merchants are affected, and what is the exact revenue exposure?*

3. **The AI Autonomy Trap (Uncontrolled Execution):**
   - Giving an LLM direct API write access to production payment gateways to execute automated refunds or traffic routing is unacceptable due to hallucination risks, financial liability, and compliance regulations (RBI, PCI-DSS).

---

## 2. The MoneyOps AI V2 Solution: 7 Core Engineering Principles

| Traditional Payment Dashboard | MoneyOps AI V2 |
| :--- | :--- |
| **Static Thresholds** (Alert if failure rate > X%) | **Unsupervised Isolation Forest** discovering statistical anomalies across multi-dimensional feature matrices. |
| **Manual SQL Forensics** (Engineers querying DBs manually) | **Autonomous Gemini Agent** dynamically choosing and executing parameterized forensic tools against PostgreSQL. |
| **Hallucinatory AI Output** (Unverifiable chatbot responses) | **Auditable Tool Trace** recording every tool call, query arguments, raw DB responses, and millisecond latencies. |
| **Direct / Unsafe Automation** (Risk of destructive actions) | **Centralized Action Governor** enforcing a strict 3-tier risk policy (`GREEN`, `YELLOW`, `RED`). |
| **Zero Authorization Flow** | **Mandatory Human-in-the-Loop** approval with immutable append-only audit trail in PostgreSQL. |
| **Simulated Data Disguised as Real** | **Strict Provenance Tagging** (`source: razorpay_test`, `razorpay_webhook`, `incident_lab`). |
| **Information Overload** (Dozens of decorative charts) | **Minimalist 3-View Control Center** answering *What Happened?*, *Why?*, and *What Should We Do?* in 10 seconds. |

---

## 3. Technical Deep Dive: Key Components

### A. Data Ingestion & Canonical Pipeline
- **Unified Event Abstraction:** Razorpay REST API responses, live HMAC-SHA256 webhooks, and Incident Lab simulations are converted into typed `CanonicalEvent` models.
- **Financial Precision:** Currency values are stored as decimal numeric representations in INR, avoiding floating-point rounding inaccuracies.
- **Relational Invariants:** PostgreSQL enforces foreign key hierarchies (`merchants` $\to$ `orders` $\to$ `payments` $\to$ `refunds`).

### B. Unsupervised Anomaly Detection (Scikit-Learn IsolationForest)
- **Mathematical Principle:** Isolation Forests isolate anomalies by randomly selecting a feature and randomly splitting the value between the maximum and minimum values of the feature. Anomalous points require fewer splits to isolate than normal points.
- **Feature Matrix:**
  $$\vec{x} = \begin{bmatrix} \text{failure\_rate} & \text{peer\_ratio} & \text{total\_volume} & \text{top\_error\_share} & \text{financial\_exposure} \end{bmatrix}$$
- **Demonstrated Discovery:** Out of 5 gateways, `Gateway_X` was flagged with a negative anomaly score because its 19.08% failure rate was 5.42x the peer baseline of 3.52%, generating incident `INC-0001`.

### C. Generative AI Multi-Turn Tool Calling (Google Gemini)
- **Autonomous Reasoning Loop:**
  ```text
  Incident INC-0001
         ↓
  Gemini analyzes anomaly parameters
         ↓
  Calls get_incident() -> Fetches incident metadata
         ↓
  Calls get_gateway_metrics() -> Discovers 19.08% failure rate & 85.06% GATEWAY_TIMEOUT share
         ↓
  Calls get_failed_payments() -> Samples actual error codes and timestamps
         ↓
  Calls get_affected_merchants() -> Calculates multi-merchant financial exposure
         ↓
  Synthesizes Evidence-Backed Root Cause Report & Policy Recommendation
  ```
- **Zero Fabrication:** The agent operates strictly over data returned by SQL tools. When API keys are missing, the system outputs an explicit `AI_NOT_CONFIGURED` status rather than synthetic fake reports.

### D. Centralized Action Governor & Human-in-the-Loop Safety
- **Policy Engine:**
  - `reroute_gateway_traffic` $\to$ **`RED`** (Altering live payment checkout traffic affects checkout conversion and partner SLAs).
  - `pause_merchant_settlements` $\to$ **`RED`** (Holding financial settlements requires lead FinOps sign-off).
  - `enable_enhanced_webhook_monitoring` $\to$ **`YELLOW`** (Read-only rate increase).
  - `ping_gateway_diagnostics` $\to$ **`GREEN`** (Non-destructive health check).
- **Execution Invariant:** An unapproved action cannot execute under any circumstance (HTTP 400 rejection). Safe demonstration simulations explicitly confirm `real_razorpay_payments_modified: 0`.

---

## 4. Key Metrics & Achievements

- **Automated Test Suite:** 39/39 tests passing (100% pass rate) across unit, integration, ML, AI tool calling, and REST API layers.
- **Frontend Performance:** Clean production bundle built in 149ms with Vite and React 18.
- **Real Database Scale:** Over 2,500 active financial records persisted in PostgreSQL 18.
- **AI Latency:** Complete 4-turn forensic investigation executed in under 2 seconds.
