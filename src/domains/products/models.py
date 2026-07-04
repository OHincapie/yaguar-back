import uuid
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


class Category(SQLModel, table=True):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_categories_company_code"),)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    company_id: str = Field(foreign_key="companies.id", max_length=36, index=True)
    code: str = Field(max_length=50)
    name: str = Field(max_length=100)
    color: str = Field(max_length=30)


class Product(SQLModel, table=True):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("company_id", "sku", name="uq_products_company_sku"),)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    company_id: str = Field(foreign_key="companies.id", max_length=36, index=True)
    sku: str = Field(max_length=50)
    name: str = Field(max_length=200)
    category_id: str = Field(foreign_key="categories.id", max_length=36)
    price: float
    cost: float
    supplier_id: Optional[str] = Field(default=None, foreign_key="suppliers.id", max_length=36)
    unit: str = Field(default="und", max_length=20)
