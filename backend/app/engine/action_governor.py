import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.engine.database import get_db_connection

class ActionGovernor:
    """
    Centralized Action Governor for MoneyOps AI.
    Enforces risk-tiered human-in-the-loop approval, state machine validation,
    safe simulation execution, and immutable append-only audit logging in PostgreSQL.
    """

    # Policy Classification
    RISK_POLICY = {
        "reroute_gateway_traffic": {
            "risk_level": "RED",
            "description": "Reroutes live payment checkout traffic away from degraded banking node to backup partner nodes.",
            "requires_human_approval": True,
            "policy_reason": "Altering live banking gateway routing affects checkout conversion and partner SLAs."
        },
        "pause_merchant_settlements": {
            "risk_level": "RED",
            "description": "Places temporary freeze on merchant settlement payouts pending fraud review.",
            "requires_human_approval": True,
            "policy_reason": "Financial hold on merchant receivables has legal, operational, and cashflow impact."
        },
        "enable_enhanced_webhook_monitoring": {
            "risk_level": "YELLOW",
            "description": "Increases retry thresholds and polling frequency for merchant webhook notifications.",
            "requires_human_approval": True,
            "policy_reason": "Operational change impacting internal service compute and rate limits."
        },
        "ping_gateway_diagnostics": {
            "risk_level": "GREEN",
            "description": "Executes read-only healthcheck probing against banking partner endpoints.",
            "requires_human_approval": False,
            "policy_reason": "Non-destructive read-only diagnostic probing."
        }
    }

    @classmethod
    def get_risk_policy(cls, action_type: str) -> Dict[str, Any]:
        """Returns risk level and policy constraints for an action type."""
        return cls.RISK_POLICY.get(action_type, {
            "risk_level": "RED",
            "description": "Custom operational action.",
            "requires_human_approval": True,
            "policy_reason": "Unclassified operations action defaults to highest safety tier (RED)."
        })

    @classmethod
    def propose_action(
        cls,
        incident_id: str,
        investigation_id: Optional[str],
        action_type: str,
        target_entity: str,
        reason: str,
        evidence: Optional[List[Dict[str, Any]]] = None,
        actor: str = "Gemini_Agent"
    ) -> Dict[str, Any]:
        """
        Creates a proposed governed action in pending_approval state and writes to audit_logs.
        """
        conn = get_db_connection()
        c = conn.cursor()

        # 1. Verify Incident Exists
        c.execute("SELECT incident_id FROM incidents WHERE incident_id = %s;", (incident_id,))
        if not c.fetchone():
            c.close()
            conn.close()
            raise ValueError(f"Incident '{incident_id}' not found")

        # 2. Evaluate Policy
        policy = cls.get_risk_policy(action_type)
        risk_level = policy["risk_level"]
        action_id = f"act_{uuid.uuid4().hex[:10]}"
        now_str = datetime.utcnow().isoformat()
        evidence_json = json.dumps(evidence or [], default=str)

        # 3. Persist Governed Action
        c.execute("""
            INSERT INTO governed_actions (
                action_id, incident_id, investigation_id, action_type,
                target_entity, risk_level, status, reason, evidence_json, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, 'pending_approval', %s, %s, %s);
        """, (
            action_id, incident_id, investigation_id, action_type,
            target_entity, risk_level, reason, evidence_json, now_str
        ))

        # 4. Immutable Append-Only Audit Log
        audit_id = f"aud_{uuid.uuid4().hex[:10]}"
        c.execute("""
            INSERT INTO audit_logs (
                audit_id, action_id, incident_id, investigation_id, action_type,
                action_name, action_tier, approval_status,
                previous_status, new_status, actor, reason, evidence_json, timestamp
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending_approval', NULL, 'pending_approval', %s, %s, %s, %s);
        """, (
            audit_id, action_id, incident_id, investigation_id, action_type,
            action_type, risk_level,
            actor, f"Proposed {action_type} for {target_entity}: {reason}", evidence_json, now_str
        ))

        conn.commit()
        c.close()
        conn.close()

        return {
            "action_id": action_id,
            "incident_id": incident_id,
            "investigation_id": investigation_id,
            "action_type": action_type,
            "target_entity": target_entity,
            "risk_level": risk_level,
            "status": "pending_approval",
            "reason": reason,
            "policy": policy,
            "created_at": now_str
        }

    @classmethod
    def approve_action(
        cls,
        action_id: str,
        actor: str = "Operator",
        operator_notes: str = "Human authorization granted per FinOps Policy"
    ) -> Dict[str, Any]:
        """
        Transitions a pending action to approved state with human authorization.
        """
        conn = get_db_connection()
        c = conn.cursor()

        c.execute("SELECT * FROM governed_actions WHERE action_id = %s;", (action_id,))
        action = c.fetchone()
        if not action:
            c.close()
            conn.close()
            raise ValueError(f"Governed action '{action_id}' not found")

        curr_status = action["status"]
        if curr_status == "approved":
            c.close()
            conn.close()
            return dict(action)

        if curr_status != "pending_approval":
            c.close()
            conn.close()
            raise ValueError(f"Cannot approve action in '{curr_status}' state (only 'pending_approval' can be approved)")

        now_str = datetime.utcnow().isoformat()

        # Update action
        c.execute("""
            UPDATE governed_actions SET
                status = 'approved',
                approved_by = %s,
                approved_at = %s
            WHERE action_id = %s;
        """, (actor, now_str, action_id))

        # Append to audit log
        audit_id = f"aud_{uuid.uuid4().hex[:10]}"
        c.execute("""
            INSERT INTO audit_logs (
                audit_id, action_id, incident_id, investigation_id, action_type,
                action_name, action_tier, approval_status,
                previous_status, new_status, actor, reason, timestamp
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'approved', 'pending_approval', 'approved', %s, %s, %s);
        """, (
            audit_id, action_id, action["incident_id"], action["investigation_id"],
            action["action_type"], action["action_type"], action["risk_level"],
            actor, operator_notes, now_str
        ))

        conn.commit()

        c.execute("SELECT * FROM governed_actions WHERE action_id = %s;", (action_id,))
        updated = dict(c.fetchone())
        c.close()
        conn.close()
        return updated

    @classmethod
    def reject_action(
        cls,
        action_id: str,
        actor: str = "Operator",
        reason: str = "Human rejected recommendation"
    ) -> Dict[str, Any]:
        """
        Transitions a pending action to rejected state.
        """
        conn = get_db_connection()
        c = conn.cursor()

        c.execute("SELECT * FROM governed_actions WHERE action_id = %s;", (action_id,))
        action = c.fetchone()
        if not action:
            c.close()
            conn.close()
            raise ValueError(f"Governed action '{action_id}' not found")

        curr_status = action["status"]
        if curr_status == "rejected":
            c.close()
            conn.close()
            return dict(action)

        if curr_status not in ["pending_approval", "approved"]:
            c.close()
            conn.close()
            raise ValueError(f"Cannot reject action in '{curr_status}' state")

        now_str = datetime.utcnow().isoformat()

        # Update action
        c.execute("""
            UPDATE governed_actions SET
                status = 'rejected'
            WHERE action_id = %s;
        """, (action_id,))

        # Append to audit log
        audit_id = f"aud_{uuid.uuid4().hex[:10]}"
        c.execute("""
            INSERT INTO audit_logs (
                audit_id, action_id, incident_id, investigation_id, action_type,
                action_name, action_tier, approval_status,
                previous_status, new_status, actor, reason, timestamp
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'rejected', %s, 'rejected', %s, %s, %s);
        """, (
            audit_id, action_id, action["incident_id"], action["investigation_id"],
            action["action_type"], action["action_type"], action["risk_level"],
            curr_status, actor, reason, now_str
        ))

        conn.commit()

        c.execute("SELECT * FROM governed_actions WHERE action_id = %s;", (action_id,))
        updated = dict(c.fetchone())
        c.close()
        conn.close()
        return updated

    @classmethod
    def execute_action(
        cls,
        action_id: str,
        actor: str = "Operator"
    ) -> Dict[str, Any]:
        """
        Executes a safe demonstration simulation for an approved action.
        Blocks unapproved, rejected, or duplicate executions.
        """
        conn = get_db_connection()
        c = conn.cursor()

        c.execute("SELECT * FROM governed_actions WHERE action_id = %s;", (action_id,))
        action = c.fetchone()
        if not action:
            c.close()
            conn.close()
            raise ValueError(f"Governed action '{action_id}' not found")

        curr_status = action["status"]
        if curr_status == "executed":
            c.close()
            conn.close()
            raise ValueError(f"Action '{action_id}' has already been executed (duplicate execution blocked)")

        if curr_status == "rejected":
            c.close()
            conn.close()
            raise ValueError(f"Cannot execute rejected action '{action_id}'")

        if curr_status == "pending_approval" and action["risk_level"] in ["RED", "YELLOW"]:
            c.close()
            conn.close()
            raise ValueError(f"Action '{action_id}' requires explicit human approval before execution (Risk Level: {action['risk_level']})")

        # Execute Safe Demonstration Simulation
        action_type = action["action_type"]
        target = action["target_entity"]
        now_str = datetime.utcnow().isoformat()

        if action_type == "reroute_gateway_traffic":
            simulation_result = {
                "execution_mode": "SIMULATION",
                "action": "reroute_gateway_traffic",
                "target_node": target,
                "backup_nodes_activated": ["Gateway_SBI", "Gateway_ICICI", "Gateway_HDFC"],
                "traffic_split_pct": {"Gateway_SBI": 35, "Gateway_ICICI": 35, "Gateway_HDFC": 30},
                "status": "simulated_success",
                "real_razorpay_payments_modified": 0,
                "message": f"Simulated traffic diversion away from degraded node {target}. Zero live banking records modified."
            }
        elif action_type == "pause_merchant_settlements":
            simulation_result = {
                "execution_mode": "SIMULATION",
                "action": "pause_merchant_settlements",
                "target_merchant": target,
                "status": "simulated_success",
                "real_razorpay_settlements_modified": 0,
                "message": f"Simulated settlement hold applied to merchant {target}."
            }
        else:
            simulation_result = {
                "execution_mode": "SIMULATION",
                "action": action_type,
                "target": target,
                "status": "simulated_success",
                "message": f"Safe simulation executed for {action_type} on {target}."
            }

        result_json = json.dumps(simulation_result)

        # Update action
        c.execute("""
            UPDATE governed_actions SET
                status = 'executed',
                executed_at = %s,
                execution_result_json = %s
            WHERE action_id = %s;
        """, (now_str, result_json, action_id))

        # Append to audit log
        audit_id = f"aud_{uuid.uuid4().hex[:10]}"
        c.execute("""
            INSERT INTO audit_logs (
                audit_id, action_id, incident_id, investigation_id, action_type,
                action_name, action_tier, approval_status,
                previous_status, new_status, actor, reason, execution_result_json, timestamp
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'executed', %s, 'executed', %s, %s, %s, %s);
        """, (
            audit_id, action_id, action["incident_id"], action["investigation_id"],
            action["action_type"], action["action_type"], action["risk_level"],
            curr_status, actor, "Executed safe demonstration simulation",
            result_json, now_str
        ))

        conn.commit()

        c.execute("SELECT * FROM governed_actions WHERE action_id = %s;", (action_id,))
        updated = dict(c.fetchone())
        if updated.get("execution_result_json"):
            try:
                updated["execution_result"] = json.loads(updated["execution_result_json"])
            except Exception:
                pass
        c.close()
        conn.close()

        return updated

    @classmethod
    def get_action(cls, action_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a governed action by ID."""
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM governed_actions WHERE action_id = %s;", (action_id,))
        row = c.fetchone()
        c.close()
        conn.close()
        if not row:
            return None
        d = dict(row)
        if d.get("evidence_json"):
            try:
                d["evidence"] = json.loads(d["evidence_json"])
            except Exception:
                pass
        if d.get("execution_result_json"):
            try:
                d["execution_result"] = json.loads(d["execution_result_json"])
            except Exception:
                pass
        return d

    @classmethod
    def list_incident_actions(cls, incident_id: str) -> List[Dict[str, Any]]:
        """Lists all governed actions proposed for an incident."""
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM governed_actions WHERE incident_id = %s ORDER BY created_at DESC;", (incident_id,))
        rows = c.fetchall()
        c.close()
        conn.close()

        results = []
        for r in rows:
            d = dict(r)
            if d.get("evidence_json"):
                try:
                    d["evidence"] = json.loads(d["evidence_json"])
                except Exception:
                    pass
            if d.get("execution_result_json"):
                try:
                    d["execution_result"] = json.loads(d["execution_result_json"])
                except Exception:
                    pass
            results.append(d)
        return results

    @classmethod
    def list_audit_logs(cls, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves immutable append-only audit trail logs from PostgreSQL."""
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT %s;", (limit,))
        rows = c.fetchall()
        c.close()
        conn.close()

        results = []
        for r in rows:
            d = dict(r)
            if d.get("evidence_json"):
                try:
                    d["evidence"] = json.loads(d["evidence_json"])
                except Exception:
                    pass
            if d.get("execution_result_json"):
                try:
                    d["execution_result"] = json.loads(d["execution_result_json"])
                except Exception:
                    pass
            results.append(d)
        return results

action_governor = ActionGovernor()
