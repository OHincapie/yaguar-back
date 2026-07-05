from datetime import datetime

from pydantic import BaseModel

from src.domains.inventory.models import MovementType


class InventoryLevelRead(BaseModel):
    product_id: str
    stock_qty: float
    min_stock: float
    last_updated: datetime
    is_below_min: bool = False

    model_config = {"from_attributes": True}


class InventoryAdjust(BaseModel):
    qty: float = 0.0
    min_stock: float | None = None
    notes: str | None = None


class InventoryMovementRead(BaseModel):
    id: int
    product_id: str
    type: MovementType
    qty: float
    reference_id: str | None
    reference_type: str | None
    date: datetime
    notes: str | None

    model_config = {"from_attributes": True}
