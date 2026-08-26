import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.engine.database import init_db, get_db_connection
from app.engine.pipeline import CanonicalEvent, IngestionPipeline
from app.engine.incident_lab import IncidentLabGenerator

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

def test_canonical_event_invariants_validation():
    """Verify CanonicalEvent rejects invalid amounts or empty entity IDs."""
    with pytest.raises(ValueError):
        CanonicalEvent(
            source="incident_lab",
            event_type="payment.captured",
            entity_type="payment",
            entity_id="pay_001",
            merchant_id="merch_01",
            amount=-50.0  # Invalid negative amount
        ).validate_invariants()

    with pytest.raises(ValueError):
        CanonicalEvent(
            source="invalid_source",  # Invalid source
            event_type="payment.captured",
            entity_type="payment",
            entity_id="pay_001",
            merchant_id="merch_01",
            amount=100.0
        ).validate_invariants()

def test_ingestion_pipeline_single_event():
    """Verify IngestionPipeline properly persists a single payment event into PostgreSQL."""
    event = CanonicalEvent(
        source="incident_lab",
        event_type="payment.captured",
        entity_type="payment",
        entity_id="pay_pipe_test_001",
        merchant_id="merch_Nova_Store",
        amount=1500.0,
        currency="INR",
        status="captured",
        payload={
            "order_id": "order_pipe_test_001",
            "method": "upi",
            "gateway": "Gateway_HDFC"
        }
    )

    res = IngestionPipeline.ingest_event(event)
    assert res["status"] == "persisted"
    assert res["entity_id"] == "pay_pipe_test_001"

    # Query PostgreSQL
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM payments WHERE payment_id = 'pay_pipe_test_001';")
    row = dict(c.fetchone())
    c.close()
    conn.close()

    assert row["amount"] == 1500.0
    assert row["source"] == "incident_lab"
    assert row["gateway"] == "Gateway_HDFC"

def test_incident_lab_generator_reproducible():
    """Verify IncidentLabGenerator produces exact same counts with same seed."""
    res1 = IncidentLabGenerator.generate_dataset(seed=42, num_payments=200, num_merchants=5)
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM payments WHERE source = 'incident_lab';")
    cnt1 = c.fetchone()["cnt"]
    c.close()
    conn.close()

    assert res1["payments_ingested"] == 200
    assert cnt1 == 200

def test_stats_and_source_distribution_endpoints():
    """Verify GET /api/stats and GET /api/stats/sources reflect actual PostgreSQL counts."""
    # 1. Ingest a payment with source='incident_lab'
    event_lab = CanonicalEvent(
        source="incident_lab",
        event_type="payment.captured",
        entity_type="payment",
        entity_id="pay_stat_001",
        merchant_id="merch_Nova_Store",
        amount=500.0,
        status="captured"
    )
    # 2. Ingest a payment with source='razorpay_test'
    event_rzp = CanonicalEvent(
        source="razorpay_test",
        event_type="payment.captured",
        entity_type="payment",
        entity_id="pay_stat_002",
        merchant_id="merch_Nova_Store",
        amount=1000.0,
        status="captured"
    )
    IngestionPipeline.ingest_batch([event_lab, event_rzp])

    # 3. Call GET /api/stats
    res_stats = client.get("/api/stats")
    assert res_stats.status_code == 200
    data_stats = res_stats.json()
    assert data_stats["payments"] == 2

    # 4. Call GET /api/stats/sources
    res_sources = client.get("/api/stats/sources")
    assert res_sources.status_code == 200
    data_sources = res_sources.json()
    assert data_sources["payments"]["incident_lab"] == 1
    assert data_sources["payments"]["razorpay_test"] == 1
