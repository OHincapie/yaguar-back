from pydantic import BaseModel

from src.domains.sales.schemas import PaymentLine, SaleRead


class CheckoutLine(BaseModel):
    product_id: str
    qty: float
    unit_price: float
    unit_cost: float


class CheckoutRequest(BaseModel):
    # None = walk-in/casual sale, no buyer registered.
    customer_id: str | None = None
    payments: list[PaymentLine]
    lines: list[CheckoutLine]
    notes: str | None = None


class CheckoutResponse(BaseModel):
    sale: SaleRead
    total: float
    items_count: int
