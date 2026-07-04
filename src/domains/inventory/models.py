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

    product_id: str = Field(primary_key=True, foreign_key="products.id", max_length=36)
    company_id: str = Field(foreign_key="companies.id", max_length=36, index=True)
    stock_qty: float = Field(default=0.0)
    min_stock: float = Field(default=0.0)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))


class InventoryMovement(SQLModel, table=True):
    __tablename__ = "inventory_movements"

    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: str = Field(foreign_key="companies.id", max_length=36, index=True)
    product_id: str = Field(foreign_key="products.id", max_length=36)
    type: MovementType = Field(sa_type=AutoString)
    qty: float
    reference_id: Optional[str] = Field(default=None, max_length=50)
    reference_type: Optional[str] = Field(default=None, max_length=50)
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))
    notes: Optional[str] = Field(default=None, max_length=500)
