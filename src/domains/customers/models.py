from enum import StrEnum

from sqlmodel import AutoString, Field, SQLModel


class CustomerType(StrEnum):
    MAYORISTA = "Mayorista"
    MINORISTA = "Minorista"


class CustomerStatus(StrEnum):
    ACTIVO = "activo"
    VIP = "vip"
    RIESGO = "riesgo"


class Customer(SQLModel, table=True):
    __tablename__ = "customers"

    id: str = Field(primary_key=True, max_length=50)
    name: str = Field(max_length=200)
    type: CustomerType = Field(sa_type=AutoString)
    city: str = Field(max_length=100)
    ltv: float = Field(default=0.0)
    orders: int = Field(default=0)
    status: CustomerStatus = Field(default=CustomerStatus.ACTIVO, sa_type=AutoString)
    saldo: float = Field(default=0.0)
