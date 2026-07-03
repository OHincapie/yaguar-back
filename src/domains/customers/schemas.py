from pydantic import BaseModel

from src.domains.customers.models import CustomerStatus, CustomerType


class CustomerCreate(BaseModel):
    id: str
    name: str
    type: CustomerType
    city: str
    status: CustomerStatus = CustomerStatus.ACTIVO
    saldo: float = 0.0


class CustomerUpdate(BaseModel):
    name: str | None = None
    type: CustomerType | None = None
    city: str | None = None
    status: CustomerStatus | None = None
    saldo: float | None = None


class CustomerRead(BaseModel):
    id: str
    name: str
    type: CustomerType
    city: str
    ltv: float
    orders: int
    status: CustomerStatus
    saldo: float

    model_config = {"from_attributes": True}
