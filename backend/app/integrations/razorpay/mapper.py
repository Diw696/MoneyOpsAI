import uuid
from datetime import datetime
from typing import Dict, Any
from app.integrations.razorpay.models import RazorpayPaymentEntity, RazorpayOrderEntity, RazorpayRefundEntity
from app.engine.pipeline import CanonicalEvent

class RazorpayMapper:
    """
    Maps official Razorpay Test Mode API and Webhook entities into canonical representations.
    """

    @staticmethod
    def paise_to_inr(paise: int) -> float:
        """Converts integer paise to float INR (e.g. 250000 paise -> 2500.00 INR)."""
        return round(paise / 100.0, 2)

    @staticmethod
    def unix_to_iso(timestamp: int) -> str:
        """Converts Unix epoch timestamp to ISO 8601 string."""
        return datetime.utcfromtimestamp(timestamp).isoformat()

    @classmethod
    def order_to_canonical(cls, order: RazorpayOrderEntity, source: str = "razorpay_test") -> CanonicalEvent:
        """Maps a RazorpayOrderEntity to CanonicalEvent."""
        created_iso = cls.unix_to_iso(order.created_at)
        merchant_id = order.notes.get("merchant_id", "merch_Nova_Store") if order.notes else "merch_Nova_Store"
        
        return CanonicalEvent(
            canonical_id=f"can_ord_{order.id}",
            source=source,
            event_type="order.created" if order.status == "created" else "order.paid",
            entity_type="order",
            entity_id=order.id,
            merchant_id=merchant_id,
            amount=cls.paise_to_inr(order.amount),
            currency=order.currency or "INR",
            status=order.status,
            timestamp=created_iso,
            payload={
                "receipt": order.receipt,
                "amount_paid": cls.paise_to_inr(order.amount_paid or 0),
                "amount_due": cls.paise_to_inr(order.amount_due or order.amount),
                "notes": order.notes or {}
            }
        )

    @classmethod
    def payment_to_canonical(cls, payment: RazorpayPaymentEntity, source: str = "razorpay_test") -> CanonicalEvent:
        """Maps a RazorpayPaymentEntity to CanonicalEvent."""
        created_iso = cls.unix_to_iso(payment.created_at)
        captured_iso = cls.unix_to_iso(payment.created_at) if payment.status == "captured" else None
        merchant_id = payment.notes.get("merchant_id", "merch_Nova_Store") if payment.notes else "merch_Nova_Store"
        
        gateway = "Razorpay_Gateway"
        if payment.acquirer_data and "bank" in payment.acquirer_data:
            gateway = f"Gateway_{payment.acquirer_data['bank']}"

        return CanonicalEvent(
            canonical_id=f"can_pay_{payment.id}",
            source=source,
            event_type=f"payment.{payment.status}",
            entity_type="payment",
            entity_id=payment.id,
            merchant_id=merchant_id,
            amount=cls.paise_to_inr(payment.amount),
            currency=payment.currency or "INR",
            status=payment.status,
            timestamp=created_iso,
            payload={
                "order_id": payment.order_id,
                "method": payment.method or "card",
                "gateway": gateway,
                "failure_code": payment.error_code,
                "error_description": payment.error_description,
                "retry_count": 0,
                "captured_at": captured_iso,
                "notes": payment.notes or {}
            }
        )

    @classmethod
    def refund_to_canonical(cls, refund: RazorpayRefundEntity, source: str = "razorpay_test") -> CanonicalEvent:
        """Maps a RazorpayRefundEntity to CanonicalEvent."""
        created_iso = cls.unix_to_iso(refund.created_at)
        merchant_id = refund.notes.get("merchant_id", "merch_Nova_Store") if refund.notes else "merch_Nova_Store"

        return CanonicalEvent(
            canonical_id=f"can_rfnd_{refund.id}",
            source=source,
            event_type=f"refund.{refund.status}",
            entity_type="refund",
            entity_id=refund.id,
            merchant_id=merchant_id,
            amount=cls.paise_to_inr(refund.amount),
            currency=refund.currency or "INR",
            status=refund.status,
            timestamp=created_iso,
            payload={
                "payment_id": refund.payment_id,
                "speed": refund.speed_processed or "normal",
                "failure_reason": None,
                "processed_at": created_iso if refund.status == "processed" else None,
                "notes": refund.notes or {}
            }
        )

    # Legacy dictionary helpers (for backward compatibility)
    @classmethod
    def order_to_db_dict(cls, order: RazorpayOrderEntity, source: str = "razorpay_test") -> Dict[str, Any]:
        can = cls.order_to_canonical(order, source=source)
        return {
            "order_id": can.entity_id,
            "merchant_id": can.merchant_id,
            "amount": can.amount,
            "currency": can.currency,
            "status": can.status,
            "source": can.source,
            "created_at": can.timestamp,
            "ingested_at": datetime.utcnow().isoformat()
        }

    @classmethod
    def payment_to_db_dict(cls, payment: RazorpayPaymentEntity, source: str = "razorpay_test") -> Dict[str, Any]:
        can = cls.payment_to_canonical(payment, source=source)
        return {
            "payment_id": can.entity_id,
            "order_id": can.payload.get("order_id"),
            "merchant_id": can.merchant_id,
            "amount": can.amount,
            "currency": can.currency,
            "status": can.status,
            "method": can.payload.get("method"),
            "gateway": can.payload.get("gateway"),
            "failure_code": can.payload.get("failure_code"),
            "error_description": can.payload.get("error_description"),
            "retry_count": can.payload.get("retry_count", 0),
            "source": can.source,
            "created_at": can.timestamp,
            "captured_at": can.payload.get("captured_at"),
            "ingested_at": datetime.utcnow().isoformat()
        }

    @classmethod
    def refund_to_db_dict(cls, refund: RazorpayRefundEntity, source: str = "razorpay_test") -> Dict[str, Any]:
        can = cls.refund_to_canonical(refund, source=source)
        return {
            "refund_id": can.entity_id,
            "payment_id": can.payload.get("payment_id"),
            "merchant_id": can.merchant_id,
            "amount": can.amount,
            "currency": can.currency,
            "status": can.status,
            "speed": can.payload.get("speed"),
            "failure_reason": can.payload.get("failure_reason"),
            "source": can.source,
            "created_at": can.timestamp,
            "processed_at": can.payload.get("processed_at"),
            "ingested_at": datetime.utcnow().isoformat()
        }
