from enum import StrEnum

from sqlmodel import Column, Field, SQLModel
from sqlalchemy import JSON


class SupplierStatus(StrEnum):
    AL_DIA = "al día"
    PENDIENTE = "pendiente"
    VENCIDO = "vencido"


class Supplier(SQLModel, table=True):
    __tablename__ = "suppliers"

    id: str = Field(primary_key=True, max_length=50)
    name: str = Field(max_length=200)
    contact: str = Field(max_length=200)
    categories: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    rating: float = Field(default=0.0)
    lead_days: int = Field(default=0)
    saldo: float = Field(default=0.0)
    status: SupplierStatus = Field(default=SupplierStatus.AL_DIA)
    on_time_pct: float = Field(default=100.0)
    orders_count: int = Field(default=0)
