import math
from datetime import datetime, timezone

from src.domains.inventory.models import InventoryLevel, InventoryMovement, MovementType
from src.domains.inventory.repository import InventoryRepository
from src.domains.products.repository import ProductRepository
from src.shared.middleware.errors import BusinessError, NotFoundError


class InventoryService:
    def __init__(self, repo: InventoryRepository, product_repo: ProductRepository):
        self.repo = repo
        self.product_repo = product_repo

    async def _derive_bundle_level(self, company_id: str, bundle_product_id: str) -> InventoryLevel:
        components = await self.product_repo.get_components(company_id, bundle_product_id)
        if not components:
            return InventoryLevel(
                company_id=company_id, product_id=bundle_product_id, stock_qty=0.0, min_stock=0.0
            )

        available = []
        last_updated = None
        for comp in components:
            level = await self.repo.get_level(company_id, comp.component_product_id)
            comp_stock = level.stock_qty if level else 0.0
            available.append(math.floor(comp_stock / comp.qty) if comp.qty > 0 else 0)
            if level and (last_updated is None or level.last_updated > last_updated):
                last_updated = level.last_updated

        return InventoryLevel(
            company_id=company_id,
            product_id=bundle_product_id,
            stock_qty=float(min(available)),
            min_stock=0.0,
            last_updated=last_updated or datetime.now(timezone.utc),
        )

    async def list_levels(self, company_id: str, below_min: bool, page: int, page_size: int):
        real_levels, _ = await self.repo.get_all_levels(company_id, below_min=False, offset=0, limit=10_000)
        bundles = await self.product_repo.get_bundles(company_id)
        bundle_levels = [await self._derive_bundle_level(company_id, b.id) for b in bundles]

        combined = list(real_levels) + bundle_levels
        if below_min:
            combined = [lvl for lvl in combined if lvl.stock_qty <= lvl.min_stock]

        total = len(combined)
        offset = (page - 1) * page_size
        return combined[offset : offset + page_size], total

    async def get_level(self, company_id: str, product_id: str) -> InventoryLevel:
        product = await self.product_repo.get_by_id(company_id, product_id)
        if product and product.is_bundle:
            return await self._derive_bundle_level(company_id, product_id)
        level = await self.repo.get_level(company_id, product_id)
        if not level:
            raise NotFoundError("InventoryLevel", product_id)
        return level

    async def adjust(
        self,
        company_id: str,
        product_id: str,
        qty: float,
        min_stock: float | None = None,
        notes: str | None = None,
    ) -> InventoryLevel:
        product = await self.product_repo.get_by_id(company_id, product_id)
        if product and product.is_bundle:
            raise BusinessError(
                f"'{product.sku}' is a kit and has no stock of its own — adjust its base products instead"
            )

        level = await self.repo.get_level(company_id, product_id)
        current = level.stock_qty if level else 0.0
        new_qty = current + qty
        if new_qty < 0:
            raise BusinessError(f"Cannot reduce stock below 0. Current: {current}, adjustment: {qty}")
        if qty != 0:
            await self.repo.add_movement(
                company_id=company_id,
                product_id=product_id,
                type=MovementType.AJUSTE,
                qty=qty,
                notes=notes,
            )
        return await self.repo.upsert_level(company_id, product_id, qty, min_stock=min_stock)

    async def apply_sale(self, company_id: str, product_id: str, qty: float, sale_id: str) -> InventoryLevel | None:
        product = await self.product_repo.get_by_id(company_id, product_id)
        if product and product.is_bundle:
            components = await self.product_repo.get_components(company_id, product_id)
            if not components:
                raise BusinessError(f"'{product.sku}' is a kit with no components configured")

            # Validate every component has enough stock before deducting any of
            # them, so a mid-kit failure doesn't leave a partially-applied sale.
            for comp in components:
                level = await self.repo.get_level(company_id, comp.component_product_id)
                available = level.stock_qty if level else 0.0
                required = comp.qty * qty
                if available < required:
                    raise BusinessError(
                        f"Insufficient stock for kit component {comp.component_product_id}. "
                        f"Available: {available}, required: {required}"
                    )

            last_level = None
            for comp in components:
                required = comp.qty * qty
                await self.repo.add_movement(
                    company_id=company_id,
                    product_id=comp.component_product_id,
                    type=MovementType.SALIDA,
                    qty=-required,
                    reference_id=sale_id,
                    reference_type="sale",
                )
                last_level = await self.repo.upsert_level(company_id, comp.component_product_id, -required)
            return last_level

        level = await self.repo.get_level(company_id, product_id)
        current = level.stock_qty if level else 0.0
        if current < qty:
            raise BusinessError(f"Insufficient stock for {product_id}. Available: {current}, required: {qty}")
        await self.repo.add_movement(
            company_id=company_id,
            product_id=product_id,
            type=MovementType.SALIDA,
            qty=-qty,
            reference_id=sale_id,
            reference_type="sale",
        )
        return await self.repo.upsert_level(company_id, product_id, -qty)

    async def reverse_sale(self, company_id: str, product_id: str, qty: float, sale_id: str) -> None:
        """Undo a previously-applied sale line — used when editing a sale's
        lines (the old lines are reversed, then the new ones go through
        apply_sale as normal). Mirrors apply_sale's kit expansion, but adds
        stock back instead of validating/deducting it."""
        product = await self.product_repo.get_by_id(company_id, product_id)
        if product and product.is_bundle:
            components = await self.product_repo.get_components(company_id, product_id)
            for comp in components:
                restored = comp.qty * qty
                await self.repo.add_movement(
                    company_id=company_id,
                    product_id=comp.component_product_id,
                    type=MovementType.AJUSTE,
                    qty=restored,
                    reference_id=sale_id,
                    reference_type="sale_edit",
                    notes="Reversión por edición de venta",
                )
                await self.repo.upsert_level(company_id, comp.component_product_id, restored)
            return

        await self.repo.add_movement(
            company_id=company_id,
            product_id=product_id,
            type=MovementType.AJUSTE,
            qty=qty,
            reference_id=sale_id,
            reference_type="sale_edit",
            notes="Reversión por edición de venta",
        )
        await self.repo.upsert_level(company_id, product_id, qty)

    async def apply_purchase_receipt(self, company_id: str, product_id: str, qty: float, purchase_id: str) -> InventoryLevel:
        await self.repo.add_movement(
            company_id=company_id,
            product_id=product_id,
            type=MovementType.ENTRADA,
            qty=qty,
            reference_id=purchase_id,
            reference_type="purchase",
        )
        return await self.repo.upsert_level(company_id, product_id, qty)

    async def list_movements(self, company_id: str, product_id, type, from_date, to_date, page: int, page_size: int):
        offset = (page - 1) * page_size
        return await self.repo.get_movements(
            company_id, product_id=product_id, type=type, from_date=from_date, to_date=to_date,
            offset=offset, limit=page_size,
        )
