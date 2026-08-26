import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.engine.database import get_db_connection

class CanonicalEvent(BaseModel):
    """
    Unified, standardized representation of any financial lifecycle event
    originating from Real Razorpay REST API, Real Razorpay Webhooks, or Incident Lab.
    """
    canonical_id: str = Field(default_factory=lambda: f"can_{uuid.uuid4().hex[:12]}")
    source: str  # "razorpay_test", "razorpay_webhook", "incident_lab"
    event_type: str  # e.g., "order.created", "order.paid", "payment.captured", "payment.failed", "refund.processed", "webhook.received"
    entity_type: str  # "merchant", "order", "payment", "refund", "webhook"
    entity_id: str
    merchant_id: str
    amount: float = 0.0  # In INR decimal float (not paise)
    currency: str = "INR"
    status: str = "created"  # "created", "paid", "captured", "failed", "processed", "received"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    payload: Dict[str, Any] = Field(default_factory=dict)

    def validate_invariants(self) -> None:
        """Enforces fundamental financial data invariants."""
        if self.amount < 0:
            raise ValueError(f"Event {self.canonical_id}: amount cannot be negative ({self.amount})")
        if not self.entity_id:
            raise ValueError(f"Event {self.canonical_id}: entity_id cannot be empty")
        if not self.merchant_id:
            raise ValueError(f"Event {self.canonical_id}: merchant_id cannot be empty")
        if self.source not in ["razorpay_test", "razorpay_webhook", "incident_lab"]:
            raise ValueError(f"Event {self.canonical_id}: invalid source '{self.source}'")


