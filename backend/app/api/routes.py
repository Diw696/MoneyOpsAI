import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request, Header
from app.core.config import settings
from app.engine.database import get_db_connection
from app.engine.pipeline import CanonicalEvent, IngestionPipeline
from app.engine.webhook_service import webhook_service
from app.engine.incident_lab import IncidentLabGenerator
from app.integrations.razorpay.client import razorpay_client
from app.integrations.razorpay.mapper import RazorpayMapper
from app.integrations.razorpay.exceptions import RazorpayAuthError

router = APIRouter()

# =============================================================================
# HEALTH & SYSTEM STATUS
# =============================================================================

@router.get("/health")
def get_health():
    """Returns system health, database connection, and Razorpay configuration."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": "PostgreSQL",
        "razorpay_configured": razorpay_client.is_configured,
        "ai_provider": settings.AI_PROVIDER,
        "gemini_configured": bool(settings.GEMINI_API_KEY and not settings.GEMINI_API_KEY.startswith("YOUR_"))
    }

# =============================================================================
# DATA OBSERVABILITY & STATISTICS (POSTGRESQL-DERIVED)
# =============================================================================

@router.get("/stats")
def get_database_stats():
    """
    Returns actual row counts and status derived directly from PostgreSQL.
    Zero synthetic or hardcoded metrics.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) as cnt FROM merchants;")
    merchants_cnt = c.fetchone()["cnt"]
    
    c.execute("SELECT COUNT(*) as cnt FROM orders;")
    orders_cnt = c.fetchone()["cnt"]
    
    c.execute("SELECT COUNT(*) as cnt FROM payments;")
    payments_cnt = c.fetchone()["cnt"]
    
    c.execute("SELECT COUNT(*) as cnt FROM refunds;")
    refunds_cnt = c.fetchone()["cnt"]
    
    c.execute("SELECT COUNT(*) as cnt FROM webhook_events;")
    webhooks_cnt = c.fetchone()["cnt"]
    
    c.execute("SELECT COUNT(*) as cnt FROM incidents;")
    incidents_cnt = c.fetchone()["cnt"]
    
    c.close()
    conn.close()

    return {
        "database": "PostgreSQL (moneyops_v2)",
        "merchants": merchants_cnt,
        "orders": orders_cnt,
        "payments": payments_cnt,
        "refunds": refunds_cnt,
        "webhook_events": webhooks_cnt,
        "incidents": incidents_cnt,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/stats/sources")
def get_source_distribution():
    """
    Returns real breakdown of records by provenance source:
    - 'razorpay_test' (Live REST API)
    - 'razorpay_webhook' (Live Webhooks)
    - 'incident_lab' (Controlled Laboratory Generator)
    """
    conn = get_db_connection()
    c = conn.cursor()

    c.execute("SELECT source, COUNT(*) as count FROM payments GROUP BY source ORDER BY count DESC;")
    payments_by_source = {r["source"]: r["count"] for r in c.fetchall()}

    c.execute("SELECT source, COUNT(*) as count FROM orders GROUP BY source ORDER BY count DESC;")
    orders_by_source = {r["source"]: r["count"] for r in c.fetchall()}

    c.execute("SELECT source, COUNT(*) as count FROM refunds GROUP BY source ORDER BY count DESC;")
    refunds_by_source = {r["source"]: r["count"] for r in c.fetchall()}

    c.execute("SELECT source, COUNT(*) as count FROM webhook_events GROUP BY source ORDER BY count DESC;")
    webhooks_by_source = {r["source"]: r["count"] for r in c.fetchall()}

    c.close()
    conn.close()

    return {
        "payments": payments_by_source,
        "orders": orders_by_source,
        "refunds": refunds_by_source,
        "webhooks": webhooks_by_source
    }

# =============================================================================
# RAZORPAY TEST MODE REST INGESTION (ADAPTER -> CANONICAL PIPELINE)
# =============================================================================

@router.post("/razorpay/sync")
def sync_razorpay_data():
    """
    Calls official Razorpay REST APIs, maps entities into CanonicalEvents (source='razorpay_test'),
    and pushes them through the unified IngestionPipeline into PostgreSQL.
    """
    if not razorpay_client.is_configured:
        return {
            "status": "credentials_required",
            "message": "Razorpay API credentials not configured. Please set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env.",
            "configured": False,
            "orders_fetched": 0,
            "payments_fetched": 0,
            "refunds_fetched": 0
        }

    try:
        # 1. Fetch from Razorpay Test Mode APIs
        orders = razorpay_client.fetch_orders(count=20)
        payments = razorpay_client.fetch_payments(count=20)
        refunds = razorpay_client.fetch_refunds(count=20)

        # 2. Convert to CanonicalEvents
        canonical_events: List[CanonicalEvent] = []
        for o in orders:
            canonical_events.append(RazorpayMapper.order_to_canonical(o, source="razorpay_test"))
        for p in payments:
            canonical_events.append(RazorpayMapper.payment_to_canonical(p, source="razorpay_test"))
        for r in refunds:
            canonical_events.append(RazorpayMapper.refund_to_canonical(r, source="razorpay_test"))

        # 3. Route Through Shared IngestionPipeline
        ingest_stats = IngestionPipeline.ingest_batch(canonical_events)

        return {
            "status": "success",
            "source": "razorpay_test",
            "database": "PostgreSQL",
            "configured": True,
            "orders_fetched": len(orders),
            "payments_fetched": len(payments),
            "refunds_fetched": len(refunds),
            "orders_upserted": ingest_stats["orders"],
            "payments_upserted": ingest_stats["payments"],
            "refunds_upserted": ingest_stats["refunds"]
        }
    except RazorpayAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Synchronization failed: {str(e)}")

# =============================================================================
# RAZORPAY WEBHOOK INGESTION (ADAPTER -> CANONICAL PIPELINE)
# =============================================================================

@router.post("/webhooks/razorpay")
async def ingest_razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None, alias="X-Razorpay-Signature"),
    x_razorpay_event_id: Optional[str] = Header(None, alias="X-Razorpay-Event-Id")
):
    """
    Ingests real Razorpay Test Mode webhooks.
    Validates HMAC-SHA256, enforces idempotency, maps to CanonicalEvents (source='razorpay_webhook'),
    and routes through the shared IngestionPipeline.
    """
    raw_body = await request.body()
    return webhook_service.process_webhook(
        raw_body=raw_body,
        signature=x_razorpay_signature,
        header_event_id=x_razorpay_event_id
    )

