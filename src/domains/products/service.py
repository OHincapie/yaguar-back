from src.domains.products.models import Category, Product
from src.domains.products.repository import ProductRepository
from src.domains.products.schemas import (
    CategoryCreate,
    CategoryUpdate,
    ProductComponentItem,
    ProductComponentRead,
    ProductCreate,
    ProductUpdate,
)
from src.shared.middleware.errors import BusinessError, ConflictError, NotFoundError


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

        payload = data.model_dump(exclude={"components"})
        product = Product(company_id=company_id, is_bundle=bool(data.components), **payload)
        product = await self.repo.create(product)

        if data.components:
            await self._set_components(company_id, product, data.components)
        return product

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

    # Distinct, readable defaults for auto-assigned category colors — cycled
    # through in order, skipping any a company already uses so a new category
    # doesn't collide visually with an existing one.
    _CATEGORY_PALETTE = (
        "#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899", "#EF4444",
        "#14B8A6", "#F97316", "#6366F1", "#84CC16", "#06B6D4", "#D946EF",
    )

    async def create_category(self, company_id: str, data: CategoryCreate) -> Category:
        existing = await self.repo.get_all_categories(company_id)

        name = data.name.strip()
        if not name:
            raise BusinessError("La categoría necesita un nombre")

        # A name that already exists (case-insensitive) is a duplicate — the
        # code is an implementation detail the caller usually doesn't set, so
        # dedupe on the human-facing name, not the code.
        if any(c.name.strip().lower() == name.lower() for c in existing):
            raise ConflictError(f"Ya existe una categoría '{name}'")

        code = (data.code or self._derive_category_code(name, existing)).upper()
        if any(c.code == code for c in existing):
            raise ConflictError(f"El código de categoría '{code}' ya está en uso")

        color = data.color or self._pick_category_color(existing)
        category = Category(company_id=company_id, code=code, name=name, color=color)
        return await self.repo.create_category(category)

    async def update_category(self, company_id: str, id: str, data: CategoryUpdate) -> Category:
        category = await self.repo.get_category(company_id, id)
        if not category:
            raise NotFoundError("Category", id)

        if data.name is not None:
            name = data.name.strip()
            if not name:
                raise BusinessError("La categoría necesita un nombre")
            existing = await self.repo.get_all_categories(company_id)
            # Case-insensitive name uniqueness, excluding this category itself.
            if any(c.id != id and c.name.strip().lower() == name.lower() for c in existing):
                raise ConflictError(f"Ya existe una categoría '{name}'")
            category.name = name

        if data.color is not None:
            category.color = data.color

        return await self.repo.update_category(category)

    @staticmethod
    def _derive_category_code(name: str, existing: list[Category]) -> str:
        """A short uppercase code from the name — first 3 letters, then a
        numeric suffix if that's taken (TEC, TEC2, ...). Falls back to 'CAT'
        for a name with fewer than 3 usable letters."""
        letters = "".join(ch for ch in name.upper() if ch.isalpha())
        base = letters[:3] or "CAT"
        taken = {c.code for c in existing}
        if base not in taken:
            return base
        for n in range(2, 100):
            candidate = f"{base}{n}"
            if candidate not in taken:
                return candidate
        return base  # 98 collisions on one prefix — let the uniqueness check surface it

    @classmethod
    def _pick_category_color(cls, existing: list[Category]) -> str:
        used = {c.color.upper() for c in existing}
        for color in cls._CATEGORY_PALETTE:
            if color.upper() not in used:
                return color
        # More categories than palette entries — reuse by count, keeps it deterministic.
        return cls._CATEGORY_PALETTE[len(existing) % len(cls._CATEGORY_PALETTE)]

    async def get_components(self, company_id: str, sku: str) -> list[ProductComponentRead]:
        product = await self.get_product(company_id, sku)
        rows = await self.repo.get_components(company_id, product.id)
        result = []
        for row in rows:
            component = await self.repo.get_by_id(company_id, row.component_product_id)
            if component:
                result.append(
                    ProductComponentRead(
                        component_product_id=component.id,
                        component_sku=component.sku,
                        component_name=component.name,
                        qty=row.qty,
                    )
                )
        return result

    async def set_components(
        self, company_id: str, sku: str, items: list[ProductComponentItem]
    ) -> list[ProductComponentRead]:
        product = await self.get_product(company_id, sku)
        await self._set_components(company_id, product, items)
        return await self.get_components(company_id, sku)

    async def _set_components(self, company_id: str, product: Product, items: list[ProductComponentItem]) -> None:
        for item in items:
            if item.component_product_id == product.id:
                raise BusinessError("A product cannot be a component of itself")
            component = await self.repo.get_by_id(company_id, item.component_product_id)
            if not component:
                raise NotFoundError("Product", item.component_product_id)
            if component.is_bundle:
                raise BusinessError(
                    f"'{component.sku}' is itself a kit — a kit can only be made of base products"
                )

        await self.repo.replace_components(
            company_id, product.id, [(i.component_product_id, i.qty) for i in items]
        )
        product.is_bundle = len(items) > 0
        await self.repo.update(product)
