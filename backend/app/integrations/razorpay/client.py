import hmac
import hashlib
import json
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.core.config import settings
from app.integrations.razorpay.exceptions import (
    RazorpayAuthError, RazorpayNotFoundError, RazorpayRateLimitError,
    RazorpayAPIError, RazorpaySignatureVerificationError
)
from app.integrations.razorpay.models import (
    RazorpayPaymentEntity, RazorpayOrderEntity, RazorpayRefundEntity
)

class RazorpayClient:
    """
    Official Razorpay REST API Client for Test Mode.
    Provides authenticated access to Payments, Orders, Refunds, and Webhook verification.
    """

    def __init__(self, key_id: Optional[str] = None, key_secret: Optional[str] = None, base_url: str = "https://api.razorpay.com/v1"):
        self.key_id = key_id or settings.RAZORPAY_KEY_ID
        self.key_secret = key_secret or settings.RAZORPAY_KEY_SECRET
        self.webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
        self.base_url = base_url.rstrip("/")
        self.timeout = 15.0

    @property
    def is_configured(self) -> bool:
        """Returns True if legitimate Razorpay API credentials are provided."""
        return bool(self.key_id and self.key_secret and not self.key_id.startswith("rzp_test_YOUR"))

    def _get_auth(self) -> Optional[tuple]:
        if self.is_configured:
            return (self.key_id, self.key_secret)
        return None

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            raise RazorpayAuthError("Invalid or unauthorized Razorpay API credentials (KEY_ID / KEY_SECRET)")
        elif response.status_code == 404:
            raise RazorpayNotFoundError(f"Requested Razorpay resource not found at {response.url}")
        elif response.status_code == 429:
            raise RazorpayRateLimitError("Razorpay API rate limit exceeded")
        else:
            try:
                err_data = response.json()
                msg = err_data.get("error", {}).get("description") or response.text
            except Exception:
                err_data = {}
                msg = response.text
            raise RazorpayAPIError(status_code=response.status_code, message=msg, error_data=err_data)

    def verify_webhook_signature(self, raw_body: bytes, signature: str, secret: Optional[str] = None) -> bool:
        """Verifies Razorpay webhook signature using HMAC-SHA256."""
        sec = secret or self.webhook_secret
        if not sec or not signature:
            return False
        expected = hmac.new(sec.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    # -------------------------------------------------------------------------
    # Payments API: GET /v1/payments, GET /v1/payments/{id}
    # -------------------------------------------------------------------------

    def fetch_payments(self, count: int = 20, skip: int = 0, from_timestamp: Optional[int] = None, to_timestamp: Optional[int] = None) -> List[RazorpayPaymentEntity]:
        """Fetches payments from Razorpay API."""
        auth = self._get_auth()
        if not auth:
            return []

        params: Dict[str, Any] = {"count": count, "skip": skip}
        if from_timestamp is not None and from_timestamp >= 946684800:
            params["from"] = from_timestamp
        if to_timestamp is not None and to_timestamp >= 946684800:
            params["to"] = to_timestamp

        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(f"{self.base_url}/payments", auth=auth, params=params)
            data = self._handle_response(res)
            return [RazorpayPaymentEntity(**item) for item in data.get("items", [])]

    def fetch_payment(self, payment_id: str) -> Optional[RazorpayPaymentEntity]:
        """Fetches an individual payment by ID."""
        auth = self._get_auth()
        if not auth:
            return None

        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(f"{self.base_url}/payments/{payment_id}", auth=auth)
            data = self._handle_response(res)
            return RazorpayPaymentEntity(**data)

    # -------------------------------------------------------------------------
    # Orders API: GET /v1/orders, GET /v1/orders/{id}, GET /v1/orders/{id}/payments
    # -------------------------------------------------------------------------

    def fetch_orders(self, count: int = 20, skip: int = 0, from_timestamp: Optional[int] = None) -> List[RazorpayOrderEntity]:
        """Fetches orders from Razorpay API."""
        auth = self._get_auth()
        if not auth:
            return []

        params: Dict[str, Any] = {"count": count, "skip": skip}
        if from_timestamp is not None and from_timestamp >= 946684800:
            params["from"] = from_timestamp

        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(f"{self.base_url}/orders", auth=auth, params=params)
            data = self._handle_response(res)
            return [RazorpayOrderEntity(**item) for item in data.get("items", [])]

    def fetch_order(self, order_id: str) -> Optional[RazorpayOrderEntity]:
        """Fetches an order by ID."""
        auth = self._get_auth()
        if not auth:
            return None

        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(f"{self.base_url}/orders/{order_id}", auth=auth)
            data = self._handle_response(res)
            return RazorpayOrderEntity(**data)

    def fetch_order_payments(self, order_id: str) -> List[RazorpayPaymentEntity]:
        """Fetches all payments associated with an order."""
        auth = self._get_auth()
        if not auth:
            return []

        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(f"{self.base_url}/orders/{order_id}/payments", auth=auth)
            data = self._handle_response(res)
            return [RazorpayPaymentEntity(**item) for item in data.get("items", [])]

    # -------------------------------------------------------------------------
    # Refunds API: GET /v1/refunds, GET /v1/refunds/{id}, POST /v1/payments/{id}/refund
    # -------------------------------------------------------------------------

    def fetch_refunds(self, count: int = 20, skip: int = 0, from_timestamp: Optional[int] = None) -> List[RazorpayRefundEntity]:
        """Fetches refunds from Razorpay API."""
        auth = self._get_auth()
        if not auth:
            return []

        params: Dict[str, Any] = {"count": count, "skip": skip}
        if from_timestamp is not None and from_timestamp >= 946684800:
            params["from"] = from_timestamp

        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(f"{self.base_url}/refunds", auth=auth, params=params)
            data = self._handle_response(res)
            return [RazorpayRefundEntity(**item) for item in data.get("items", [])]

    def fetch_refund(self, refund_id: str) -> Optional[RazorpayRefundEntity]:
        """Fetches a single refund by ID."""
        auth = self._get_auth()
        if not auth:
            return None

        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(f"{self.base_url}/refunds/{refund_id}", auth=auth)
            data = self._handle_response(res)
            return RazorpayRefundEntity(**data)

    def fetch_payment_refunds(self, payment_id: str) -> List[RazorpayRefundEntity]:
        """Fetches all refunds issued against a specific payment."""
        auth = self._get_auth()
        if not auth:
            return []

        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(f"{self.base_url}/payments/{payment_id}/refunds", auth=auth)
            data = self._handle_response(res)
            return [RazorpayRefundEntity(**item) for item in data.get("items", [])]

    def create_test_refund(self, payment_id: str, amount_inr: Optional[float] = None, notes: Optional[Dict[str, Any]] = None) -> Optional[RazorpayRefundEntity]:
        """Creates a refund in Test Mode against a payment."""
        auth = self._get_auth()
        if not auth:
            return None

        body: Dict[str, Any] = {"notes": notes or {"created_by": "MoneyOps_ActionGovernor"}}
        if amount_inr is not None:
            body["amount"] = int(amount_inr * 100)  # INR to paise

        with httpx.Client(timeout=self.timeout) as client:
            res = client.post(f"{self.base_url}/payments/{payment_id}/refund", auth=auth, json=body)
            data = self._handle_response(res)
            return RazorpayRefundEntity(**data)

razorpay_client = RazorpayClient()
