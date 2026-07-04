import uuid
from enum import StrEnum

from sqlmodel import AutoString, Field, SQLModel, UniqueConstraint


class CustomerType(StrEnum):
    MAYORISTA = "Mayorista"
    MINORISTA = "Minorista"


class CustomerStatus(StrEnum):
    ACTIVO = "activo"
    VIP = "vip"
    RIESGO = "riesgo"


class Customer(SQLModel, table=True):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_customers_company_code"),)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    company_id: str = Field(foreign_key="companies.id", max_length=36, index=True)
    code: str = Field(max_length=50)
    name: str = Field(max_length=200)
    type: CustomerType = Field(sa_type=AutoString)
    city: str = Field(max_length=100)
    ltv: float = Field(default=0.0)
    orders: int = Field(default=0)
    status: CustomerStatus = Field(default=CustomerStatus.ACTIVO, sa_type=AutoString)
    saldo: float = Field(default=0.0)
