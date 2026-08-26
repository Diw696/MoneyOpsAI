import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.engine.database import init_db, get_db_connection
from app.engine.incident_lab import IncidentLabGenerator
from app.engine.feature_engine import FeatureEngine
from app.engine.anomaly_detector import AnomalyDetector, anomaly_detector

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_clean_db():
    init_db()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("TRUNCATE TABLE audit_logs, ai_investigation_steps, ai_investigations, incidents, webhook_events, refunds, payments, orders, merchants CASCADE;")
    conn.commit()
    c.close()
    conn.close()

def test_feature_extraction_from_postgresql():
    """Verify FeatureEngine extracts gateway-level aggregations and peer failure rates from PostgreSQL."""
    IncidentLabGenerator.generate_dataset(seed=42, num_payments=500, num_merchants=5, anomaly_type="gateway_spike")

    features = FeatureEngine.extract_gateway_features()
    assert len(features) > 0

    # Ensure all expected explainable business feature keys exist
    for f in features:
        assert "entity_id" in f
        assert "failure_rate" in f
        assert "peer_failure_rate" in f
        assert "failure_rate_ratio" in f
        assert "top_failure_code" in f
        assert "potential_exposure" in f

    # Gateway_X should have the highest failure rate in gateway_spike dataset
    gw_x = next((f for f in features if f["entity_id"] == "Gateway_X"), None)
    assert gw_x is not None
    assert gw_x["failure_rate"] > 0.10
    assert gw_x["failure_rate_ratio"] > 2.0

def test_anomaly_detection_and_incident_persistence():
    """Verify IsolationForest detects Gateway_X anomaly and creates incident in PostgreSQL."""
    IncidentLabGenerator.generate_dataset(seed=42, num_payments=1000, num_merchants=10, anomaly_type="gateway_spike")

    res = anomaly_detector.run_detection()
    assert res["status"] == "success"
    assert res["anomalies_detected"] == 1
    assert len(res["incidents"]) == 1

    inc = res["incidents"][0]
    assert inc["target_entity"] == "Gateway_X"
    assert inc["potential_exposure"] > 0

    # Verify incident persisted in PostgreSQL
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM incidents WHERE target_entity_id = 'Gateway_X';")
    db_inc = dict(c.fetchone())
    c.close()
    conn.close()

    assert db_inc["incident_id"] == inc["incident_id"]
    assert db_inc["status"] == "open"
    assert db_inc["source"] == "incident_lab"
    assert "Gateway_X" in db_inc["title"]

def test_anomaly_detector_idempotency_no_duplicate_incidents():
    """Verify running detector multiple times updates existing incident without duplicate records."""
    IncidentLabGenerator.generate_dataset(seed=42, num_payments=500, num_merchants=5, anomaly_type="gateway_spike")

    # First run
    res1 = anomaly_detector.run_detection()
    assert res1["anomalies_detected"] == 1

    # Second run
    res2 = anomaly_detector.run_detection()
    assert res2["anomalies_detected"] == 1

    # Verify only 1 incident row exists in PostgreSQL
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM incidents WHERE status = 'open';")
    count = c.fetchone()["cnt"]
    c.close()
    conn.close()

    assert count == 1

def test_healthy_dataset_produces_zero_incidents():
    """Verify detector on healthy baseline dataset produces 0 anomalies and 0 incidents."""
    IncidentLabGenerator.generate_dataset(seed=42, num_payments=500, num_merchants=5, anomaly_type="none")

    res = anomaly_detector.run_detection()
    assert res["anomalies_detected"] == 0
    assert len(res["incidents"]) == 0

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM incidents;")
    count = c.fetchone()["cnt"]
    c.close()
    conn.close()

    assert count == 0

def test_anomaly_detection_and_incidents_api_endpoints():
    """Verify POST /api/anomalies/detect and GET /api/incidents endpoints."""
    IncidentLabGenerator.generate_dataset(seed=42, num_payments=500, num_merchants=5, anomaly_type="gateway_spike")

    # 1. Trigger Detection via API
    res_detect = client.post("/api/anomalies/detect")
    assert res_detect.status_code == 200
    data_detect = res_detect.json()
    assert data_detect["anomalies_detected"] == 1

    # 2. List Incidents via API
    res_list = client.get("/api/incidents")
    assert res_list.status_code == 200
    incidents = res_list.json()
    assert len(incidents) == 1
    assert incidents[0]["target_entity_id"] == "Gateway_X"
    assert "evidence" in incidents[0]

    # 3. Get Single Incident via API
    inc_id = incidents[0]["incident_id"]
    res_single = client.get(f"/api/incidents/{inc_id}")
    assert res_single.status_code == 200
    assert res_single.json()["incident_id"] == inc_id
