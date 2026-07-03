from datetime import date as Date
from datetime import datetime

from pydantic import BaseModel

from src.domains.purchases.models import PurchaseStatus


class PurchaseLineCreate(BaseModel):
    product_sku: str
    qty: float
    unit_cost: float


class PurchaseLineRead(BaseModel):
    id: int
    purchase_id: str
    product_sku: str
    qty: float
    unit_cost: float

    model_config = {"from_attributes": True}


class PurchaseCreate(BaseModel):
    id: str
    supplier_id: str
    eta: Date | None = None
    notes: str | None = None
    lines: list[PurchaseLineCreate] = []


class PurchaseStatusUpdate(BaseModel):
    status: PurchaseStatus


class PurchaseRead(BaseModel):
    id: str
    supplier_id: str
    date: datetime
    total: float
    status: PurchaseStatus
    eta: Date | None
    notes: str | None

    model_config = {"from_attributes": True}
