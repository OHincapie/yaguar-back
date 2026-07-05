from src.domains.inventory.models import InventoryLevel, InventoryMovement, MovementType
from src.domains.inventory.repository import InventoryRepository
from src.shared.middleware.errors import BusinessError, NotFoundError


class InventoryService:
    def __init__(self, repo: InventoryRepository):
        self.repo = repo

    async def list_levels(self, company_id: str, below_min: bool, page: int, page_size: int):
        offset = (page - 1) * page_size
        return await self.repo.get_all_levels(company_id, below_min=below_min, offset=offset, limit=page_size)

    async def get_level(self, company_id: str, product_id: str) -> InventoryLevel:
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

    async def apply_sale(self, company_id: str, product_id: str, qty: float, sale_id: str) -> InventoryLevel:
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
