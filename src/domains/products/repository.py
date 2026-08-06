from sqlalchemy.exc import IntegrityError
from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.inventory.models import InventoryLevel, InventoryMovement
from src.domains.products.models import Category, Product, ProductComponent
from src.domains.purchases.models import PurchaseLine
from src.domains.sales.models import SaleLine
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
        archived: bool = False,
    ) -> tuple[list[Product], int]:
        # `archived` selects which side to return, it doesn't widen the result:
        # the archived list is its own view (Inventario's "Archivados" filter),
        # never mixed into the working catalog.
        query = select(Product).where(
            Product.company_id == company_id, Product.is_archived == archived
        )
        if category_id:
            query = query.where(Product.category_id == category_id)
        if search:
            query = query.where(Product.name.ilike(f"%{search}%"))

        count_result = await self.session.exec(query)  # type: ignore
        total = len(count_result.all())

        # Explicit sort: OFFSET/LIMIT without an ORDER BY lets Postgres return
        # rows in any order it likes, so page 2 can repeat or skip rows from
        # page 1. sku is unique per company, so it's a fully deterministic key.
        result = await self.session.exec(query.order_by(Product.sku).offset(offset).limit(limit))  # type: ignore
        return result.all(), total

    async def get_by_sku(self, company_id: str, sku: str) -> Product | None:
        result = await self.session.exec(  # type: ignore
            select(Product).where(Product.company_id == company_id, Product.sku == sku)
        )
        return result.first()

    async def skus_with_prefix(self, company_id: str, prefix: str) -> set[str]:
        """Archived products are included deliberately: the uniqueness
        constraint is on (company_id, sku) regardless of archived state, so
        reusing an archived product's SKU would fail on insert."""
        result = await self.session.exec(  # type: ignore
            select(Product.sku).where(
                Product.company_id == company_id, Product.sku.like(f"{prefix}%")
            )
        )
        return set(result.all())

    async def get_by_id(self, company_id: str, id: str) -> Product | None:
        result = await self.session.exec(  # type: ignore
            select(Product).where(Product.company_id == company_id, Product.id == id)
        )
        return result.first()

    async def get_bundles(self, company_id: str) -> list[Product]:
        result = await self.session.exec(  # type: ignore
            select(Product)
            .where(
                Product.company_id == company_id,
                Product.is_bundle == True,  # noqa: E712
                Product.is_archived == False,  # noqa: E712
            )
            .order_by(Product.sku)
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

    async def has_history(self, product: Product) -> bool:
        """Whether anything references this product that a hard delete would
        falsify: a sale line, a purchase line, or being a component of another
        kit. Checked up front rather than by catching the FK violation, because
        recovering from an IntegrityError means a rollback, and reading an
        attribute off a rolled-back instance is the MissingGreenlet trap
        documented in CLAUDE.md."""
        for model, column in (
            (SaleLine, SaleLine.product_id),
            (PurchaseLine, PurchaseLine.product_id),
            (ProductComponent, ProductComponent.component_product_id),
        ):
            result = await self.session.exec(select(model).where(column == product.id).limit(1))  # type: ignore
            if result.first() is not None:
                return True
        return False

    async def set_archived(self, product: Product, archived: bool) -> Product:
        product.is_archived = archived
        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def delete(self, product: Product) -> None:
        sku = product.sku  # read before rollback expires the instance's attributes
        # A product's own inventory (level + movement history) and its own
        # component list go with it — having stock is not a reason to keep a
        # product someone wants gone; the confirm modal warns about it. Sale/
        # purchase lines (and being a component of *another* kit) still block
        # via their FKs — deleting those would falsify real business history.
        await self.session.exec(delete(InventoryLevel).where(InventoryLevel.product_id == product.id))  # type: ignore
        await self.session.exec(delete(InventoryMovement).where(InventoryMovement.product_id == product.id))  # type: ignore
        await self.session.exec(  # type: ignore
            delete(ProductComponent).where(ProductComponent.bundle_product_id == product.id)
        )
        await self.session.delete(product)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(
                f"No se puede eliminar '{sku}' — tiene ventas, compras o kits asociados"
            ) from exc

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

    async def update_category(self, category: Category) -> Category:
        self.session.add(category)
        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def products_in_category(self, company_id: str, category_id: str) -> list[Product]:
        """Includes archived products on purpose — they still carry a
        category_id, and leaving them pointing at a deleted category would
        break the join when the archived view renders them."""
        result = await self.session.exec(  # type: ignore
            select(Product).where(
                Product.company_id == company_id, Product.category_id == category_id
            )
        )
        return result.all()

    async def reassign_category(self, products: list[Product], target_category_id: str) -> None:
        for product in products:
            product.category_id = target_category_id
            self.session.add(product)
        await self.session.commit()

    async def delete_category(self, category: Category) -> None:
        name = category.name  # read before a rollback could expire the instance
        await self.session.delete(category)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(
                f"No se puede eliminar la categoría '{name}' — todavía tiene productos asociados"
            ) from exc

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
