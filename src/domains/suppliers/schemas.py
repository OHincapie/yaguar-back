from pydantic import BaseModel

from src.domains.suppliers.models import SupplierStatus


class SupplierCreate(BaseModel):
    id: str
    name: str
    contact: str
    categories: list[str] = []
    rating: float = 0.0
    lead_days: int = 0
    saldo: float = 0.0
    status: SupplierStatus = SupplierStatus.AL_DIA
    on_time_pct: float = 100.0


class SupplierUpdate(BaseModel):
    name: str | None = None
    contact: str | None = None
    categories: list[str] | None = None
    rating: float | None = None
    lead_days: int | None = None
    saldo: float | None = None
    status: SupplierStatus | None = None
    on_time_pct: float | None = None


class SupplierRead(BaseModel):
    id: str
    name: str
    contact: str
    categories: list[str]
    rating: float
    lead_days: int
    saldo: float
    status: SupplierStatus
    on_time_pct: float
    orders_count: int

    model_config = {"from_attributes": True}
