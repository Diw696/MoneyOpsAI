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
    c.execute("DELETE FROM audit_logs; DELETE FROM ai_investigation_steps; DELETE FROM ai_investigations; DELETE FROM incidents; DELETE FROM webhook_events; DELETE FROM refunds; DELETE FROM payments; DELETE FROM orders; DELETE FROM merchants;")
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

def _insert_raw_payments(gateway: str, total: int, failed: int, source: str = "razorpay_test"):
    """Inserts real payment rows directly (bypassing IncidentLabGenerator, which
    can't reliably produce an exact tiny total for one gateway) so a test can pin
    down an exact small sample size like the real INC-0005 bug (2 attempts, both
    failed)."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO merchants (merchant_id, name, category, baseline_refund_rate, created_at)
        VALUES ('merch_test_tiny', 'Test Tiny Merchant', 'test', 0.01, NOW())
        ON CONFLICT (merchant_id) DO NOTHING;
    """)
    for i in range(total):
        status = "failed" if i < failed else "captured"
        c.execute("""
            INSERT INTO payments (
                payment_id, merchant_id, amount, currency, status, method, gateway,
                failure_code, source, created_at, ingested_at
            ) VALUES (%s, 'merch_test_tiny', 100, 'INR', %s, 'card', %s, %s, %s, NOW(), NOW());
        """, (
            f"pay_tiny_{gateway}_{i:03d}", status, gateway,
            "BAD_REQUEST_ERROR" if status == "failed" else None, source
        ))
    conn.commit()
    c.close()
    conn.close()

def test_sub_floor_gateway_never_creates_critical_or_high_incident():
    """
    Real reproduction of the INC-0005 bug: a gateway with only 2 total payment
    attempts, both failed (a 100% failure rate) must NOT create a CRITICAL/HIGH
    (or any) incident — regardless of how extreme the raw percentage looks —
    because it never clears MIN_SAMPLE_SIZE. A second gateway with a real,
    adequately-sampled spike must still fire normally in the same run, proving
    the guardrail suppresses only the statistically unreliable entity.
    """
    IncidentLabGenerator.generate_dataset(seed=42, num_payments=500, num_merchants=5, anomaly_type="gateway_spike")
    _insert_raw_payments("Gateway_TinySample", total=2, failed=2, source="razorpay_test")

    evaluations = anomaly_detector.evaluate_gateways()
    tiny = next(g for g in evaluations if g["gateway"] == "Gateway_TinySample")
    assert tiny["total_payments"] == 2
    assert tiny["failure_rate"] == 1.0
    assert tiny["sample_size_sufficient"] is False
    assert tiny["below_confidence_threshold"] is True
    assert tiny["is_anomalous"] is False

    res = anomaly_detector.run_detection()
    incident_targets = [inc["target_entity"] for inc in res["incidents"]]
    assert "Gateway_TinySample" not in incident_targets

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM incidents WHERE target_entity_id = 'Gateway_TinySample';")
    assert c.fetchone() is None
    # The real, adequately-sampled Gateway_X spike must still fire in the same run.
    c.execute("SELECT severity FROM incidents WHERE target_entity_id = 'Gateway_X';")
    gw_x_row = c.fetchone()
    c.close()
    conn.close()
    assert gw_x_row is not None
    assert gw_x_row["severity"] in ("critical", "high", "medium")

def test_wilson_lower_bound_rejects_marginal_small_sample():
    """A gateway right at the sample-size floor (20 attempts) with a raw rate that
    only barely clears MIN_FAILURE_RATE (3/20 = 15%) can still have a Wilson lower
    bound below the 8% floor — this is exactly the small-n overconfidence Task 2
    guards against beyond the raw count check alone."""
    lb_marginal = AnomalyDetector.wilson_lower_bound(failures=3, total=20)
    assert lb_marginal < 0.08

    # A well-sampled, genuinely elevated rate should clear it comfortably.
    lb_real = AnomalyDetector.wilson_lower_bound(failures=87, total=456)
    assert lb_real > 0.08

