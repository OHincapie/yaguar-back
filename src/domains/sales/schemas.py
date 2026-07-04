from datetime import datetime

from pydantic import BaseModel

from src.domains.sales.models import PaymentMethod, SaleStatus


class SaleLineCreate(BaseModel):
    product_id: str
    qty: float
    unit_price: float
    unit_cost: float


class SaleLineRead(BaseModel):
    id: int
    sale_id: str
    product_id: str
    qty: float
    unit_price: float
    unit_cost: float

    model_config = {"from_attributes": True}


class SaleCreate(BaseModel):
    customer_id: str
    payment_method: PaymentMethod = PaymentMethod.EFECTIVO
    status: SaleStatus = SaleStatus.PENDIENTE
    notes: str | None = None
    lines: list[SaleLineCreate] = []


class SaleStatusUpdate(BaseModel):
    status: SaleStatus


class SaleRead(BaseModel):
    id: str
    code: str
    customer_id: str
    date: datetime
    total: float
    payment_method: PaymentMethod
    status: SaleStatus
    notes: str | None

    model_config = {"from_attributes": True}
