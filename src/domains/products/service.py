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
        self,
        company_id: str,
        category_id: str | None,
        search: str | None,
        page: int,
        page_size: int,
        archived: bool = False,
    ):
        offset = (page - 1) * page_size
        return await self.repo.get_all(
            company_id=company_id,
            category_id=category_id,
            search=search,
            offset=offset,
            limit=page_size,
            archived=archived,
        )

    async def get_product(self, company_id: str, sku: str) -> Product:
        product = await self.repo.get_by_sku(company_id, sku)
        if not product:
            raise NotFoundError("Product", sku)
        return product

    async def create_product(self, company_id: str, data: ProductCreate) -> Product:
        sku = (data.sku or "").strip().upper()
        if sku:
            existing = await self.repo.get_by_sku(company_id, sku)
            if existing:
                raise ConflictError(f"Product with SKU '{sku}' already exists")
        else:
            # SKU is optional: plenty of small shops don't run their own coding
            # scheme and typing one is friction on the most-used form in the
            # app. Derived from the name the same way category codes are.
            sku = await self._derive_product_sku(company_id, data.name)

        payload = data.model_dump(exclude={"components", "sku"})
        product = Product(company_id=company_id, sku=sku, is_bundle=bool(data.components), **payload)
        product = await self.repo.create(product)

        if data.components:
            await self._set_components(company_id, product, data.components)
        return product

    async def update_product(self, company_id: str, sku: str, data: ProductUpdate) -> Product:
        product = await self.get_product(company_id, sku)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(product, field, value)
        return await self.repo.update(product)

    async def delete_product(self, company_id: str, sku: str) -> str:
        """Returns "deleted" or "archived" so the caller can tell the user what
        actually happened. A product referenced by a sale, a purchase or another
        kit is archived rather than removed — deleting those lines would leave a
        received purchase showing fewer items than were paid for, and its total
        no longer matching the ledger entry it wrote."""
        product = await self.get_product(company_id, sku)
        if await self.repo.has_history(product):
            await self.repo.set_archived(product, True)
            return "archived"
        await self.repo.delete(product)
        return "deleted"

    async def restore_product(self, company_id: str, sku: str) -> Product:
        product = await self.get_product(company_id, sku)
        if not product.is_archived:
            raise BusinessError(f"El producto '{sku}' no está archivado")
        return await self.repo.set_archived(product, False)

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

    async def delete_category(self, company_id: str, id: str, reassign_to: str | None = None) -> int:
        """Deletes a category, moving its products to `reassign_to` first.
        Returns how many were moved. Refuses without a target when the category
        still has products — products can't be left pointing at a category that
        no longer exists (every screen joins on it), and silently picking a
        destination for someone isn't ours to decide."""
        category = await self.repo.get_category(company_id, id)
        if not category:
            raise NotFoundError("Category", id)

        products = await self.repo.products_in_category(company_id, id)
        if products:
            if not reassign_to:
                raise BusinessError(
                    f"La categoría '{category.name}' tiene {len(products)} "
                    f"producto{'s' if len(products) != 1 else ''} — indica a cuál moverlos"
                )
            if reassign_to == id:
                raise BusinessError("La categoría destino no puede ser la que estás eliminando")
            target = await self.repo.get_category(company_id, reassign_to)
            if not target:
                raise NotFoundError("Category", reassign_to)
            await self.repo.reassign_category(products, target.id)

        await self.repo.delete_category(category)
        return len(products)

    async def _derive_product_sku(self, company_id: str, name: str) -> str:
        """An auto SKU from the product name: the first letters uppercased plus
        a zero-padded counter — "Melena de León" → MELE001, then MELE002 for the
        next one. Mirrors _derive_category_code's convention, with the counter
        always present so auto-generated SKUs read consistently rather than
        having the first of each family look different from its siblings."""
        letters = "".join(ch for ch in name.upper() if ch.isalpha())
        base = letters[:4] or "PRD"
        taken = await self.repo.skus_with_prefix(company_id, base)
        for n in range(1, 1000):
            candidate = f"{base}{n:03d}"
            if candidate not in taken:
                return candidate
        raise BusinessError(
            f"No se pudo generar un SKU automático para '{name}' — escribe uno manualmente"
        )

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
