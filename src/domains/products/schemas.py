from pydantic import BaseModel


class CategoryCreate(BaseModel):
    id: str
    name: str
    color: str


class CategoryRead(BaseModel):
    id: str
    name: str
    color: str

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    sku: str
    name: str
    category_id: str
    price: float
    cost: float
    supplier_id: str | None = None
    unit: str = "und"


class ProductUpdate(BaseModel):
    name: str | None = None
    category_id: str | None = None
    price: float | None = None
    cost: float | None = None
    supplier_id: str | None = None
    unit: str | None = None


class ProductRead(BaseModel):
    sku: str
    name: str
    category_id: str
    price: float
    cost: float
    supplier_id: str | None
    unit: str

    model_config = {"from_attributes": True}

    @property
    def margin(self) -> float:
        if self.price == 0:
            return 0.0
        return round((self.price - self.cost) / self.price * 100, 1)
