from pydantic import BaseModel

from src.domains.sales.models import PaymentMethod
from src.domains.sales.schemas import SaleRead


class CheckoutLine(BaseModel):
    product_id: str
    qty: float
    unit_price: float
    unit_cost: float


class CheckoutRequest(BaseModel):
    customer_id: str
    payment_method: PaymentMethod = PaymentMethod.EFECTIVO
    lines: list[CheckoutLine]
    notes: str | None = None


class CheckoutResponse(BaseModel):
    sale: SaleRead
    total: float
    items_count: int
