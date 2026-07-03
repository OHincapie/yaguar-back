from datetime import datetime

from pydantic import BaseModel

from src.domains.inventory.models import MovementType


class InventoryLevelRead(BaseModel):
    product_sku: str
    stock_qty: float
    min_stock: float
    last_updated: datetime
    is_below_min: bool = False

    model_config = {"from_attributes": True}


class InventoryAdjust(BaseModel):
    qty: float
    notes: str | None = None


class InventoryMovementRead(BaseModel):
    id: int
    product_sku: str
    type: MovementType
    qty: float
    reference_id: str | None
    reference_type: str | None
    date: datetime
    notes: str | None

    model_config = {"from_attributes": True}
