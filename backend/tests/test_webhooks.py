import json
import hmac
import hashlib
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.engine.database import init_db, get_db_connection

client = TestClient(app)

SECRET = "whsec_test_secret_12345"

@pytest.fixture(autouse=True)
def setup_clean_db(monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", SECRET)
    init_db()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("TRUNCATE TABLE audit_logs, ai_investigation_steps, ai_investigations, incidents, webhook_events, refunds, payments, orders, merchants CASCADE;")
    conn.commit()
    c.close()
    conn.close()

def generate_signature(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

def test_webhook_valid_signature_payment_captured():
    """Verify valid signature processes payment.captured and stores in PostgreSQL."""
    payload = {
        "entity": "event",
        "account_id": "acc_TU6z7jmcjJLP4N",
        "event": "payment.captured",
        "id": "x_evt_pay_cap_001",
        "created_at": 1724580000,
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_cap_001",
                    "entity": "payment",
                    "amount": 350000,  # 3,500.00 INR
                    "currency": "INR",
                    "status": "captured",
                    "order_id": "order_test_cap_001",
                    "method": "card",
                    "acquirer_data": {"bank": "HDFC"},
                    "created_at": 1724580000,
                    "notes": {"merchant_id": "merch_Nova_Store"}
                }
            }
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_signature(raw_body)

    res = client.post(
        "/api/webhooks/razorpay",
        content=raw_body,
        headers={"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": "x_evt_pay_cap_001", "Content-Type": "application/json"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "processed"
    assert data["external_event_id"] == "x_evt_pay_cap_001"
    assert data["event_type"] == "payment.captured"
    assert data["entity_id"] == "pay_test_cap_001"

    # Verify PostgreSQL persistence
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM payments WHERE payment_id = %s;", ("pay_test_cap_001",))
    pay_row = dict(c.fetchone())
    c.execute("SELECT * FROM webhook_events WHERE external_event_id = %s;", ("x_evt_pay_cap_001",))
    wh_row = dict(c.fetchone())
    c.close()
    conn.close()

    assert pay_row["amount"] == 3500.0
    assert pay_row["status"] == "captured"
    assert pay_row["source"] == "razorpay_webhook"
    assert wh_row["delivery_status"] == "processed"

def test_webhook_invalid_signature_rejected():
    """Verify invalid signature is rejected with HTTP 400."""
    payload = {"event": "payment.captured", "id": "x_evt_invalid_001"}
    raw_body = json.dumps(payload).encode("utf-8")
    fake_sig = "fake_invalid_hmac_signature_hex_string"

    res = client.post(
        "/api/webhooks/razorpay",
        content=raw_body,
        headers={"X-Razorpay-Signature": fake_sig, "Content-Type": "application/json"}
    )
    assert res.status_code == 400
    assert "Invalid Razorpay webhook signature" in res.json()["detail"]

def test_webhook_missing_signature_rejected():
    """Verify missing signature when secret is configured is rejected with HTTP 400."""
    payload = {"event": "payment.captured", "id": "x_evt_missing_sig_001"}
    raw_body = json.dumps(payload).encode("utf-8")

    res = client.post(
        "/api/webhooks/razorpay",
        content=raw_body,
        headers={"Content-Type": "application/json"}
    )
    assert res.status_code == 400
    assert "Invalid Razorpay webhook signature" in res.json()["detail"]

def test_webhook_duplicate_event_id_idempotency():
    """Verify duplicate delivery returns duplicate_skipped without duplicate database entries."""
    payload = {
        "event": "payment.captured",
        "id": "x_evt_idem_001",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_idem_001",
                    "amount": 100000,
                    "currency": "INR",
                    "status": "captured",
                    "created_at": 1724580000,
                    "notes": {"merchant_id": "merch_Nova_Store"}
                }
            }
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_signature(raw_body)

    # 1. First Dispatch
    res1 = client.post(
        "/api/webhooks/razorpay",
        content=raw_body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"}
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "processed"

    # 2. Second Dispatch (Replay)
    res2 = client.post(
        "/api/webhooks/razorpay",
        content=raw_body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"}
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "duplicate_skipped"
    assert "already ingested (idempotency enforced)" in res2.json()["message"]

    # Verify only 1 webhook record and 1 payment record exists in PostgreSQL
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM webhook_events WHERE external_event_id = %s;", ("x_evt_idem_001",))
    wh_count = c.fetchone()["cnt"]
    c.execute("SELECT COUNT(*) as cnt FROM payments WHERE payment_id = %s;", ("pay_idem_001",))
    pay_count = c.fetchone()["cnt"]
    c.close()
    conn.close()

    assert wh_count == 1
    assert pay_count == 1

def test_webhook_order_paid_event():
    """Verify order.paid event is normalized into orders table in PostgreSQL."""
    payload = {
        "event": "order.paid",
        "id": "x_evt_ord_001",
        "payload": {
            "order": {
                "entity": {
                    "id": "order_test_hook_001",
                    "amount": 899900,  # 8,999.00 INR
                    "currency": "INR",
                    "status": "paid",
                    "created_at": 1724580000,
                    "notes": {"merchant_id": "merch_Nova_Store"}
                }
            }
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_signature(raw_body)

    res = client.post(
        "/api/webhooks/razorpay",
        content=raw_body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "processed"

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE order_id = %s;", ("order_test_hook_001",))
    ord_row = dict(c.fetchone())
    c.close()
    conn.close()

    assert ord_row["amount"] == 8999.0
    assert ord_row["status"] == "paid"
    assert ord_row["source"] == "razorpay_webhook"

def test_webhook_refund_processed_event():
    """Verify refund.processed event is normalized into refunds table in PostgreSQL."""
    payload = {
        "event": "refund.processed",
        "id": "x_evt_ref_001",
        "payload": {
            "refund": {
                "entity": {
                    "id": "rfnd_test_hook_001",
                    "payment_id": "pay_test_hook_parent_001",
                    "amount": 150000,  # 1,500.00 INR
                    "currency": "INR",
                    "status": "processed",
                    "speed_processed": "instant",
                    "created_at": 1724580000,
                    "notes": {"merchant_id": "merch_Nova_Store"}
                }
            }
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_signature(raw_body)

    res = client.post(
        "/api/webhooks/razorpay",
        content=raw_body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "processed"

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM refunds WHERE refund_id = %s;", ("rfnd_test_hook_001",))
    ref_row = dict(c.fetchone())
    c.close()
    conn.close()

    assert ref_row["amount"] == 1500.0
    assert ref_row["speed"] == "instant"
    assert ref_row["status"] == "processed"

def test_webhook_malformed_json_rejected():
    """Verify non-JSON byte body is rejected with HTTP 400."""
    raw_body = b"NOT_A_VALID_JSON_STRING"
    sig = generate_signature(raw_body)

    res = client.post(
        "/api/webhooks/razorpay",
        content=raw_body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"}
    )
    assert res.status_code == 400
    assert "Malformed JSON payload" in res.json()["detail"]
