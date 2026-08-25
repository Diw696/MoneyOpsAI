import hmac
import hashlib
import json
import pytest
from app.core.config import settings
from app.integrations.razorpay.client import razorpay_client
from app.integrations.razorpay.mapper import RazorpayMapper
from app.integrations.razorpay.models import RazorpayPaymentEntity, RazorpayRefundEntity
from app.engine.event_pipeline import event_pipeline, EventRepository
from app.engine.database import get_db_connection

def test_webhook_signature_verification():
    secret = "test_webhook_secret_key_123"
    raw_payload = b'{"event":"payment.captured","id":"wh_test_99"}'
    valid_sig = hmac.new(secret.encode(), raw_payload, hashlib.sha256).hexdigest()
    
    assert razorpay_client.verify_webhook_signature(raw_payload, valid_sig, secret=secret) is True
    assert razorpay_client.verify_webhook_signature(raw_payload, "invalid_sig_hex", secret=secret) is False

def test_razorpay_payment_mapper():
    entity_dict = {
        "id": "pay_test_Rzp01",
        "entity": "payment",
        "amount": 499900,  # 4999 INR
        "currency": "INR",
        "status": "captured",
        "order_id": "order_test_Ord01",
        "method": "card",
        "captured": True,
        "notes": {"merchant_id": "merch_Nova_Store"},
        "acquirer_data": {"bank": "Gateway_HDFC"},
        "created_at": 1724580000
    }
    p = RazorpayPaymentEntity(**entity_dict)
    canonical = RazorpayMapper.payment_to_canonical(p)

    assert canonical.entity_id == "pay_test_Rzp01"
    assert canonical.amount == 4999.0
    assert canonical.event_source == "razorpay_test"
    assert canonical.merchant_id == "merch_Nova_Store"
    assert canonical.payload["gateway"] == "Gateway_HDFC"

def test_raw_event_persistence_and_idempotency():
    ext_id = "x_rzp_ev_idempotent_test_001"
    payload = {
        "event": "payment.captured",
        "id": ext_id,
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_idem_001",
                    "amount": 250000,
                    "currency": "INR",
                    "status": "captured",
                    "method": "card",
                    "notes": {"merchant_id": "merch_Nova_Store"},
                    "created_at": 1724580000
                }
            }
        }
    }

    # First Ingestion
    res1 = event_pipeline.process_event("payment.captured", payload, source="razorpay_webhook", external_event_id=ext_id)
    assert res1["status"] == "processed"

    # Verify persisted in raw_external_events
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM raw_external_events WHERE external_event_id = ?", (ext_id,))
    raw_row = cursor.fetchone()
    assert raw_row is not None
    assert raw_row["processing_status"] == "processed"
    conn.close()

    # Second Ingestion (Exact same external_event_id) -> Idempotency Check
    res2 = event_pipeline.process_event("payment.captured", payload, source="razorpay_webhook", external_event_id=ext_id)
    assert res2["status"] == "duplicate_skipped"
    assert "already ingested" in res2["message"]

def test_test_mode_refund_creation():
    refund = razorpay_client.create_test_refund(payment_id="pay_idem_001", amount_inr=500.0)
    assert refund is not None
    assert refund.payment_id == "pay_idem_001"
    assert refund.amount == 50000  # 500 INR in paise
