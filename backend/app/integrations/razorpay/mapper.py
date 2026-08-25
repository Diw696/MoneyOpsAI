from datetime import datetime
from typing import Dict, Any, Optional
from app.integrations.razorpay.models import (
    RazorpayPaymentEntity, RazorpayOrderEntity, RazorpayRefundEntity
)

class RazorpayMapper:
    """
    Transforms official Razorpay API responses into clean internal relational entity dictionaries.
    Ensures strict conversion of amounts from paise to INR, Unix timestamps to ISO strings,
    and extraction of acquirer gateway metadata.
    """

    @staticmethod
    def payment_to_db_dict(p: RazorpayPaymentEntity, source: str = "razorpay_test") -> Dict[str, Any]:
        amount_inr = round(p.amount / 100.0, 2)
        created_iso = datetime.utcfromtimestamp(p.created_at).isoformat()
        now_iso = datetime.utcnow().isoformat()
        merchant_id = p.notes.get("merchant_id", "merch_Nova_Store") if isinstance(p.notes, dict) else "merch_Nova_Store"
        gateway = p.acquirer_data.get("bank") or p.bank or "Razorpay_Gateway"

        return {
            "payment_id": p.id,
            "order_id": p.order_id,
            "merchant_id": merchant_id,
            "amount": amount_inr,
            "currency": p.currency or "INR",
            "status": p.status,
            "method": p.method or "card",
            "gateway": gateway,
            "failure_code": p.error_code,
            "error_description": p.error_description,
            "retry_count": 0,
            "source": source,
            "created_at": created_iso,
            "captured_at": created_iso if p.status == "captured" else None,
            "ingested_at": now_iso
        }

    @staticmethod
    def order_to_db_dict(o: RazorpayOrderEntity, source: str = "razorpay_test") -> Dict[str, Any]:
        amount_inr = round(o.amount / 100.0, 2)
        created_iso = datetime.utcfromtimestamp(o.created_at).isoformat()
        now_iso = datetime.utcnow().isoformat()
        merchant_id = o.notes.get("merchant_id", "merch_Nova_Store") if isinstance(o.notes, dict) else "merch_Nova_Store"

        return {
            "order_id": o.id,
            "merchant_id": merchant_id,
            "amount": amount_inr,
            "currency": o.currency or "INR",
            "status": o.status,
            "source": source,
            "created_at": created_iso,
            "ingested_at": now_iso
        }

    @staticmethod
    def refund_to_db_dict(r: RazorpayRefundEntity, source: str = "razorpay_test") -> Dict[str, Any]:
        amount_inr = round(r.amount / 100.0, 2)
        created_iso = datetime.utcfromtimestamp(r.created_at).isoformat()
        now_iso = datetime.utcnow().isoformat()
        merchant_id = r.notes.get("merchant_id", "merch_Nova_Store") if isinstance(r.notes, dict) else "merch_Nova_Store"

        return {
            "refund_id": r.id,
            "payment_id": r.payment_id,
            "merchant_id": merchant_id,
            "amount": amount_inr,
            "currency": r.currency or "INR",
            "status": r.status,
            "speed": r.speed_processed or "normal",
            "failure_reason": None,
            "source": source,
            "created_at": created_iso,
            "processed_at": created_iso if r.status == "processed" else None,
            "ingested_at": now_iso
        }
