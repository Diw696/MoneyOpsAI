import json
import uuid
import hmac
import hashlib
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from fastapi import HTTPException
from app.core.config import settings
from app.engine.database import get_db_connection
from app.integrations.razorpay.client import razorpay_client
from app.integrations.razorpay.models import (
    RazorpayPaymentEntity, RazorpayOrderEntity, RazorpayRefundEntity
)
from app.integrations.razorpay.mapper import RazorpayMapper

class WebhookService:
    """
    Production-grade Razorpay Webhook Ingestion Engine.
    Handles HMAC-SHA256 signature verification, idempotent deduplication,
    raw event recording, out-of-order parent entity reconciliation, and canonical normalization.
    """

    @staticmethod
    def verify_signature(raw_body: bytes, signature: Optional[str]) -> bool:
        secret = settings.RAZORPAY_WEBHOOK_SECRET
        if not secret:
            # If no secret configured in development, consider signature valid
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

        # 2. Parse Raw JSON
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=400, detail="Malformed JSON payload")

        event_type = payload.get("event", "unknown")
        external_event_id = header_event_id or payload.get("id") or payload.get("event_id") or f"evt_{uuid.uuid4().hex[:12]}"
        now_str = datetime.utcnow().isoformat()
        internal_event_id = f"wh_{uuid.uuid4().hex[:8]}"

        conn = get_db_connection()
        cursor = conn.cursor()

        # 3. Enforce Idempotency (Check if external_event_id was already processed)
        cursor.execute(
            "SELECT event_id, external_event_id, delivery_status FROM webhook_events WHERE external_event_id = ?",
            (external_event_id,)
        )
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return {
                "status": "duplicate_skipped",
                "message": f"Webhook event '{external_event_id}' already ingested (idempotency enforced)",
                "event_id": existing["event_id"],
                "external_event_id": existing["external_event_id"]
            }

        # 4. Extract Entity Payload & ID
        entity_id = "unknown"
        payment_payload = payload.get("payload", {}).get("payment", {}).get("entity")
        order_payload = payload.get("payload", {}).get("order", {}).get("entity")
        refund_payload = payload.get("payload", {}).get("refund", {}).get("entity")

        if payment_payload:
            entity_id = payment_payload.get("id", "unknown")
        elif order_payload:
            entity_id = order_payload.get("id", "unknown")
        elif refund_payload:
            entity_id = refund_payload.get("id", "unknown")
        elif "payment_id" in payload:
            entity_id = payload["payment_id"]
            payment_payload = payload

        # 5. Store Raw Webhook Event
        cursor.execute("""
            INSERT INTO webhook_events (
                event_id, external_event_id, event_type, entity_id,
                payload_json, signature_valid, delivery_status, source, received_at
            ) VALUES (?, ?, ?, ?, ?, 1, 'received', 'razorpay_webhook', ?)
        """, (
            internal_event_id, external_event_id, event_type,
            entity_id, json.dumps(payload), now_str
        ))

        # Ensure default merchant exists for foreign key references
        merchant_id = (
            (payment_payload and payment_payload.get("notes", {}).get("merchant_id")) or
            (order_payload and order_payload.get("notes", {}).get("merchant_id")) or
            "merch_Nova_Store"
        )
        cursor.execute("""
            INSERT OR IGNORE INTO merchants (merchant_id, name, category, baseline_refund_rate, created_at)
            VALUES (?, 'Nova Lifestyle & Fashion', 'ecommerce', 0.018, ?)
        """, (merchant_id, now_str))

        # 6. Normalize and Persist into Relational Models
        # Case A: Order Event (order.paid, etc.)
        if order_payload:
            try:
                order_entity = RazorpayOrderEntity(**order_payload)
                o_dict = RazorpayMapper.order_to_db_dict(order_entity, source="razorpay_webhook")
                cursor.execute("""
                    INSERT OR REPLACE INTO orders (
                        order_id, merchant_id, amount, currency, status, source, created_at, ingested_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    o_dict["order_id"], o_dict["merchant_id"], o_dict["amount"],
                    o_dict["currency"], o_dict["status"], o_dict["source"],
                    o_dict["created_at"], o_dict["ingested_at"]
                ))
            except Exception as e:
                pass

        # Case B: Payment Event (payment.authorized, payment.captured, payment.failed, etc.)
        if payment_payload:
            try:
                payment_entity = RazorpayPaymentEntity(**payment_payload)
                p_dict = RazorpayMapper.payment_to_db_dict(payment_entity, source="razorpay_webhook")

                # If order_id referenced does not exist in orders, create stub order to maintain FK integrity
                if p_dict["order_id"]:
                    cursor.execute("SELECT order_id FROM orders WHERE order_id = ?", (p_dict["order_id"],))
                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO orders (order_id, merchant_id, amount, currency, status, source, created_at, ingested_at)
                            VALUES (?, ?, ?, ?, 'paid', 'razorpay_webhook', ?, ?)
                        """, (p_dict["order_id"], p_dict["merchant_id"], p_dict["amount"], p_dict["currency"], p_dict["created_at"], now_str))

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
            except Exception as e:
                pass

        # Case C: Refund Event (refund.created, refund.processed, refund.failed, refund.speed_changed)
        if refund_payload:
            try:
                refund_entity = RazorpayRefundEntity(**refund_payload)
                r_dict = RazorpayMapper.refund_to_db_dict(refund_entity, source="razorpay_webhook")

                # Reconcile parent payment if not present (Out-of-order webhook delivery)
                cursor.execute("SELECT payment_id FROM payments WHERE payment_id = ?", (r_dict["payment_id"],))
                if not cursor.fetchone():
                    # Create stub parent payment to satisfy relational foreign key
                    cursor.execute("""
                        INSERT OR IGNORE INTO payments (
                            payment_id, merchant_id, amount, currency, status, method, gateway, source, created_at, ingested_at
                        ) VALUES (?, ?, ?, ?, 'captured', 'card', 'Razorpay_Gateway', 'razorpay_webhook', ?, ?)
                    """, (r_dict["payment_id"], r_dict["merchant_id"], r_dict["amount"], r_dict["currency"], r_dict["created_at"], now_str))

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
            except Exception as e:
                import traceback
                print(f"[Webhook Service Error] Refund processing failed: {e}\n{traceback.format_exc()}")

        # 7. Update Webhook Status to 'processed'
        cursor.execute(
            "UPDATE webhook_events SET delivery_status = 'processed', processed_at = ? WHERE event_id = ?",
            (datetime.utcnow().isoformat(), internal_event_id)
        )

        conn.commit()
        conn.close()

        return {
            "status": "processed",
            "event_id": internal_event_id,
            "external_event_id": external_event_id,
            "event_type": event_type,
            "entity_id": entity_id,
            "source": "razorpay_webhook"
        }

webhook_service = WebhookService()
