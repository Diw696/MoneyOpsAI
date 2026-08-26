import pytest
from unittest.mock import patch, PropertyMock
from fastapi.testclient import TestClient
from app.main import app
from app.engine.database import init_db, get_db_connection
from app.integrations.razorpay.client import RazorpayClient
from app.integrations.razorpay.models import RazorpayPaymentEntity, RazorpayOrderEntity, RazorpayRefundEntity
from app.integrations.razorpay.mapper import RazorpayMapper

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

def test_database_schema_created_in_postgresql():
    """Verify all 9 clean V2 tables exist in PostgreSQL information_schema."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    tables = [row["table_name"] for row in c.fetchall()]
    c.close()
    conn.close()

    expected_tables = [
        "ai_investigation_steps",
        "ai_investigations",
        "audit_logs",
        "incidents",
        "merchants",
        "orders",
        "payments",
        "refunds",
        "webhook_events"
    ]
    for tbl in expected_tables:
        assert tbl in tables, f"Expected table '{tbl}' to exist in PostgreSQL schema"

def test_mapper_conversion_official_fields():
    """Test mapper accurately parses official Razorpay Test Mode response fields."""
    raw_payment = RazorpayPaymentEntity(
        id="pay_test_001",
        amount=499900,  # 4,999.00 INR in paise
        currency="INR",
        status="captured",
        order_id="order_test_001",
        method="card",
        acquirer_data={"bank": "HDFC"},
        created_at=1724580000,
        notes={"merchant_id": "merch_Nova_Store"}
    )
    p_dict = RazorpayMapper.payment_to_db_dict(raw_payment, source="razorpay_test")
    assert p_dict["payment_id"] == "pay_test_001"
    assert p_dict["amount"] == 4999.0
    assert p_dict["gateway"] == "Gateway_HDFC"
    assert p_dict["source"] == "razorpay_test"
    assert "2024" in p_dict["created_at"]

    raw_order = RazorpayOrderEntity(
        id="order_test_001",
        amount=499900,
        currency="INR",
        status="paid",
        created_at=1724580000,
        notes={"merchant_id": "merch_Nova_Store"}
    )
    o_dict = RazorpayMapper.order_to_db_dict(raw_order, source="razorpay_test")
    assert o_dict["order_id"] == "order_test_001"
    assert o_dict["amount"] == 4999.0

    raw_refund = RazorpayRefundEntity(
        id="rfnd_test_001",
        payment_id="pay_test_001",
        amount=499900,
        currency="INR",
        status="processed",
        speed_processed="instant",
        created_at=1724580000
    )
    r_dict = RazorpayMapper.refund_to_db_dict(raw_refund, source="razorpay_test")
    assert r_dict["refund_id"] == "rfnd_test_001"
    assert r_dict["payment_id"] == "pay_test_001"
    assert r_dict["amount"] == 4999.0

def test_sync_endpoint_without_credentials():
    """Verify sync endpoint safely reports missing credentials without fabricating fake data."""
    with patch.object(RazorpayClient, "is_configured", new_callable=PropertyMock, return_value=False):
        res = client.post("/api/razorpay/sync")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "credentials_required"
        assert data["configured"] is False
        assert data["payments_fetched"] == 0
        assert data["orders_fetched"] == 0
        assert data["refunds_fetched"] == 0

def test_sync_endpoint_end_to_end_persists_to_postgresql():
    """
    Test End-to-End:
    Razorpay API response -> Sync Endpoint -> PostgreSQL Upsert -> Query Endpoints.
    """
    mock_orders = [
        RazorpayOrderEntity(
            id="order_real_test_901",
            amount=750000,
            currency="INR",
            status="paid",
            created_at=1724580000,
            notes={"merchant_id": "merch_Nova_Store"}
        )
    ]
    mock_payments = [
        RazorpayPaymentEntity(
            id="pay_real_test_901",
            amount=750000,
            currency="INR",
            status="captured",
            order_id="order_real_test_901",
            method="upi",
            acquirer_data={"bank": "Axis"},
            created_at=1724580000,
            notes={"merchant_id": "merch_Nova_Store"}
        )
    ]
    mock_refunds = [
        RazorpayRefundEntity(
            id="rfnd_real_test_901",
            payment_id="pay_real_test_901",
            amount=750000,
            currency="INR",
            status="processed",
            speed_processed="normal",
            created_at=1724580000
        )
    ]

    with patch.object(RazorpayClient, "is_configured", new_callable=PropertyMock, return_value=True), \
         patch.object(RazorpayClient, "fetch_orders", return_value=mock_orders), \
         patch.object(RazorpayClient, "fetch_payments", return_value=mock_payments), \
         patch.object(RazorpayClient, "fetch_refunds", return_value=mock_refunds):

        # 1. Trigger Sync
        res = client.post("/api/razorpay/sync")
        assert res.status_code == 200
        sync_result = res.json()
        assert sync_result["status"] == "success"
        assert sync_result["orders_fetched"] == 1
        assert sync_result["payments_fetched"] == 1
        assert sync_result["refunds_fetched"] == 1
        assert sync_result["payments_upserted"] == 1

        # 2. Verify Persistence in PostgreSQL via GET Endpoints
        p_res = client.get("/api/payments")
        assert p_res.status_code == 200
        payments = p_res.json()
        assert len(payments) == 1
        assert payments[0]["payment_id"] == "pay_real_test_901"
        assert payments[0]["amount"] == 7500.0
        assert payments[0]["method"] == "upi"
        assert payments[0]["source"] == "razorpay_test"

        o_res = client.get("/api/orders")
        assert o_res.status_code == 200
        orders = o_res.json()
        assert len(orders) == 1
        assert orders[0]["order_id"] == "order_real_test_901"
        assert orders[0]["amount"] == 7500.0

        r_res = client.get("/api/refunds")
        assert r_res.status_code == 200
        refunds = r_res.json()
        assert len(refunds) == 1
        assert refunds[0]["refund_id"] == "rfnd_real_test_901"
        assert refunds[0]["payment_id"] == "pay_real_test_901"
        assert refunds[0]["amount"] == 7500.0
