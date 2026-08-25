import pytest
from app.engine.database import init_db, get_db_connection
from app.engine.seed_data import seed_database
from app.engine.money_graph import money_graph
from app.engine.case_memory import case_memory
from app.engine.anomaly_detector import anomaly_detector
from app.engine.merchant_memory import merchant_memory
from app.engine.agent import investigation_agent
from app.engine.governor import governor
from app.models.schemas import ActionTier

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    seed_database()

def test_database_seeded():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as c FROM merchants")
    assert cursor.fetchone()["c"] >= 20
    cursor.execute("SELECT COUNT(*) as c FROM incidents")
    assert cursor.fetchone()["c"] == 4
    cursor.execute("SELECT COUNT(*) as c FROM payments")
    assert cursor.fetchone()["c"] > 1000
    conn.close()

def test_money_graph_traversal():
    # Test single payment cluster traversal
    cluster = money_graph.get_payment_cluster("pay_P19283")
    assert cluster["payment"]["id"] == "pay_P19283"
    assert len(cluster["refunds"]) == 2
    assert cluster["is_duplicate_refund"] is True

    # Test gateway blast radius
    blast = money_graph.get_gateway_blast_radius("Gateway_X", "R-104")
    assert blast["gateway"] == "Gateway_X"
    assert blast["affected_merchants_count"] >= 15

def test_case_memory_retrieval():
    results = case_memory.find_similar_incidents("Gateway X refund failure spike R-104 timeout", top_k=3)
    assert len(results) >= 1
    top_case = results[0]
    assert top_case.incident_id == "INC-1282"
    assert top_case.similarity_score >= 0.75

def test_anomaly_detector_scoring():
    anom = anomaly_detector.score_anomaly("test_entity", "payment", {
        "amount": 50000.0,
        "retry_count": 12,
        "refund_deviation": 4.5,
        "gateway_failure_rate": 0.5
    })
    assert anom.anomaly_score >= 0.70
    assert anom.is_anomaly is True
    assert len(anom.contributing_signals) > 0

def test_agent_investigation_golden_demo():
    # Golden Demo 1: Gateway X Spike
    report = investigation_agent.investigate("INC-2841")
    assert report.incident_id == "INC-2841"
    assert report.severity == "critical"
    assert report.confidence >= 0.90
    assert report.action_tier == ActionTier.RED_EXECUTE
    assert report.requires_approval is True
    assert len(report.agent_steps) >= 4
    assert len(report.similar_incidents) >= 1
    assert report.similar_incidents[0].incident_id == "INC-1282"

def test_agent_investigation_duplicate_refund():
    # Scenario 2: Duplicate Refund
    report = investigation_agent.investigate("INC-2840")
    assert report.incident_id == "INC-2840"
    assert report.financial_exposure == 4999.0
    assert "duplicate" in report.root_cause.lower() or "refund" in report.root_cause.lower()

def test_action_governor_execution():
    audit_entry = governor.execute_action(
        investigation_id="INV-TEST-001",
        incident_id="INC-2841",
        action_name="pause_gateway_refund_retries",
        action_tier=ActionTier.RED_EXECUTE,
        approved=True,
        actor="FinOps_Lead_Test",
        evidence_summary=["Test evidence 1", "Test evidence 2"],
        tools_called=["get_gateway_telemetry", "find_similar_incidents"],
        anomaly_score=0.932,
        ai_confidence=0.932,
        root_cause="Gateway X timeout",
        recommended_action="Pause automated refund retries",
        financial_exposure=3140000.0
    )
    assert audit_entry.audit_id.startswith("ACT-")
    assert audit_entry.approval_status == "approved"
    assert audit_entry.human_approval is True
