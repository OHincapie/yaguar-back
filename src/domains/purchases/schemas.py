from datetime import date as Date
from datetime import datetime

from pydantic import BaseModel

from src.domains.purchases.models import PurchaseStatus


class PurchaseLineCreate(BaseModel):
    product_id: str
    qty: float
    unit_cost: float


class PurchaseLineRead(BaseModel):
    id: int
    purchase_id: str
    product_id: str
    qty: float
    unit_cost: float

    model_config = {"from_attributes": True}


class PurchaseCreate(BaseModel):
    supplier_id: str
    eta: Date | None = None
    notes: str | None = None
    lines: list[PurchaseLineCreate] = []


class PurchaseStatusUpdate(BaseModel):
    status: PurchaseStatus


class PurchaseUpdate(BaseModel):
    supplier_id: str | None = None
    eta: Date | None = None
    notes: str | None = None
    # When provided, replaces the purchase's lines entirely and recalculates
    # total. Only allowed while the purchase hasn't been received/cancelled
    # yet — see PurchaseService.update_purchase.
    lines: list[PurchaseLineCreate] | None = None


class PurchaseRead(BaseModel):
    id: str
    code: str
    supplier_id: str
    date: datetime
    total: float
    status: PurchaseStatus
    eta: Date | None
    notes: str | None

    model_config = {"from_attributes": True}
