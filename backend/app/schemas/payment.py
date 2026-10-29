from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class PaymentInitiate(BaseModel):
    provider: str = "sandbox"  # "sandbox", "razorpay", or "cod"
    payment_method: str | None = None  # "upi_gpay", "upi_phonepe", "upi_qr", "card", "cod"


class RazorpayOrderResponse(BaseModel):
    order_id: int
    razorpay_order_id: str
    amount: int  # in paise
    currency: str = "INR"
    key_id: str
    payment_id: int
    is_simulation: bool = False


class PaymentVerify(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str
    payment_method: str | None = "upi_gpay"


class PaymentRead(BaseModel):
    id: int
    order_id: int
    provider: str
    provider_reference: str | None = None
    amount: Decimal
    status: str
    payment_method: str | None = None

    model_config = ConfigDict(from_attributes=True)