class IngestionPipeline:
    """
    Central, shared ingestion pipeline for all incoming financial events.
    Validates canonical invariants, ensures relational parent entity integrity,
    and performs idempotent upserts into PostgreSQL.
    """

    @classmethod
    def ingest_event(cls, event: CanonicalEvent, conn=None) -> Dict[str, Any]:
        """Ingests a single canonical event into PostgreSQL."""
        event.validate_invariants()
        
        close_conn_at_end = False
        if conn is None:
            conn = get_db_connection()
            close_conn_at_end = True
            
        cursor = conn.cursor()
        now_str = datetime.utcnow().isoformat()
        res_info = {"canonical_id": event.canonical_id, "entity_type": event.entity_type, "entity_id": event.entity_id, "status": "persisted"}

        # 1. Ensure Merchant Exists
        cursor.execute("""
            INSERT INTO merchants (merchant_id, name, category, baseline_refund_rate, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (merchant_id) DO NOTHING;
        """, (
            event.merchant_id,
            event.payload.get("merchant_name", f"Merchant {event.merchant_id[-8:]}"),
            event.payload.get("category", "ecommerce"),
            event.payload.get("baseline_refund_rate", 0.015),
            event.timestamp
        ))

        # 2. Ingest by Entity Type
        if event.entity_type == "order":
            cursor.execute("""
                INSERT INTO orders (order_id, merchant_id, amount, currency, status, source, created_at, ingested_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (order_id) DO UPDATE SET
                    amount = EXCLUDED.amount,
                    currency = EXCLUDED.currency,
                    status = EXCLUDED.status,
                    ingested_at = EXCLUDED.ingested_at;
            """, (
                event.entity_id, event.merchant_id, event.amount,
                event.currency, event.status, event.source,
                event.timestamp, now_str
            ))

        elif event.entity_type == "payment":
            order_id = event.payload.get("order_id")
            if order_id:
                cursor.execute("SELECT order_id FROM orders WHERE order_id = %s;", (order_id,))
                if not cursor.fetchone():
                    # Create placeholder order to satisfy relational FK
                    cursor.execute("""
                        INSERT INTO orders (order_id, merchant_id, amount, currency, status, source, created_at, ingested_at)
                        VALUES (%s, %s, %s, %s, 'paid', %s, %s, %s)
                        ON CONFLICT (order_id) DO NOTHING;
                    """, (order_id, event.merchant_id, event.amount, event.currency, event.source, event.timestamp, now_str))

            cursor.execute("""
                INSERT INTO payments (
                    payment_id, order_id, merchant_id, amount, currency, status,
                    method, gateway, failure_code, error_description, retry_count,
                    source, created_at, captured_at, ingested_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (payment_id) DO UPDATE SET
                    amount = EXCLUDED.amount,
                    currency = EXCLUDED.currency,
                    status = EXCLUDED.status,
                    method = EXCLUDED.method,
                    gateway = EXCLUDED.gateway,
                    failure_code = EXCLUDED.failure_code,
                    error_description = EXCLUDED.error_description,
                    retry_count = EXCLUDED.retry_count,
                    captured_at = EXCLUDED.captured_at,
                    ingested_at = EXCLUDED.ingested_at;
            """, (
                event.entity_id,
                order_id,
                event.merchant_id,
                event.amount,
                event.currency,
                event.status,
                event.payload.get("method", "card"),
                event.payload.get("gateway", "Razorpay_Gateway"),
                event.payload.get("failure_code"),
                event.payload.get("error_description"),
                event.payload.get("retry_count", 0),
                event.source,
                event.timestamp,
                event.payload.get("captured_at") or (event.timestamp if event.status == "captured" else None),
                now_str
            ))

        elif event.entity_type == "refund":
            payment_id = event.payload.get("payment_id") or f"pay_parent_{event.entity_id}"
            cursor.execute("SELECT payment_id FROM payments WHERE payment_id = %s;", (payment_id,))
            if not cursor.fetchone():
                # Create placeholder payment to satisfy relational FK
                cursor.execute("""
                    INSERT INTO payments (
                        payment_id, merchant_id, amount, currency, status, method, gateway, source, created_at, ingested_at
                    ) VALUES (%s, %s, %s, %s, 'captured', 'card', 'Razorpay_Gateway', %s, %s, %s)
                    ON CONFLICT (payment_id) DO NOTHING;
                """, (payment_id, event.merchant_id, event.amount, event.currency, event.source, event.timestamp, now_str))

            cursor.execute("""
                INSERT INTO refunds (
                    refund_id, payment_id, merchant_id, amount, currency, status,
                    speed, failure_reason, source, created_at, processed_at, ingested_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (refund_id) DO UPDATE SET
                    amount = EXCLUDED.amount,
                    currency = EXCLUDED.currency,
                    status = EXCLUDED.status,
                    speed = EXCLUDED.speed,
                    failure_reason = EXCLUDED.failure_reason,
                    processed_at = EXCLUDED.processed_at,
                    ingested_at = EXCLUDED.ingested_at;
            """, (
                event.entity_id,
                payment_id,
                event.merchant_id,
                event.amount,
                event.currency,
                event.status,
                event.payload.get("speed", "normal"),
                event.payload.get("failure_reason"),
                event.source,
                event.timestamp,
                event.payload.get("processed_at") or event.timestamp,
                now_str
            ))

        elif event.entity_type == "webhook":
            external_event_id = event.payload.get("external_event_id") or event.entity_id
            cursor.execute("""
                INSERT INTO webhook_events (
                    event_id, external_event_id, event_type, entity_id,
                    payload_json, signature_valid, delivery_status, source, received_at, processed_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (external_event_id) DO UPDATE SET
                    delivery_status = EXCLUDED.delivery_status,
                    processed_at = EXCLUDED.processed_at;
            """, (
                event.canonical_id,
                external_event_id,
                event.event_type,
                event.entity_id,
                json.dumps(event.payload),
                1 if event.payload.get("signature_valid", True) else 0,
                event.status,
                event.source,
                event.timestamp,
                now_str
            ))

        if close_conn_at_end:
            conn.commit()
            cursor.close()
            conn.close()

        return res_info

    @classmethod
    def ingest_batch(cls, events: List[CanonicalEvent]) -> Dict[str, int]:
        """Ingests a batch of canonical events inside a single transaction for high performance."""
        if not events:
            return {"total": 0, "orders": 0, "payments": 0, "refunds": 0, "webhooks": 0}

        conn = get_db_connection()
        counts = {"total": 0, "orders": 0, "payments": 0, "refunds": 0, "webhooks": 0, "merchants": 0}
        
        try:
            for event in events:
                cls.ingest_event(event, conn=conn)
                counts["total"] += 1
                if event.entity_type == "order":
                    counts["orders"] += 1
                elif event.entity_type == "payment":
                    counts["payments"] += 1
                elif event.entity_type == "refund":
                    counts["refunds"] += 1
                elif event.entity_type == "webhook":
                    counts["webhooks"] += 1
                elif event.entity_type == "merchant":
                    counts["merchants"] += 1

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

        return counts

ingestion_pipeline = IngestionPipeline()
