import pytest
import json
from fastapi.testclient import TestClient
from app.main import app
from app.engine.database import get_db_connection, init_db
from app.engine.case_memory import case_memory, HISTORICAL_CASES

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    case_memory.ensure_historical_cases_seeded()

def test_case_memory_seeds_in_postgresql():
    """Verifies that historical simulation cases are seeded into PostgreSQL."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT incident_id, title, status, source FROM incidents WHERE status = 'resolved';")
    rows = c.fetchall()
    c.close()
    conn.close()

    assert len(rows) >= 3
    ids = [r["incident_id"] for r in rows]
    assert "INC-HIST-001" in ids
    assert "INC-HIST-002" in ids
    assert "INC-HIST-003" in ids
    for r in rows:
        assert r["source"] == "incident_lab"

def test_case_memory_similarity_calculation():
    """Verifies that Gateway_X timeout incident accurately matches historical INC-HIST-001."""
    curr = {
        "incident_id": "INC-0001",
        "type": "gateway_failure_spike",
        "target_entity_type": "gateway",
        "target_entity_id": "Gateway_X",
        "evidence_json": json.dumps({
            "failure_rate_pct": 19.08,
            "peer_failure_rate_pct": 3.52,
            "top_failure_code": "GATEWAY_TIMEOUT",
            "top_failure_code_share_pct": 85.06
        })
    }

    hist = HISTORICAL_CASES[0] # INC-HIST-001 (Gateway_X timeout spike)
    sim = case_memory.calculate_similarity(curr, hist)

    assert sim["similarity_score_pct"] >= 80.0
    assert sim["confidence_tier"] == "HIGH MATCH"
    assert sim["factors"]["type_match"] == 35.0
    assert sim["factors"]["entity_match"] == 25.0
    assert sim["factors"]["error_code_match"] == 20.0

def test_similar_incidents_api_endpoint():
    """Verifies GET /api/incidents/{id}/similar returns ranked historical precedents."""
    # Ensure active incident exists
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO incidents (
            incident_id, title, type, target_entity_type, target_entity_id,
            severity, status, affected_merchants, affected_payments,
            potential_exposure, anomaly_score, primary_signal, source, detected_at, description
        ) VALUES (
            'INC-TEST-SIM', 'Test Gateway Spike', 'gateway_failure_spike', 'gateway', 'Gateway_X',
            'critical', 'open', 10, 87, 150000.0, 0.95, 'Gateway_X timeout spike', 'incident_lab', NOW(), 'Test'
        ) ON CONFLICT (incident_id) DO NOTHING;
    """)
    conn.commit()
    c.close()
    conn.close()

    res = client.get("/api/incidents/INC-TEST-SIM/similar")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    top = data[0]
    assert "historical_incident_id" in top
    assert "similarity_score_pct" in top
    assert "historical_root_cause" in top
    assert "previous_action" in top
    assert "outcome" in top
    assert top["historical_incident_id"] == "INC-HIST-001"
