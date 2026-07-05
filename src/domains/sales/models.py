import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from sqlalchemy import DateTime
from sqlmodel import AutoString, Field, SQLModel, UniqueConstraint


class PaymentMethod(StrEnum):
    EFECTIVO = "Efectivo"
    CREDITO = "Crédito"
    TARJETA = "Tarjeta"
    TRANSFERENCIA = "Transferencia"


class SaleStatus(StrEnum):
    PAGADO = "pagado"
    PENDIENTE = "pendiente"
    VENCIDO = "vencido"
    CANCELADO = "cancelado"


class Sale(SQLModel, table=True):
    __tablename__ = "sales"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_sales_company_code"),)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    company_id: str = Field(foreign_key="companies.id", max_length=36, index=True)
    code: str = Field(max_length=50)
    customer_id: str = Field(foreign_key="customers.id", max_length=36)
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))
    total: float = Field(default=0.0)
    payment_method: PaymentMethod = Field(default=PaymentMethod.EFECTIVO, sa_type=AutoString)
    status: SaleStatus = Field(default=SaleStatus.PENDIENTE, sa_type=AutoString)
    notes: Optional[str] = Field(default=None, max_length=500)
    # Only meaningful for credit sales — Mara (collections agent) uses this
    # to flag a sale as overdue. Null for cash/card/transfer sales.
    due_date: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))


class SaleLine(SQLModel, table=True):
    __tablename__ = "sale_lines"

    id: Optional[int] = Field(default=None, primary_key=True)
    sale_id: str = Field(foreign_key="sales.id", max_length=36)
    product_id: str = Field(foreign_key="products.id", max_length=36)
    qty: float
    unit_price: float
    unit_cost: float
