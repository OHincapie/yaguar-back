from datetime import datetime, timezone

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.inventory.models import InventoryLevel, InventoryMovement, MovementType


class InventoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_level(self, product_sku: str) -> InventoryLevel | None:
        result = await self.session.exec(  # type: ignore
            select(InventoryLevel).where(InventoryLevel.product_sku == product_sku)
        )
        return result.first()

    async def get_all_levels(self, below_min: bool = False, offset: int = 0, limit: int = 50) -> tuple[list[InventoryLevel], int]:
        query = select(InventoryLevel)
        if below_min:
            query = query.where(InventoryLevel.stock_qty <= InventoryLevel.min_stock)

        count_result = await self.session.exec(select(InventoryLevel))  # type: ignore
        total = len(count_result.all())

        result = await self.session.exec(query.offset(offset).limit(limit))  # type: ignore
        return result.all(), total

    async def upsert_level(self, product_sku: str, qty_delta: float, min_stock: float | None = None) -> InventoryLevel:
        level = await self.get_level(product_sku)
        if level is None:
            level = InventoryLevel(product_sku=product_sku, stock_qty=qty_delta, min_stock=min_stock or 0.0)
        else:
            level.stock_qty += qty_delta
            if min_stock is not None:
                level.min_stock = min_stock
            level.last_updated = datetime.now(timezone.utc)
        self.session.add(level)
        await self.session.commit()
        await self.session.refresh(level)
        return level

    async def set_level(self, product_sku: str, stock_qty: float, min_stock: float | None = None) -> InventoryLevel:
        level = await self.get_level(product_sku)
        if level is None:
            level = InventoryLevel(product_sku=product_sku, stock_qty=stock_qty, min_stock=min_stock or 0.0)
        else:
            level.stock_qty = stock_qty
            if min_stock is not None:
                level.min_stock = min_stock
            level.last_updated = datetime.now(timezone.utc)
        self.session.add(level)
        await self.session.commit()
        await self.session.refresh(level)
        return level

    async def add_movement(
        self,
        product_sku: str,
        type: MovementType,
        qty: float,
        reference_id: str | None = None,
        reference_type: str | None = None,
        notes: str | None = None,
    ) -> InventoryMovement:
        movement = InventoryMovement(
            product_sku=product_sku,
            type=type,
            qty=qty,
            reference_id=reference_id,
            reference_type=reference_type,
            notes=notes,
        )
        self.session.add(movement)
        await self.session.commit()
        await self.session.refresh(movement)
        return movement

    async def get_movements(
        self,
        product_sku: str | None = None,
        type: MovementType | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[InventoryMovement], int]:
        query = select(InventoryMovement)
        if product_sku:
            query = query.where(InventoryMovement.product_sku == product_sku)
        if type:
            query = query.where(InventoryMovement.type == type)
        if from_date:
            query = query.where(InventoryMovement.date >= from_date)
        if to_date:
            query = query.where(InventoryMovement.date <= to_date)

        count_result = await self.session.exec(query)  # type: ignore
        total = len(count_result.all())

        result = await self.session.exec(query.order_by(InventoryMovement.date.desc()).offset(offset).limit(limit))  # type: ignore
        return result.all(), total
