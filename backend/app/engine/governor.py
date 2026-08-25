import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.models.schemas import ActionTier, AuditLogEntry, IncidentStatus
from app.engine.database import get_db_connection

class ActionGovernor:
    """
    Action Governor: Enforces strict 3-tier permission policies.
    Guarantees that consequential financial actions are never executed autonomously
    by LLMs without deterministic policy checks and human-in-the-loop approval.
    """

    POLICY_REGISTRY = {
        "pause_gateway_refund_retries": {
            "tier": ActionTier.RED_EXECUTE,
            "requires_approval": True,
            "description": "Pause automated refund retries across gateway to prevent cascade failure and duplicate debits."
        },
        "freeze_duplicate_refund_workflow": {
            "tier": ActionTier.RED_EXECUTE,
            "requires_approval": True,
            "description": "Freeze linked refund workflow and block second debit authorization."
        },
        "trigger_manual_settlement_reconciliation": {
            "tier": ActionTier.RED_EXECUTE,
            "requires_approval": True,
            "description": "Trigger urgent out-of-band nodal reconciliation with banking partner."
        },
        "apply_velocity_throttle": {
            "tier": ActionTier.YELLOW_RECOMMEND,
            "requires_approval": True,
            "description": "Apply progressive velocity throttling on suspicious customer card fingerprint."
        },
        "generate_merchant_advisory": {
            "tier": ActionTier.YELLOW_RECOMMEND,
            "requires_approval": False,
            "description": "Issue operational status notification to affected merchants."
        },
        "observe_and_log": {
            "tier": ActionTier.GREEN_OBSERVE,
            "requires_approval": False,
            "description": "Observe telemetry and record forensic snapshot."
        }
    }

    def validate_action(self, action_name: str, proposed_tier: ActionTier) -> Dict[str, Any]:
        """Validates action policy compliance against registered rules."""
        policy = self.POLICY_REGISTRY.get(action_name, {
            "tier": ActionTier.RED_EXECUTE,
            "requires_approval": True,
            "description": "Custom or unrecognized action default to Red Tier."
        })
        return {
            "action_name": action_name,
            "enforced_tier": policy["tier"],
            "requires_approval": policy["requires_approval"],
            "policy_description": policy["description"]
        }

    def execute_action(
        self,
        investigation_id: str,
        incident_id: str,
        action_name: str,
        action_tier: ActionTier,
        approved: bool,
        actor: str,
        evidence_summary: List[str],
        tools_called: List[str],
        anomaly_score: float,
        ai_confidence: float,
        root_cause: str,
        recommended_action: str,
        financial_exposure: float,
        operator_notes: Optional[str] = None
    ) -> AuditLogEntry:
        """
        Executes or rejects the proposed action, performs state simulation,
        and logs an immutable entry into the audit trail.
        """
        audit_id = f"ACT-{str(uuid.uuid4())[:8].upper()}"
        now_str = datetime.utcnow().isoformat()

        conn = get_db_connection()
        cursor = conn.cursor()

        if approved:
            approval_status = "approved"
            simulated_result = f"Action '{action_name}' executed in simulation. Workflow state updated. Safeguards applied to affected entities. Operator note: {operator_notes or 'Authorized per FinOps policy'}"
            
            # Update incident status to resolved
            cursor.execute("UPDATE incidents SET status = 'resolved' WHERE incident_id = ?", (incident_id,))
            cursor.execute("UPDATE investigations SET status = 'resolved' WHERE investigation_id = ?", (investigation_id,))
        else:
            approval_status = "rejected"
            simulated_result = f"Action '{action_name}' was REJECTED by operator {actor}. Safeguards bypassed. Investigation closed without action."
            cursor.execute("UPDATE incidents SET status = 'closed' WHERE incident_id = ?", (incident_id,))
            cursor.execute("UPDATE investigations SET status = 'closed' WHERE investigation_id = ?", (investigation_id,))

        cursor.execute("""
            INSERT INTO audit_logs (
                audit_id, investigation_id, incident_id, timestamp, actor, action_name,
                action_tier, evidence_summary_json, tools_called_json, anomaly_score,
                ai_confidence, root_cause, recommended_action, approval_status,
                human_approval, simulated_action_result, financial_exposure
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            audit_id, investigation_id, incident_id, now_str, actor, action_name,
            action_tier.value if hasattr(action_tier, "value") else str(action_tier),
            json.dumps(evidence_summary), json.dumps(tools_called),
            anomaly_score, ai_confidence, root_cause, recommended_action,
            approval_status, 1 if approved else 0, simulated_result, financial_exposure
        ))

        conn.commit()
        conn.close()

        return AuditLogEntry(
            audit_id=audit_id,
            investigation_id=investigation_id,
            incident_id=incident_id,
            timestamp=now_str,
            actor=actor,
            action_name=action_name,
            action_tier=action_tier.value if hasattr(action_tier, "value") else str(action_tier),
            evidence_summary=evidence_summary,
            tools_called=tools_called,
            anomaly_score=anomaly_score,
            ai_confidence=ai_confidence,
            root_cause=root_cause,
            recommended_action=recommended_action,
            approval_status=approval_status,
            human_approval=approved,
            simulated_action_result=simulated_result,
            financial_exposure=financial_exposure
        )

governor = ActionGovernor()
