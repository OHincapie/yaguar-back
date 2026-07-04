import uuid
from enum import StrEnum

from sqlmodel import AutoString, Column, Field, SQLModel, UniqueConstraint
from sqlalchemy import JSON


class SupplierStatus(StrEnum):
    AL_DIA = "al día"
    PENDIENTE = "pendiente"
    VENCIDO = "vencido"


class Supplier(SQLModel, table=True):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_suppliers_company_code"),)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    company_id: str = Field(foreign_key="companies.id", max_length=36, index=True)
    code: str = Field(max_length=50)
    name: str = Field(max_length=200)
    contact: str = Field(max_length=200)
    categories: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    rating: float = Field(default=0.0)
    lead_days: int = Field(default=0)
    saldo: float = Field(default=0.0)
    status: SupplierStatus = Field(default=SupplierStatus.AL_DIA, sa_type=AutoString)
    on_time_pct: float = Field(default=100.0)
    orders_count: int = Field(default=0)