# =============================================================================
# INCIDENT LAB INGESTION (GENERATOR -> CANONICAL PIPELINE)
# =============================================================================

class GenerateLabRequest(BaseModel):
    seed: int = 42
    payments: int = 1000
    merchants: int = 10
    anomaly: str = "none"  # "none", "gateway_spike", "refund_spike", "duplicate_refund", "webhook_retry"

@router.post("/incident-lab/generate")
def generate_incident_lab_data(req: GenerateLabRequest):
    """
    Generates reproducible financial lifecycle events and routes them through
    the shared IngestionPipeline with source='incident_lab'.
    """
    try:
        summary = IncidentLabGenerator.generate_dataset(
            seed=req.seed,
            num_payments=req.payments,
            num_merchants=req.merchants,
            anomaly_type=req.anomaly
        )
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Incident Lab generation failed: {str(e)}")

# =============================================================================
# DATA ENTITY QUERY ENDPOINTS (POSTGRESQL)
# =============================================================================

@router.get("/payments")
def list_payments(limit: int = 50, source: Optional[str] = None):
    """Retrieves persisted payments from PostgreSQL."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if source:
        cursor.execute("SELECT * FROM payments WHERE source = %s ORDER BY created_at DESC LIMIT %s;", (source, limit))
    else:
        cursor.execute("SELECT * FROM payments ORDER BY created_at DESC LIMIT %s;", (limit,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/orders")
def list_orders(limit: int = 50, source: Optional[str] = None):
    """Retrieves persisted orders from PostgreSQL."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if source:
        cursor.execute("SELECT * FROM orders WHERE source = %s ORDER BY created_at DESC LIMIT %s;", (source, limit))
    else:
        cursor.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT %s;", (limit,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/refunds")
def list_refunds(limit: int = 50, source: Optional[str] = None):
    """Retrieves persisted refunds from PostgreSQL."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if source:
        cursor.execute("SELECT * FROM refunds WHERE source = %s ORDER BY created_at DESC LIMIT %s;", (source, limit))
    else:
        cursor.execute("SELECT * FROM refunds ORDER BY created_at DESC LIMIT %s;", (limit,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/webhooks")
def list_webhooks(limit: int = 50):
    """Retrieves persisted webhook events from PostgreSQL."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM webhook_events ORDER BY received_at DESC LIMIT %s;", (limit,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/incidents")
def list_incidents():
    """Retrieves active incidents from PostgreSQL."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM incidents ORDER BY detected_at DESC;")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(r) for r in rows]
