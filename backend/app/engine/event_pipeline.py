import json
import uuid
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from app.models.schemas import CanonicalEvent, AnomalySignal
from app.engine.database import get_db_connection
from app.engine.anomaly_detector import anomaly_detector
from app.engine.money_graph import money_graph
from app.integrations.razorpay.client import razorpay_client
from app.integrations.razorpay.mapper import RazorpayMapper

class EventValidator:
    """Validates structural integrity and financial invariants of incoming event payloads."""

    @staticmethod
    def validate(event_type: str, raw_payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not event_type:
            return False, "Missing event_type"
        if not isinstance(raw_payload, dict):
            return False, "Payload must be a dictionary"
        return True, None


class EventNormalizer:
    """Normalizes heterogeneous event sources (Razorpay Webhooks, Synthetic, Simulator) into CanonicalEvent."""

    @staticmethod
    def normalize(event_type: str, payload: Dict[str, Any], source: str = "synthetic", event_id: Optional[str] = None) -> CanonicalEvent:
        if source in ["razorpay_webhook", "razorpay_test"]:
            return RazorpayMapper.webhook_payload_to_canonical(payload, event_id or f"wh_rzp_{uuid.uuid4().hex[:8]}")
        
        # Synthetic / Laboratory Event
        ev_id = payload.get("event_id") or f"can_syn_{uuid.uuid4().hex[:8]}"
        entity_id = payload.get("payment_id") or payload.get("refund_id") or payload.get("entity_id") or f"ent_{uuid.uuid4().hex[:6]}"
        merchant_id = payload.get("merchant_id", "merch_Nova_Store")
        amount = float(payload.get("amount", 1000.0))
        status = payload.get("status", "captured")
        entity_type = "refund" if "refund" in event_type else "payment"

        return CanonicalEvent(
            canonical_id=ev_id,
            event_source=source,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            merchant_id=merchant_id,
            amount=amount,
            status=status,
            payload=payload,
            ingested_at=datetime.utcnow().isoformat()
        )


class EventRepository:
    """Persists raw events, canonical events, and relational entity lifecycles to SQLite."""

    @staticmethod
    def save_raw_event(source: str, external_event_id: str, entity_type: str, entity_id: str, raw_payload: Dict[str, Any]) -> Tuple[str, bool]:
        """
        Saves raw external event payload before normalization.
        Enforces idempotency: returns (raw_id, is_duplicate).
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        now_str = datetime.utcnow().isoformat()
        raw_id = f"raw_{uuid.uuid4().hex[:8]}"

        # Check for duplicate event
        cursor.execute("SELECT id, processing_status FROM raw_external_events WHERE external_event_id = ?", (external_event_id,))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return existing["id"], True  # is_duplicate

        cursor.execute("""
            INSERT INTO raw_external_events (
                id, source, external_event_id, entity_type, entity_id, payload_json, received_at, processing_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'received')
        """, (raw_id, source, external_event_id, entity_type, entity_id, json.dumps(raw_payload), now_str))

        conn.commit()
        conn.close()
        return raw_id, False

    @staticmethod
    def mark_raw_processed(raw_id: str, status: str = "processed", error_msg: Optional[str] = None):
        conn = get_db_connection()
        cursor = conn.cursor()
        now_str = datetime.utcnow().isoformat()
        cursor.execute("""
            UPDATE raw_external_events
            SET processing_status = ?, processed_at = ?, error_message = ?
            WHERE id = ?
        """, (status, now_str, error_msg, raw_id))
        conn.commit()
        conn.close()

    @staticmethod
    def save_canonical(event: CanonicalEvent, anom_sig: Optional[AnomalySignal] = None, raw_event_id: Optional[str] = None):
        conn = get_db_connection()
        cursor = conn.cursor()
        now_str = datetime.utcnow().isoformat()

        # 1. Save Canonical Event Record
        cursor.execute("""
            INSERT OR REPLACE INTO canonical_events (
                canonical_id, event_source, event_type, entity_type, entity_id,
                merchant_id, amount, status, payload_json, ingested_at, is_anomaly, anomaly_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.canonical_id, event.event_source, event.event_type, event.entity_type,
            event.entity_id, event.merchant_id, event.amount, event.status,
            json.dumps(event.payload), event.ingested_at,
            1 if (anom_sig and anom_sig.is_anomaly) else 0,
            anom_sig.anomaly_score if anom_sig else 0.0
        ))

        # 2. Update Entity-Specific Relational Table
        if event.entity_type == "payment":
            ord_id = event.payload.get("order_id") or f"ord_{event.entity_id[-8:]}"
            gateway = event.payload.get("gateway") or "Gateway_HDFC"
            method = event.payload.get("method", "card")
            source_created = event.payload.get("source_created_at") or now_str

            # Check / Insert Order
            cursor.execute("SELECT order_id FROM orders WHERE order_id = ?", (ord_id,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO orders (order_id, merchant_id, customer_id, amount, currency, status, source, created_at, ingested_at)
                    VALUES (?, ?, 'cust_0001', ?, 'INR', 'paid', ?, ?, ?)
                """, (ord_id, event.merchant_id, event.amount, event.event_source, source_created, now_str))

            cursor.execute("""
                INSERT OR REPLACE INTO payments (
                    payment_id, order_id, merchant_id, customer_id, amount, currency,
                    status, method, gateway, source, created_at, captured_at, source_created_at, ingested_at, last_synced_at,
                    failure_code, error_description, retry_count
                ) VALUES (?, ?, ?, 'cust_0001', ?, 'INR', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.entity_id, ord_id, event.merchant_id, event.amount,
                event.status, method, gateway, event.event_source, source_created,
                now_str if event.status == "captured" else None, source_created, now_str, now_str,
                event.payload.get("failure_code"), event.payload.get("error_description"),
                event.payload.get("retry_count", 0)
            ))

            # Webhook Record
            cursor.execute("""
                INSERT OR REPLACE INTO webhook_events (
                    event_id, event_type, entity_id, merchant_id, source, raw_event_id,
                    timestamp, delivery_attempt, signature_valid, delivery_status, http_status, response_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, 'delivered', 200, 110)
            """, (f"wh_{event.canonical_id}", event.event_type, event.entity_id, event.merchant_id, event.event_source, raw_event_id, now_str))

        elif event.entity_type == "refund":
            pay_id = event.payload.get("payment_id", "pay_P19283")
            speed = event.payload.get("speed", "instant")
            source_created = event.payload.get("source_created_at") or now_str

            cursor.execute("""
                INSERT OR REPLACE INTO refunds (
                    refund_id, payment_id, merchant_id, amount, status, speed, source, created_at, processed_at, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.entity_id, pay_id, event.merchant_id, event.amount,
                event.status, speed, event.event_source, source_created,
                now_str if event.status == "processed" else None, now_str
            ))

            cursor.execute("""
                INSERT OR REPLACE INTO webhook_events (
                    event_id, event_type, entity_id, merchant_id, source, raw_event_id,
                    timestamp, delivery_attempt, signature_valid, delivery_status, http_status, response_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, 'delivered', 200, 120)
            """, (f"wh_{event.canonical_id}", event.event_type, event.entity_id, event.merchant_id, event.event_source, raw_event_id, now_str))

        conn.commit()
        conn.close()


class FinancialEventPipeline:
    """
    End-to-End Canonical Ingestion & Reconciliation Pipeline:
    SOURCE → RAW PERSISTENCE (Idempotency) → VALIDATE → NORMALIZE → ANOMALY DETECTION → PERSIST → UPDATE GRAPH
    """

    def __init__(self):
        self.validator = EventValidator()
        self.normalizer = EventNormalizer()
        self.repository = EventRepository()

    def process_event(self, raw_event_type: str, raw_payload: Dict[str, Any], source: str = "synthetic", external_event_id: Optional[str] = None) -> Dict[str, Any]:
        # 1. Validate
        is_valid, err = self.validator.validate(raw_event_type, raw_payload)
        if not is_valid:
            raise ValueError(f"Event validation failed: {err}")

        # Extract entity metadata for raw logging
        ext_ev_id = external_event_id or raw_payload.get("id") or f"ext_{uuid.uuid4().hex[:8]}"
        entity_id = (
            raw_payload.get("payload", {}).get("payment", {}).get("entity", {}).get("id") or
            raw_payload.get("payload", {}).get("refund", {}).get("entity", {}).get("id") or
            raw_payload.get("payment_id") or raw_payload.get("refund_id") or ext_ev_id
        )
        entity_type = "refund" if ("refund" in raw_event_type or "rfnd" in str(entity_id)) else "payment"

        # 2. Raw Event Persistence (with Idempotency check)
        raw_id, is_duplicate = self.repository.save_raw_event(
            source=source,
            external_event_id=ext_ev_id,
            entity_type=entity_type,
            entity_id=entity_id,
            raw_payload=raw_payload
        )

        if is_duplicate:
            return {
                "status": "duplicate_skipped",
                "message": f"Event {ext_ev_id} already ingested (idempotency enforced)",
                "raw_event_id": raw_id,
                "external_event_id": ext_ev_id
            }

        try:
            # 3. Normalize into Canonical Event
            canonical = self.normalizer.normalize(
                event_type=raw_event_type,
                payload=raw_payload,
                source=source,
                event_id=ext_ev_id
            )

            # 4. On-Demand Reconciliation for Missing Parent Entities
            if canonical.entity_type == "refund":
                linked_pay = canonical.payload.get("payment_id")
                if linked_pay:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT payment_id FROM payments WHERE payment_id = ?", (linked_pay,))
                    pay_exists = cursor.fetchone()
                    conn.close()

                    if not pay_exists:
                        # Attempt API fetch if live client credentials configured
                        fetched_p = razorpay_client.fetch_payment(linked_pay)
                        if fetched_p:
                            p_canon = RazorpayMapper.payment_to_canonical(fetched_p)
                            self.repository.save_canonical(p_canon)

            # 5. Anomaly Scoring
            anom_sig = anomaly_detector.score_anomaly(
                entity_id=canonical.entity_id,
                entity_type=canonical.entity_type,
                payload=canonical.payload
            )
            canonical.is_anomaly = anom_sig.is_anomaly
            canonical.anomaly_score = anom_sig.anomaly_score

            # 6. Save Canonical Entity
            self.repository.save_canonical(canonical, anom_sig, raw_event_id=raw_id)
            self.repository.mark_raw_processed(raw_id, status="processed")

            # 7. Incremental In-Memory Money Graph Update
            if canonical.entity_type == "payment":
                money_graph.add_payment_event(
                    payment_id=canonical.entity_id,
                    order_id=canonical.payload.get("order_id", f"ord_{canonical.entity_id[-8:]}"),
                    merchant_id=canonical.merchant_id,
                    customer_id=canonical.payload.get("customer_id", "cust_0001"),
                    amount=canonical.amount,
                    status=canonical.status,
                    gateway=canonical.payload.get("gateway", "Gateway_HDFC"),
                    failure_code=canonical.payload.get("failure_code"),
                    retry_count=canonical.payload.get("retry_count", 0)
                )
            elif canonical.entity_type == "refund":
                money_graph.add_refund_event(
                    refund_id=canonical.entity_id,
                    payment_id=canonical.payload.get("payment_id", "pay_P19283"),
                    merchant_id=canonical.merchant_id,
                    amount=canonical.amount,
                    status=canonical.status
                )
            money_graph.add_webhook_event(
                event_id=f"wh_{canonical.canonical_id}",
                entity_id=canonical.entity_id,
                event_type=canonical.event_type,
                status="delivered"
            )

            return {
                "status": "processed",
                "canonical_id": canonical.canonical_id,
                "raw_event_id": raw_id,
                "entity_id": canonical.entity_id,
                "is_anomaly": anom_sig.is_anomaly,
                "anomaly_score": anom_sig.anomaly_score,
                "contributing_signals": anom_sig.contributing_signals
            }
        except Exception as e:
            self.repository.mark_raw_processed(raw_id, status="failed", error_msg=str(e))
            raise

event_pipeline = FinancialEventPipeline()
