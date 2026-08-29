from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, field_validator

def clean_notes(v: Any) -> Dict[str, Any]:
    if isinstance(v, dict):
        return v
    return {}

class RazorpayPaymentEntity(BaseModel):
    id: str
    entity: str = "payment"
    amount: int  # in paise (e.g. 100000 = ₹1000.00)
    currency: str = "INR"
    status: str  # captured, failed, authorized, refunded, created
    order_id: Optional[str] = None
    invoice_id: Optional[str] = None
    international: Optional[bool] = False
    method: Optional[str] = "card"
    amount_refunded: Optional[int] = 0
    refund_status: Optional[str] = None
    captured: Optional[bool] = True
    description: Optional[str] = None
    card_id: Optional[str] = None
    bank: Optional[str] = None
    wallet: Optional[str] = None
    vpa: Optional[str] = None
    email: Optional[str] = None
    contact: Optional[str] = None
    notes: Union[Dict[str, Any], List[Any]] = Field(default_factory=dict)
    fee: Optional[int] = None
    tax: Optional[int] = None
    error_code: Optional[str] = None
    error_description: Optional[str] = None
    error_source: Optional[str] = None
    error_step: Optional[str] = None
    error_reason: Optional[str] = None
    acquirer_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: int  # Unix timestamp

    @field_validator("notes", mode="before")
    @classmethod
    def validate_notes(cls, v: Any) -> Dict[str, Any]:
        return clean_notes(v)

class RazorpayOrderEntity(BaseModel):
    id: str
    entity: str = "order"
    amount: int  # in paise
    amount_paid: Optional[int] = 0
    amount_due: Optional[int] = 0
    currency: str = "INR"
    receipt: Optional[str] = None
    status: str  # created, attempted, paid
    attempts: Optional[int] = 0
    notes: Union[Dict[str, Any], List[Any]] = Field(default_factory=dict)
    created_at: int

    @field_validator("notes", mode="before")
    @classmethod
    def validate_notes(cls, v: Any) -> Dict[str, Any]:
        return clean_notes(v)

class RazorpayRefundEntity(BaseModel):
    id: str
    entity: str = "refund"
    amount: int  # in paise
    currency: str = "INR"
    payment_id: str
    notes: Union[Dict[str, Any], List[Any]] = Field(default_factory=dict)
    receipt: Optional[str] = None
    acquirer_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: int
    batch_id: Optional[str] = None
    status: str  # pending, processed, failed
    speed_processed: Optional[str] = "normal"
    speed_requested: Optional[str] = "normal"

    @field_validator("notes", mode="before")
    @classmethod
    def validate_notes(cls, v: Any) -> Dict[str, Any]:
        return clean_notes(v)

class RazorpayCollectionResponse(BaseModel):
    entity: str = "collection"
    count: int
    items: List[Dict[str, Any]]
