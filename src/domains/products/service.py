from src.domains.products.models import Category, Product
from src.domains.products.repository import ProductRepository
from src.domains.products.schemas import CategoryCreate, ProductCreate, ProductUpdate
from src.shared.middleware.errors import ConflictError, NotFoundError


class ProductService:
    def __init__(self, repo: ProductRepository):
        self.repo = repo

    async def list_products(
        self, company_id: str, category_id: str | None, search: str | None, page: int, page_size: int
    ):
        offset = (page - 1) * page_size
        return await self.repo.get_all(
            company_id=company_id, category_id=category_id, search=search, offset=offset, limit=page_size
        )

    async def get_product(self, company_id: str, sku: str) -> Product:
        product = await self.repo.get_by_sku(company_id, sku)
        if not product:
            raise NotFoundError("Product", sku)
        return product

    async def create_product(self, company_id: str, data: ProductCreate) -> Product:
        existing = await self.repo.get_by_sku(company_id, data.sku)
        if existing:
            raise ConflictError(f"Product with SKU '{data.sku}' already exists")
        product = Product(company_id=company_id, **data.model_dump())
        return await self.repo.create(product)

    async def update_product(self, company_id: str, sku: str, data: ProductUpdate) -> Product:
        product = await self.get_product(company_id, sku)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(product, field, value)
        return await self.repo.update(product)

    async def delete_product(self, company_id: str, sku: str) -> None:
        product = await self.get_product(company_id, sku)
        await self.repo.delete(product)

    async def list_categories(self, company_id: str) -> list[Category]:
        return await self.repo.get_all_categories(company_id)

    async def create_category(self, company_id: str, data: CategoryCreate) -> Category:
        existing = await self.repo.get_category_by_code(company_id, data.code)
        if existing:
            raise ConflictError(f"Category '{data.code}' already exists")
        category = Category(company_id=company_id, **data.model_dump())
        return await self.repo.create_category(category)
