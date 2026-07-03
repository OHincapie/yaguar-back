from src.domains.inventory.models import InventoryLevel, InventoryMovement, MovementType
from src.domains.inventory.repository import InventoryRepository
from src.shared.middleware.errors import BusinessError, NotFoundError


class InventoryService:
    def __init__(self, repo: InventoryRepository):
        self.repo = repo

    async def list_levels(self, below_min: bool, page: int, page_size: int):
        offset = (page - 1) * page_size
        return await self.repo.get_all_levels(below_min=below_min, offset=offset, limit=page_size)

    async def get_level(self, product_sku: str) -> InventoryLevel:
        level = await self.repo.get_level(product_sku)
        if not level:
            raise NotFoundError("InventoryLevel", product_sku)
        return level

    async def adjust(self, product_sku: str, qty: float, notes: str | None = None) -> InventoryLevel:
        level = await self.repo.get_level(product_sku)
        current = level.stock_qty if level else 0.0
        new_qty = current + qty
        if new_qty < 0:
            raise BusinessError(f"Cannot reduce stock below 0. Current: {current}, adjustment: {qty}")
        await self.repo.add_movement(
            product_sku=product_sku,
            type=MovementType.AJUSTE,
            qty=qty,
            notes=notes,
        )
        return await self.repo.upsert_level(product_sku, qty)

    async def apply_sale(self, product_sku: str, qty: float, sale_id: str) -> InventoryLevel:
        level = await self.repo.get_level(product_sku)
        current = level.stock_qty if level else 0.0
        if current < qty:
            raise BusinessError(f"Insufficient stock for {product_sku}. Available: {current}, required: {qty}")
        await self.repo.add_movement(
            product_sku=product_sku,
            type=MovementType.SALIDA,
            qty=-qty,
            reference_id=sale_id,
            reference_type="sale",
        )
        return await self.repo.upsert_level(product_sku, -qty)

    async def apply_purchase_receipt(self, product_sku: str, qty: float, purchase_id: str) -> InventoryLevel:
        await self.repo.add_movement(
            product_sku=product_sku,
            type=MovementType.ENTRADA,
            qty=qty,
            reference_id=purchase_id,
            reference_type="purchase",
        )
        return await self.repo.upsert_level(product_sku, qty)

    async def list_movements(self, product_sku, type, from_date, to_date, page: int, page_size: int):
        offset = (page - 1) * page_size
        return await self.repo.get_movements(
            product_sku=product_sku, type=type, from_date=from_date, to_date=to_date,
            offset=offset, limit=page_size,
        )
