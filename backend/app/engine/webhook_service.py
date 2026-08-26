import json
import uuid
import hmac
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import HTTPException
from app.core.config import settings
from app.engine.database import get_db_connection
from app.engine.pipeline import CanonicalEvent, IngestionPipeline
from app.integrations.razorpay.models import (
    RazorpayPaymentEntity, RazorpayOrderEntity, RazorpayRefundEntity
)
from app.integrations.razorpay.mapper import RazorpayMapper

class WebhookService:
    """
    Production-grade Razorpay Webhook Ingestion Adapter.
    Verifies HMAC-SHA256 signatures, enforces idempotency,
    maps incoming events to CanonicalEvents, and routes them through the shared IngestionPipeline.
    """

    @staticmethod
    def verify_signature(raw_body: bytes, signature: Optional[str]) -> bool:
        secret = settings.RAZORPAY_WEBHOOK_SECRET
        if not secret:
            return True
        if not signature:
            return False

        expected_signature = hmac.new(
            secret.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_signature, signature)

    @classmethod
    def process_webhook(
        cls,
        raw_body: bytes,
        signature: Optional[str],
        header_event_id: Optional[str] = None
    ) -> Dict[str, Any]:
        # 1. Verify HMAC Signature
        if settings.RAZORPAY_WEBHOOK_SECRET and not cls.verify_signature(raw_body, signature):
            raise HTTPException(status_code=400, detail="Invalid Razorpay webhook signature")

        # 2. Parse Raw JSON Payload
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=400, detail="Malformed JSON payload")

        event_type = payload.get("event", "unknown")
        external_event_id = header_event_id or payload.get("id") or payload.get("event_id") or f"evt_{uuid.uuid4().hex[:12]}"
        now_str = datetime.utcnow().isoformat()
        internal_event_id = f"wh_{uuid.uuid4().hex[:8]}"

        # 3. Check Idempotency in PostgreSQL
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT event_id, external_event_id, delivery_status FROM webhook_events WHERE external_event_id = %s;",
            (external_event_id,)
        )
        existing = cursor.fetchone()
        cursor.close()
        conn.close()

        if existing:
            return {
                "status": "duplicate_skipped",
                "message": f"Webhook event '{external_event_id}' already ingested (idempotency enforced)",
                "event_id": existing["event_id"],
                "external_event_id": existing["external_event_id"]
            }

        # 4. Extract Entity Payload & Construct Canonical Events
        payment_payload = payload.get("payload", {}).get("payment", {}).get("entity")
        order_payload = payload.get("payload", {}).get("order", {}).get("entity")
        refund_payload = payload.get("payload", {}).get("refund", {}).get("entity")

        entity_id = "unknown"
        merchant_id = "merch_Nova_Store"
        events_to_ingest = []

        if payment_payload:
            entity_id = payment_payload.get("id", "unknown")
            merchant_id = payment_payload.get("notes", {}).get("merchant_id", merchant_id)
            payment_entity = RazorpayPaymentEntity(**payment_payload)
            events_to_ingest.append(RazorpayMapper.payment_to_canonical(payment_entity, source="razorpay_webhook"))

        elif order_payload:
            entity_id = order_payload.get("id", "unknown")
            merchant_id = order_payload.get("notes", {}).get("merchant_id", merchant_id)
            order_entity = RazorpayOrderEntity(**order_payload)
            events_to_ingest.append(RazorpayMapper.order_to_canonical(order_entity, source="razorpay_webhook"))

        elif refund_payload:
            entity_id = refund_payload.get("id", "unknown")
            merchant_id = refund_payload.get("notes", {}).get("merchant_id", merchant_id)
            refund_entity = RazorpayRefundEntity(**refund_payload)
            events_to_ingest.append(RazorpayMapper.refund_to_canonical(refund_entity, source="razorpay_webhook"))

        # 5. Construct Canonical Webhook Event
        wh_event = CanonicalEvent(
            canonical_id=internal_event_id,
            source="razorpay_webhook",
            event_type=event_type,
            entity_type="webhook",
            entity_id=entity_id,
            merchant_id=merchant_id,
            amount=0.0,
            status="processed",
            timestamp=now_str,
            payload={
                "external_event_id": external_event_id,
                "signature_valid": True,
                "raw_payload": payload
            }
        )
        events_to_ingest.append(wh_event)

        # 6. Route Through Shared IngestionPipeline
        IngestionPipeline.ingest_batch(events_to_ingest)

        return {
            "status": "processed",
            "event_id": internal_event_id,
            "external_event_id": external_event_id,
            "event_type": event_type,
            "entity_id": entity_id,
            "source": "razorpay_webhook"
        }

webhook_service = WebhookService()
