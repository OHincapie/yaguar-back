from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from sqlalchemy import DateTime
from sqlmodel import AutoString, Field, SQLModel


class MovementType(StrEnum):
    ENTRADA = "entrada"
    SALIDA = "salida"
    AJUSTE = "ajuste"


class InventoryLevel(SQLModel, table=True):
    __tablename__ = "inventory_levels"

    product_sku: str = Field(primary_key=True, foreign_key="products.sku", max_length=50)
    stock_qty: float = Field(default=0.0)
    min_stock: float = Field(default=0.0)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))


class InventoryMovement(SQLModel, table=True):
    __tablename__ = "inventory_movements"

    id: Optional[int] = Field(default=None, primary_key=True)
    product_sku: str = Field(foreign_key="products.sku", max_length=50)
    type: MovementType = Field(sa_type=AutoString)
    qty: float
    reference_id: Optional[str] = Field(default=None, max_length=50)
    reference_type: Optional[str] = Field(default=None, max_length=50)
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))
    notes: Optional[str] = Field(default=None, max_length=500)