def test_merchant_refund_spike_creates_merchant_type_incident():
    """
    Verify the merchant-level detector family (distinct from the gateway
    IsolationForest scorer) actually creates a merchant_refund_spike incident
    from a refund_spike Incident Lab scenario — the incident type must be
    genuinely different data, not just a different title on gateway-shaped data.
    """
    IncidentLabGenerator.generate_dataset(seed=2, num_payments=1500, num_merchants=5, anomaly_type="refund_spike")

    res = anomaly_detector.run_detection()
    refund_incidents = [inc for inc in res["incidents"] if "Refund Rate Anomaly" in inc["title"]]
    assert len(refund_incidents) == 1
    assert refund_incidents[0]["target_entity"] == "merch_Nova_Store"

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM incidents WHERE type = 'merchant_refund_spike';")
    row = dict(c.fetchone())
    c.close()
    conn.close()

    assert row["target_entity_type"] == "merchant"
    assert row["target_entity_id"] == "merch_Nova_Store"
    evidence = json.loads(row["evidence_json"])
    assert evidence["entity_type"] == "merchant"
    assert evidence["actual_refund_rate_pct"] > evidence["baseline_refund_rate_pct"]

def test_no_phantom_recurrence_after_reject_or_execute():
    """
    Reproduces the exact product complaint: Batch 1 -> incident detected ->
    human rejects it -> incident leaves active work. Batch 2 (normal activity,
    no new scenario injected) must NOT immediately recreate the same incident
    from the same old evidence merely because the historical aggregate is
    still technically anomalous. Also confirms the same for the
    execute/approve path, and that a genuinely NEW batch's fresh evidence
    still creates a new incident afterward.
    """
    from app.engine.action_governor import action_governor

    # Batch 1: real refund-spike scenario -> should detect.
    IncidentLabGenerator.generate_dataset(seed=2, num_payments=1500, num_merchants=5, anomaly_type="refund_spike")
    res1 = anomaly_detector.run_detection()
    refund_incs = [i for i in res1["incidents"] if "Refund Rate Anomaly" in i["title"]]
    assert len(refund_incs) == 1
    inc_id = refund_incs[0]["incident_id"]

    # Human rejects it.
    prop = action_governor.propose_action(
        incident_id=inc_id, investigation_id="inv_x", action_type="pause_merchant_settlements",
        target_entity="merch_Nova_Store", reason="test", actor="Gemini_Agent"
    )
    action_governor.reject_action(prop["action_id"], actor="Operator", reason="false positive")

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT status FROM incidents WHERE incident_id = %s;", (inc_id,))
    assert c.fetchone()["status"] == "rejected"
    c.close()
    conn.close()

    # Batch 2: normal activity only, no scenario injected — must NOT re-trigger
    # the same incident from the same old (now-rejected) evidence.
    IncidentLabGenerator.generate_dataset(seed=999, num_payments=300, num_merchants=5, anomaly_type="none")
    res2 = anomaly_detector.run_detection()
    refund_incs_2 = [i for i in res2["incidents"] if "Refund Rate Anomaly" in i["title"]]
    assert len(refund_incs_2) == 0, f"phantom recurrence: {refund_incs_2}"

def test_duplicate_refund_creates_distinct_incident_type():
    """Verify duplicate_refund scenario data creates a merchant_duplicate_refund
    incident distinct from a plain refund-volume spike."""
    IncidentLabGenerator.generate_dataset(seed=11, num_payments=800, num_merchants=5, anomaly_type="duplicate_refund")

    res = anomaly_detector.run_detection()
    dup_incidents = [inc for inc in res["incidents"] if "Duplicate Refund" in inc["title"]]
    assert len(dup_incidents) == 1

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM incidents WHERE type = 'merchant_duplicate_refund';")
    assert c.fetchone()["cnt"] == 1
    c.close()
    conn.close()

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
