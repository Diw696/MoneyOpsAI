import pytest
import uuid
import json
from fastapi.testclient import TestClient
from app.main import app
from app.engine.database import get_db_connection
from app.engine.action_governor import action_governor

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_test_incident():
    """Ensures a valid incident exists for action tests."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO incidents (
            incident_id, title, type, severity, status, description, affected_merchants,
            potential_exposure, anomaly_score, detected_at, target_entity_type, target_entity_id
        ) VALUES (
            'INC-TEST-ACT', 'Test Incident for Action Governor', 'gateway_failure_spike',
            'critical', 'open', 'Test Description', 5, 50000.0, 0.85, NOW(), 'gateway', 'Gateway_X'
        ) ON CONFLICT (incident_id) DO NOTHING;
    """)
    conn.commit()
    c.close()
    conn.close()

def test_risk_classification_policy():
    """Verifies that ActionGovernor correctly evaluates risk tiers per policy."""
    policy_red = action_governor.get_risk_policy("reroute_gateway_traffic")
    assert policy_red["risk_level"] == "RED"
    assert policy_red["requires_human_approval"] is True

    policy_settlement = action_governor.get_risk_policy("pause_merchant_settlements")
    assert policy_settlement["risk_level"] == "RED"

    policy_yellow = action_governor.get_risk_policy("enable_enhanced_webhook_monitoring")
    assert policy_yellow["risk_level"] == "YELLOW"

    policy_green = action_governor.get_risk_policy("ping_gateway_diagnostics")
    assert policy_green["risk_level"] == "GREEN"
    assert policy_green["requires_human_approval"] is False

def test_propose_action_creates_pending_state_and_audit_record():
    """Verifies that proposing an action creates a pending_approval record and an audit log."""
    res = action_governor.propose_action(
        incident_id="INC-TEST-ACT",
        investigation_id="inv_test_123",
        action_type="reroute_gateway_traffic",
        target_entity="Gateway_X",
        reason="19.08% failure spike on Gateway_X",
        evidence=[{"metric": "failure_rate", "value": 19.08}],
        actor="Gemini_Agent"
    )

    action_id = res["action_id"]
    assert res["status"] == "pending_approval"
    assert res["risk_level"] == "RED"

    # Verify in PostgreSQL
    action = action_governor.get_action(action_id)
    assert action is not None
    assert action["status"] == "pending_approval"
    assert action["target_entity"] == "Gateway_X"

    # Verify Audit Log
    logs = action_governor.list_audit_logs(limit=10)
    creation_log = next((l for l in logs if l.get("action_id") == action_id and l.get("new_status") == "pending_approval"), None)
    assert creation_log is not None
    assert creation_log["actor"] == "Gemini_Agent"

def test_cannot_execute_pending_action_without_approval():
    """Verifies that executing a pending RED/YELLOW action without approval is strictly blocked."""
    res = action_governor.propose_action(
        incident_id="INC-TEST-ACT",
        investigation_id="inv_test_123",
        action_type="reroute_gateway_traffic",
        target_entity="Gateway_X",
        reason="Test execution block",
        actor="Gemini_Agent"
    )
    action_id = res["action_id"]

    with pytest.raises(ValueError, match="requires explicit human approval"):
        action_governor.execute_action(action_id, actor="Unauthorized_Script")

