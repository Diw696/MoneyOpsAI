import json
import hmac
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Header
from app.core.config import settings
from app.engine.database import get_db_connection
from app.engine.webhook_service import webhook_service
from app.integrations.razorpay.client import razorpay_client
from app.integrations.razorpay.mapper import RazorpayMapper
from app.integrations.razorpay.exceptions import RazorpayAuthError, RazorpayAPIError

router = APIRouter()

# =============================================================================
# HEALTH & SYSTEM STATUS
# =============================================================================

@router.get("/health")
def get_health():
    """Returns system health and Razorpay integration connection status."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "razorpay_configured": razorpay_client.is_configured,
        "ai_provider": settings.AI_PROVIDER,
        "gemini_configured": bool(settings.GEMINI_API_KEY and not settings.GEMINI_API_KEY.startswith("YOUR_"))
    }

# =============================================================================
# RAZORPAY TEST MODE SYNCHRONIZATION (PHASE 3)
# =============================================================================

@router.post("/razorpay/sync")
def sync_razorpay_data():
    """
    Calls official Razorpay REST APIs to fetch Orders, Payments, and Refunds,
    maps fields strictly into canonical schemas, and upserts into SQLite.
    Zero synthetic fabrication. Returns actual fetched and persisted counts.
    """
    if not razorpay_client.is_configured:
        return {
            "status": "credentials_required",
            "message": "Razorpay API credentials not configured. Please set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env.",
            "configured": False,
            "orders_fetched": 0,
            "payments_fetched": 0,
            "refunds_fetched": 0,
            "orders_upserted": 0,
            "payments_upserted": 0,
            "refunds_upserted": 0
        }

    try:
        # 1. Fetch from Razorpay Test Mode APIs
        orders = razorpay_client.fetch_orders(count=20)
        payments = razorpay_client.fetch_payments(count=20)
        refunds = razorpay_client.fetch_refunds(count=20)

        conn = get_db_connection()
        cursor = conn.cursor()
        now_str = datetime.utcnow().isoformat()

        # Ensure default merchant exists for foreign key integrity
        cursor.execute("""
            INSERT OR IGNORE INTO merchants (merchant_id, name, category, baseline_refund_rate, created_at)
            VALUES ('merch_Nova_Store', 'Nova Lifestyle & Fashion', 'ecommerce', 0.018, ?)
        """, (now_str,))

        orders_count = 0
        payments_count = 0
        refunds_count = 0

        # 2. Upsert Orders
        for o in orders:
            o_dict = RazorpayMapper.order_to_db_dict(o, source="razorpay_test")
            cursor.execute("""
                INSERT OR REPLACE INTO orders (order_id, merchant_id, amount, currency, status, source, created_at, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                o_dict["order_id"], o_dict["merchant_id"], o_dict["amount"],
                o_dict["currency"], o_dict["status"], o_dict["source"],
                o_dict["created_at"], o_dict["ingested_at"]
            ))
            orders_count += 1

        # 3. Upsert Payments
        for p in payments:
            p_dict = RazorpayMapper.payment_to_db_dict(p, source="razorpay_test")
            cursor.execute("""
                INSERT OR REPLACE INTO payments (
                    payment_id, order_id, merchant_id, amount, currency, status,
                    method, gateway, failure_code, error_description, retry_count,
                    source, created_at, captured_at, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p_dict["payment_id"], p_dict["order_id"], p_dict["merchant_id"],
                p_dict["amount"], p_dict["currency"], p_dict["status"],
                p_dict["method"], p_dict["gateway"], p_dict["failure_code"],
                p_dict["error_description"], p_dict["retry_count"],
                p_dict["source"], p_dict["created_at"], p_dict["captured_at"],
                p_dict["ingested_at"]
            ))
            payments_count += 1

        # 4. Upsert Refunds
        for r in refunds:
            r_dict = RazorpayMapper.refund_to_db_dict(r, source="razorpay_test")
            cursor.execute("""
                INSERT OR REPLACE INTO refunds (
                    refund_id, payment_id, merchant_id, amount, currency, status,
                    speed, failure_reason, source, created_at, processed_at, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r_dict["refund_id"], r_dict["payment_id"], r_dict["merchant_id"],
                r_dict["amount"], r_dict["currency"], r_dict["status"],
                r_dict["speed"], r_dict["failure_reason"], r_dict["source"],
                r_dict["created_at"], r_dict["processed_at"], r_dict["ingested_at"]
            ))
            refunds_count += 1

        conn.commit()
        conn.close()

        return {
            "status": "success",
            "source": "razorpay_test",
            "configured": True,
            "orders_fetched": len(orders),
            "payments_fetched": len(payments),
            "refunds_fetched": len(refunds),
            "orders_upserted": orders_count,
            "payments_upserted": payments_count,
            "refunds_upserted": refunds_count
        }
    except RazorpayAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Synchronization failed: {str(e)}")

# =============================================================================
# RAZORPAY WEBHOOK INGESTION (PHASE 5)
# =============================================================================

@router.post("/webhooks/razorpay")
async def ingest_razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None, alias="X-Razorpay-Signature"),
    x_razorpay_event_id: Optional[str] = Header(None, alias="X-Razorpay-Event-Id")
):
    """
    Ingests real Razorpay Test Mode webhooks.
    Validates HMAC-SHA256 signature against RAZORPAY_WEBHOOK_SECRET,
    enforces idempotency via external_event_id, stores raw event in webhook_events,
    and normalizes into orders, payments, and refunds tables.
    """
    raw_body = await request.body()
    return webhook_service.process_webhook(
        raw_body=raw_body,
        signature=x_razorpay_signature,
        header_event_id=x_razorpay_event_id
    )

# =============================================================================
# DATA ENTITY QUERY ENDPOINTS
# =============================================================================

@router.get("/payments")
def list_payments(limit: int = 50, source: Optional[str] = None):
    """Retrieves persisted payments from SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if source:
        cursor.execute("SELECT * FROM payments WHERE source = ? ORDER BY created_at DESC LIMIT ?", (source, limit))
    else:
        cursor.execute("SELECT * FROM payments ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/orders")
def list_orders(limit: int = 50, source: Optional[str] = None):
    """Retrieves persisted orders from SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if source:
        cursor.execute("SELECT * FROM orders WHERE source = ? ORDER BY created_at DESC LIMIT ?", (source, limit))
    else:
        cursor.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/refunds")
def list_refunds(limit: int = 50, source: Optional[str] = None):
    """Retrieves persisted refunds from SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if source:
        cursor.execute("SELECT * FROM refunds WHERE source = ? ORDER BY created_at DESC LIMIT ?", (source, limit))
    else:
        cursor.execute("SELECT * FROM refunds ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/webhooks")
def list_webhooks(limit: int = 50):
    """Retrieves persisted webhook events from SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM webhook_events ORDER BY received_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/incidents")
def list_incidents():
    """Retrieves active incidents from SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM incidents ORDER BY detected_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
