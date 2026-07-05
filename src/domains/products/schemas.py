from pydantic import BaseModel


class CategoryCreate(BaseModel):
    code: str
    name: str
    color: str


class CategoryRead(BaseModel):
    id: str
    code: str
    name: str
    color: str

    model_config = {"from_attributes": True}


class ProductComponentItem(BaseModel):
    component_product_id: str
    qty: float


class ProductComponentRead(BaseModel):
    component_product_id: str
    component_sku: str
    component_name: str
    qty: float


class SetComponentsRequest(BaseModel):
    items: list[ProductComponentItem]


class ProductCreate(BaseModel):
    sku: str
    name: str
    category_id: str
    price: float
    cost: float
    supplier_id: str | None = None
    unit: str = "und"
    components: list[ProductComponentItem] | None = None


class ProductUpdate(BaseModel):
    name: str | None = None
    category_id: str | None = None
    price: float | None = None
    cost: float | None = None
    supplier_id: str | None = None
    unit: str | None = None


class ProductRead(BaseModel):
    id: str
    sku: str
    name: str
    category_id: str
    price: float
    cost: float
    supplier_id: str | None
    unit: str
    is_bundle: bool

    model_config = {"from_attributes": True}

    @property
    def margin(self) -> float:
        if self.price == 0:
            return 0.0
        return round((self.price - self.cost) / self.price * 100, 1)
