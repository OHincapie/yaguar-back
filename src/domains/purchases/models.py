import uuid
from datetime import date as Date
from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from sqlalchemy import DateTime
from sqlmodel import AutoString, Field, SQLModel, UniqueConstraint


class PurchaseStatus(StrEnum):
    BORRADOR = "borrador"
    EN_CAMINO = "en camino"
    ADUANA = "aduana"
    RECIBIDO = "recibido"
    CANCELADO = "cancelado"


class Purchase(SQLModel, table=True):
    __tablename__ = "purchases"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_purchases_company_code"),)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    company_id: str = Field(foreign_key="companies.id", max_length=36, index=True)
    code: str = Field(max_length=50)
    supplier_id: str = Field(foreign_key="suppliers.id", max_length=36)
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))
    total: float = Field(default=0.0)
    status: PurchaseStatus = Field(default=PurchaseStatus.BORRADOR, sa_type=AutoString)
    eta: Optional[Date] = Field(default=None)
    notes: Optional[str] = Field(default=None, max_length=500)


class PurchaseLine(SQLModel, table=True):
    __tablename__ = "purchase_lines"

    id: Optional[int] = Field(default=None, primary_key=True)
    purchase_id: str = Field(foreign_key="purchases.id", max_length=36)
    product_id: str = Field(foreign_key="products.id", max_length=36)
    qty: float
    unit_cost: float
