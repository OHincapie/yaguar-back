from typing import Optional

from sqlmodel import Field, SQLModel


class Category(SQLModel, table=True):
    __tablename__ = "categories"

    id: str = Field(primary_key=True, max_length=50)
    name: str = Field(max_length=100)
    color: str = Field(max_length=30)


class Product(SQLModel, table=True):
    __tablename__ = "products"

    sku: str = Field(primary_key=True, max_length=50)
    name: str = Field(max_length=200)
    category_id: str = Field(foreign_key="categories.id", max_length=50)
    price: float
    cost: float
    supplier_id: Optional[str] = Field(default=None, foreign_key="suppliers.id", max_length=50)
    unit: str = Field(default="und", max_length=20)
