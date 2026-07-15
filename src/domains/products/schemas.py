from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    # Both optional: the service derives a 3-letter code from the name and
    # picks a palette color when omitted, so callers (the chat, a simple UI
    # form) only need to supply a name. A UI with a color picker can still
    # pass an explicit color; passing a code is allowed but rarely useful.
    code: str | None = None
    color: str | None = None


class CategoryRead(BaseModel):
    id: str
    code: str
    name: str
    color: str

    model_config = {"from_attributes": True}


class CategoryUpdate(BaseModel):
    # Both optional — a caller can rename, recolor, or both. The code isn't
    # editable (it's an internal handle other things may reference).
    name: str | None = None
    color: str | None = None


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
