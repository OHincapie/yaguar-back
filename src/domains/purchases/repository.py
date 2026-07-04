from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.purchases.models import Purchase, PurchaseLine, PurchaseStatus


class PurchaseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(
        self,
        status: PurchaseStatus | None = None,
        supplier_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Purchase], int]:
        query = select(Purchase)
        if status:
            query = query.where(Purchase.status == status)
        if supplier_id:
            query = query.where(Purchase.supplier_id == supplier_id)

        count_result = await self.session.exec(select(Purchase))  # type: ignore
        total = len(count_result.all())

        result = await self.session.exec(query.order_by(Purchase.date.desc()).offset(offset).limit(limit))  # type: ignore
        return result.all(), total

    async def get_by_id(self, id: str) -> Purchase | None:
        result = await self.session.exec(select(Purchase).where(Purchase.id == id))  # type: ignore
        return result.first()

    async def get_lines(self, purchase_id: str) -> list[PurchaseLine]:
        result = await self.session.exec(select(PurchaseLine).where(PurchaseLine.purchase_id == purchase_id))  # type: ignore
        return result.all()

    async def create(self, purchase: Purchase, lines: list[PurchaseLine]) -> Purchase:
        self.session.add(purchase)
        for line in lines:
            self.session.add(line)
        await self.session.commit()
        await self.session.refresh(purchase)
        return purchase

    async def update(self, purchase: Purchase) -> Purchase:
        self.session.add(purchase)
        await self.session.commit()
        await self.session.refresh(purchase)
        return purchase
