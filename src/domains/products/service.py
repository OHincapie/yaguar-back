from src.domains.products.models import Category, Product
from src.domains.products.repository import ProductRepository
from src.domains.products.schemas import CategoryCreate, ProductCreate, ProductUpdate
from src.shared.middleware.errors import ConflictError, NotFoundError


class ProductService:
    def __init__(self, repo: ProductRepository):
        self.repo = repo

    async def list_products(self, category_id: str | None, search: str | None, page: int, page_size: int):
        offset = (page - 1) * page_size
        return await self.repo.get_all(category_id=category_id, search=search, offset=offset, limit=page_size)

    async def get_product(self, sku: str) -> Product:
        product = await self.repo.get_by_sku(sku)
        if not product:
            raise NotFoundError("Product", sku)
        return product

    async def create_product(self, data: ProductCreate) -> Product:
        existing = await self.repo.get_by_sku(data.sku)
        if existing:
            raise ConflictError(f"Product with SKU '{data.sku}' already exists")
        product = Product(**data.model_dump())
        return await self.repo.create(product)

    async def update_product(self, sku: str, data: ProductUpdate) -> Product:
        product = await self.get_product(sku)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(product, field, value)
        return await self.repo.update(product)

    async def delete_product(self, sku: str) -> None:
        product = await self.get_product(sku)
        await self.repo.delete(product)

    async def list_categories(self) -> list[Category]:
        return await self.repo.get_all_categories()

    async def create_category(self, data: CategoryCreate) -> Category:
        existing = await self.repo.get_category(data.id)
        if existing:
            raise ConflictError(f"Category '{data.id}' already exists")
        category = Category(**data.model_dump())
        return await self.repo.create_category(category)
