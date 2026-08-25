# MoneyOps AI — Action Governor & Permission Policies

The **Action Governor** enforces deterministic safeguards preventing AI agents from autonomously mutating financial state without policy verification and human oversight.

---

## 1. Three-Tier Policy Classification

| Tier | Policy Name | Permission Level | Approval Required | Example Actions |
| :--- | :--- | :--- | :---: | :--- |
| **GREEN** | Observe | Autonomous Read-Only | No | Telemetry logging, forensic snapshot, health check |
| **YELLOW** | Recommend | Advisory & Non-Destructive | Yes / Conditional | Merchant advisory notice, temporary velocity throttle |
| **RED** | Execute | Destructive / State-Mutating | **Strict Yes** | `pause_gateway_refund_retries`, `freeze_duplicate_refund_workflow`, `trigger_manual_settlement_reconciliation` |

---

## 2. Human-in-the-Loop Workflow

```text
  AI Investigation Report
            │ (Proposes Action: "pause_gateway_refund_retries")
            ▼
     [ Action Governor ]
            │ (Enforces RED_EXECUTE Policy)
            ▼
  [ Approval Request Modal ]
            │
      ┌─────┴─────┐
      ▼           ▼
  [ APPROVE ]  [ REJECT ]
      │           │
      ▼           ▼
  Execute     Simulate Rejection
  Simulation  & Close Case
      │           │
      └─────┬─────┘
            ▼
  [ Write to SQLite audit_logs ]
            │
            ▼
  [ Immutable Audit Record: ACT-5B0A49B6 ]
```

---

## 3. Immutable Audit Trail Fields

Every executed or rejected action creates a permanent record in `audit_logs`:
- `audit_id`: Unique identifier (e.g. `ACT-5B0A49B6`).
- `investigation_id` & `incident_id`: Direct relational link to the trigger incident.
- `actor`: Authorizing operator name (e.g. `Diwakar_Kaushik (Lead FinOps)`).
- `evidence_summary`: Snapshot of forensic evidence used during decision.
- `tools_called`: List of tools executed by the AI agent.
- `anomaly_score` & `ai_confidence`: Quantitative model signals.
- `simulated_action_result`: Outcome narrative.
- `financial_exposure`: Quantified exposure protected.
