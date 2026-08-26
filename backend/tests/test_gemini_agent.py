import os
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.engine.database import init_db, get_db_connection
from app.engine.incident_lab import IncidentLabGenerator
from app.engine.anomaly_detector import anomaly_detector
from app.engine.investigation_tools import InvestigationTools, TOOL_REGISTRY
from app.engine.gemini_agent import GeminiInvestigationAgent, gemini_agent

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_dataset():
    """Initializes schema and generates reproducible dataset with INC-0001."""
    init_db()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM audit_logs; DELETE FROM ai_investigation_steps; DELETE FROM ai_investigations; DELETE FROM incidents; DELETE FROM webhook_events; DELETE FROM refunds; DELETE FROM payments; DELETE FROM orders; DELETE FROM merchants;")
    conn.commit()
    c.close()
    conn.close()

    # Generate standard Incident Lab dataset and detect incident
    IncidentLabGenerator.generate_dataset(seed=42, num_payments=500, num_merchants=5, anomaly_type="gateway_spike")
    anomaly_detector.run_detection()

def test_ai_status_endpoint():
    """Verify GET /api/ai/status reports provider without exposing secrets."""
    res = client.get("/api/ai/status")
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "gemini"
    assert "configured" in data
    assert "model" in data
    assert "status" in data
    assert "api_key" not in data

def test_tool_get_incident():
    """Verify get_incident queries real PostgreSQL incident record."""
    res = InvestigationTools.get_incident("INC-0001")
    assert "error" not in res
    assert res["incident_id"] == "INC-0001"
    assert res["target_entity_id"] == "Gateway_X"
    assert res["status"] == "open"
    assert res["potential_exposure"] > 0

def test_tool_get_gateway_metrics():
    """Verify get_gateway_metrics calculates real PostgreSQL failure rate and peer rate."""
    res = InvestigationTools.get_gateway_metrics("Gateway_X")
    assert "error" not in res
    assert res["gateway"] == "Gateway_X"
    assert res["failure_rate_pct"] > 10.0
    assert res["peer_failure_rate_pct"] < 6.0
    assert res["failure_rate_ratio"] > 2.0
    assert len(res["failure_code_breakdown"]) > 0
    assert res["failure_code_breakdown"][0]["failure_code"] == "GATEWAY_TIMEOUT"

def test_tool_get_failed_payments():
    """Verify get_failed_payments returns forensic rows with error codes from PostgreSQL."""
    res = InvestigationTools.get_failed_payments("Gateway_X", limit=10)
    assert "error" not in res
    assert res["gateway"] == "Gateway_X"
    assert res["failed_payments_returned"] > 0
    record = res["sample_records"][0]
    assert record["status"] == "failed"
    assert record["gateway"] == "Gateway_X"
    assert "failure_code" in record

def test_tool_get_affected_merchants():
    """Verify get_affected_merchants aggregates failure impact across merchants in PostgreSQL."""
    res = InvestigationTools.get_affected_merchants("Gateway_X")
    assert "error" not in res
    assert res["gateway"] == "Gateway_X"
    assert res["affected_merchants_count"] > 0
    for m in res["merchants"]:
        assert "merchant_id" in m
        assert "failures" in m
        assert "merchant_exposure_inr" in m

def test_tool_get_payment_context():
    """Verify get_payment_context retrieves relational order-payment-merchant chain."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT payment_id FROM payments LIMIT 1;")
    pid = c.fetchone()["payment_id"]
    c.close()
    conn.close()

    res = InvestigationTools.get_payment_context(pid)
    assert "error" not in res
    assert res["payment"]["payment_id"] == pid
    assert "order" in res
    assert "merchant" in res

def test_tool_get_webhook_activity():
    """Verify get_webhook_activity returns webhook delivery status from PostgreSQL."""
    res = InvestigationTools.get_webhook_activity("Gateway_X", limit=20)
    assert "error" not in res
    assert res["gateway"] == "Gateway_X"
    assert "webhook_events_returned" in res

def test_tool_find_similar_incidents():
    """Verify find_similar_incidents returns historical precedent or clean status."""
    res = InvestigationTools.find_similar_incidents("gateway_failure_spike")
    assert res["status"] in ["AVAILABLE", "NOT_AVAILABLE"]

def test_tool_invalid_arguments_handling():
    """Verify tools cleanly handle missing parameters without crashing."""
    assert "error" in InvestigationTools.get_incident("")
    assert "error" in InvestigationTools.get_gateway_metrics("")
    assert "error" in InvestigationTools.get_failed_payments("")
    assert "error" in InvestigationTools.get_affected_merchants("")
    assert "error" in InvestigationTools.get_payment_context("")
    assert "error" in InvestigationTools.get_webhook_activity("")

def test_investigate_endpoint_when_ai_not_configured(monkeypatch):
    """Verify POST /api/incidents/INC-0001/investigate returns 400 AI_NOT_CONFIGURED when key is empty."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    res = client.post("/api/incidents/INC-0001/investigate")
    assert res.status_code == 400
    detail = res.json()["detail"]
    assert detail["error_code"] == "AI_NOT_CONFIGURED"

def test_investigate_endpoint_incident_not_found(monkeypatch):
    """Verify POST /api/incidents/INC-9999/investigate returns 404 for non-existent incident."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "dummy_key_123456789")
    res = client.post("/api/incidents/INC-9999/investigate")
    assert res.status_code == 404

def test_investigation_and_steps_persistence_in_postgresql():
    """Verify storing and retrieving investigation sessions and steps in PostgreSQL."""
    conn = get_db_connection()
    c = conn.cursor()
    inv_id = "inv_test_abc123"
    c.execute("""
        INSERT INTO ai_investigations (
            investigation_id, incident_id, provider, model, status,
            what_happened, why_it_happened, estimated_exposure, started_at
        ) VALUES (%s, 'INC-0001', 'gemini', 'gemini-2.0-flash', 'completed', 'Spike occurred', 'Gateway X timeout', 158842.85, NOW());
    """, (inv_id,))

    step_id = "step_test_001"
    c.execute("""
        INSERT INTO ai_investigation_steps (
            step_id, investigation_id, step_number, tool_name,
            input_json, output_json, timestamp
        ) VALUES (%s, %s, 1, 'get_gateway_metrics', '{"gateway": "Gateway_X"}', '{"failure_rate": 0.19}', NOW());
    """, (step_id, inv_id))
    conn.commit()
    c.close()
    conn.close()

    # Query via API
    res_inv = client.get(f"/api/investigations/{inv_id}")
    assert res_inv.status_code == 200
    assert res_inv.json()["investigation_id"] == inv_id
    assert res_inv.json()["provider"] == "gemini"

    res_steps = client.get(f"/api/investigations/{inv_id}/steps")
    assert res_steps.status_code == 200
    steps = res_steps.json()
    assert len(steps) == 1
    assert steps[0]["tool_name"] == "get_gateway_metrics"
