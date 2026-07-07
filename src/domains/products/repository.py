from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.products.models import Category, Product, ProductComponent
from src.shared.middleware.errors import ConflictError


class ProductRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(
        self,
        company_id: str,
        category_id: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Product], int]:
        query = select(Product).where(Product.company_id == company_id)
        if category_id:
            query = query.where(Product.category_id == category_id)
        if search:
            query = query.where(Product.name.ilike(f"%{search}%"))

        count_result = await self.session.exec(query)  # type: ignore
        total = len(count_result.all())

        result = await self.session.exec(query.offset(offset).limit(limit))  # type: ignore
        return result.all(), total

    async def get_by_sku(self, company_id: str, sku: str) -> Product | None:
        result = await self.session.exec(  # type: ignore
            select(Product).where(Product.company_id == company_id, Product.sku == sku)
        )
        return result.first()

    async def get_by_id(self, company_id: str, id: str) -> Product | None:
        result = await self.session.exec(  # type: ignore
            select(Product).where(Product.company_id == company_id, Product.id == id)
        )
        return result.first()

    async def get_bundles(self, company_id: str) -> list[Product]:
        result = await self.session.exec(  # type: ignore
            select(Product).where(Product.company_id == company_id, Product.is_bundle == True)  # noqa: E712
        )
        return result.all()

    async def create(self, product: Product) -> Product:
        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def update(self, product: Product) -> Product:
        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def delete(self, product: Product) -> None:
        sku = product.sku  # read before rollback expires the instance's attributes
        await self.session.delete(product)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(f"Can't delete '{sku}' — it has inventory, purchase, or sale records tied to it") from exc

    async def get_all_categories(self, company_id: str) -> list[Category]:
        result = await self.session.exec(select(Category).where(Category.company_id == company_id))  # type: ignore
        return result.all()

    async def get_category(self, company_id: str, id: str) -> Category | None:
        result = await self.session.exec(  # type: ignore
            select(Category).where(Category.company_id == company_id, Category.id == id)
        )
        return result.first()

    async def get_category_by_code(self, company_id: str, code: str) -> Category | None:
        result = await self.session.exec(  # type: ignore
            select(Category).where(Category.company_id == company_id, Category.code == code)
        )
        return result.first()

    async def create_category(self, category: Category) -> Category:
        self.session.add(category)
        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def get_components(self, company_id: str, bundle_product_id: str) -> list[ProductComponent]:
        result = await self.session.exec(  # type: ignore
            select(ProductComponent).where(
                ProductComponent.company_id == company_id,
                ProductComponent.bundle_product_id == bundle_product_id,
            )
        )
        return result.all()

    async def replace_components(
        self, company_id: str, bundle_product_id: str, items: list[tuple[str, float]]
    ) -> list[ProductComponent]:
        existing = await self.get_components(company_id, bundle_product_id)
        for row in existing:
            await self.session.delete(row)
        new_rows = [
            ProductComponent(
                company_id=company_id,
                bundle_product_id=bundle_product_id,
                component_product_id=component_id,
                qty=qty,
            )
            for component_id, qty in items
        ]
        for row in new_rows:
            self.session.add(row)
        await self.session.commit()
        for row in new_rows:
            await self.session.refresh(row)
        return new_rows
