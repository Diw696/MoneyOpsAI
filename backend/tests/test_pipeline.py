import pytest
from app.engine.event_pipeline import event_pipeline
from app.engine.database import get_db_connection

def test_canonical_event_pipeline():
    payload = {
        "event_id": "ev_pipe_test_001",
        "payment_id": "pay_pipe_test_001",
        "merchant_id": "merch_Nova_Store",
        "amount": 4999.0,
        "status": "captured",
        "failure_code": None,
        "retry_count": 0
    }
    result = event_pipeline.process_event("payment.captured", payload, source="synthetic")
    assert result["status"] == "processed"
    assert result["canonical_id"] == "ev_pipe_test_001"

    # Verify persisted in SQLite
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM canonical_events WHERE canonical_id = ?", ("ev_pipe_test_001",))
    row = cursor.fetchone()
    conn.close()
    assert row is not None
    assert row["amount"] == 4999.0
    assert row["entity_type"] == "payment"