def test_human_approval_and_safe_simulation_execution():
    """Verifies the complete approve -> execute safe simulation -> audit trail flow."""
    res = action_governor.propose_action(
        incident_id="INC-TEST-ACT",
        investigation_id="inv_test_123",
        action_type="reroute_gateway_traffic",
        target_entity="Gateway_X",
        reason="Reroute traffic to backup banking nodes",
        actor="Gemini_Agent"
    )
    action_id = res["action_id"]

    # 1. Human Approval
    app_res = action_governor.approve_action(action_id, actor="Lead_FinOps_Operator", operator_notes="Approved for SBI/ICICI cutover")
    assert app_res["status"] == "approved"
    assert app_res["approved_by"] == "Lead_FinOps_Operator"
    assert app_res["approved_at"] is not None

    # 2. Execute Safe Simulation
    exec_res = action_governor.execute_action(action_id, actor="Lead_FinOps_Operator")
    assert exec_res["status"] == "executed"
    assert exec_res["executed_at"] is not None
    
    sim_data = exec_res.get("execution_result", {})
    assert sim_data.get("execution_mode") == "SIMULATION"
    assert sim_data.get("real_razorpay_payments_modified") == 0
    assert "Gateway_SBI" in sim_data.get("backup_nodes_activated", [])

    # 3. Duplicate Execution Blocked
    with pytest.raises(ValueError, match="already been executed"):
        action_governor.execute_action(action_id, actor="Lead_FinOps_Operator")

    # 4. Cannot approve already executed action
    with pytest.raises(ValueError, match="Cannot approve action in 'executed' state"):
        action_governor.approve_action(action_id, actor="Another_Operator")

def test_rejection_workflow():
    """Verifies that rejecting an action transitions to rejected and prevents execution."""
    res = action_governor.propose_action(
        incident_id="INC-TEST-ACT",
        investigation_id="inv_test_123",
        action_type="pause_merchant_settlements",
        target_entity="merch_Nova_Store",
        reason="Suspicious refund frequency",
        actor="Gemini_Agent"
    )
    action_id = res["action_id"]

    # Reject action
    rej_res = action_governor.reject_action(action_id, actor="Risk_Manager", reason="Merchant confirmed legitimate high-volume promo")
    assert rej_res["status"] == "rejected"

    # Verify execution is blocked
    with pytest.raises(ValueError, match="Cannot execute rejected action"):
        action_governor.execute_action(action_id, actor="Risk_Manager")

    # Verify approval is blocked
    with pytest.raises(ValueError, match="Cannot approve action in 'rejected' state"):
        action_governor.approve_action(action_id, actor="Risk_Manager")

def test_action_api_endpoints_full_lifecycle():
    """Verifies all Phase D REST API endpoints."""
    # 1. Propose via API
    prop_resp = client.post("/api/actions/propose", json={
        "incident_id": "INC-TEST-ACT",
        "investigation_id": "inv_test_api",
        "action_type": "reroute_gateway_traffic",
        "target_entity": "Gateway_X",
        "reason": "API proposal test",
        "actor": "Gemini_Agent"
    })
    assert prop_resp.status_code == 200
    action_data = prop_resp.json()
    action_id = action_data["action_id"]
    assert action_data["status"] == "pending_approval"

    # 2. Attempt Execution before approval -> Expect 400
    exec_fail_resp = client.post(f"/api/actions/{action_id}/execute", json={"actor": "Operator"})
    assert exec_fail_resp.status_code == 400
    assert "requires explicit human approval" in exec_fail_resp.json()["detail"]

    # 3. Approve via API
    app_resp = client.post(f"/api/actions/{action_id}/approve", json={
        "actor": "Operator_Sarah",
        "operator_notes": "Approved via Operations UI"
    })
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "approved"

    # 4. Execute via API
    exec_resp = client.post(f"/api/actions/{action_id}/execute", json={"actor": "Operator_Sarah"})
    assert exec_resp.status_code == 200
    exec_body = exec_resp.json()
    assert exec_body["status"] == "executed"
    assert exec_body["execution_result"]["execution_mode"] == "SIMULATION"

    # 5. Get Action by ID
    get_resp = client.get(f"/api/actions/{action_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "executed"

    # 6. List Actions for Incident
    inc_acts_resp = client.get("/api/incidents/INC-TEST-ACT/actions")
    assert inc_acts_resp.status_code == 200
    assert len(inc_acts_resp.json()) >= 1

    # 7. Audit Logs Endpoint
    audit_resp = client.get("/api/audit-logs")
    assert audit_resp.status_code == 200
    assert len(audit_resp.json()) >= 1

def test_invalid_action_id_returns_404():
    """Verifies that querying a nonexistent action returns 404."""
    resp = client.get("/api/actions/act_nonexistent_9999")
    assert resp.status_code == 404
