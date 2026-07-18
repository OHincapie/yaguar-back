from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.purchases.models import Purchase, PurchaseLine, PurchaseStatus


class PurchaseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(
        self,
        company_id: str,
        status: PurchaseStatus | None = None,
        supplier_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Purchase], int]:
        query = select(Purchase).where(Purchase.company_id == company_id)
        if status:
            query = query.where(Purchase.status == status)
        if supplier_id:
            query = query.where(Purchase.supplier_id == supplier_id)

        count_result = await self.session.exec(query)  # type: ignore
        total = len(count_result.all())

        result = await self.session.exec(query.order_by(Purchase.date.desc()).offset(offset).limit(limit))  # type: ignore
        return result.all(), total

    async def get_by_id(self, company_id: str, id: str) -> Purchase | None:
        result = await self.session.exec(  # type: ignore
            select(Purchase).where(Purchase.company_id == company_id, Purchase.id == id)
        )
        return result.first()

    async def get_by_code(self, company_id: str, code: str) -> Purchase | None:
        result = await self.session.exec(  # type: ignore
            select(Purchase).where(Purchase.company_id == company_id, Purchase.code == code)
        )
        return result.first()

    async def count_for_company(self, company_id: str) -> int:
        result = await self.session.exec(  # type: ignore
            select(func.count()).select_from(Purchase).where(Purchase.company_id == company_id)
        )
        return int(result.one())

    async def get_lines(self, purchase_id: str) -> list[PurchaseLine]:
        result = await self.session.exec(select(PurchaseLine).where(PurchaseLine.purchase_id == purchase_id))  # type: ignore
        return result.all()

    async def products_with_open_orders(self, company_id: str) -> set[str]:
        """Product ids sitting on a purchase order that hasn't landed yet
        (borrador/en camino/aduana). Yaco uses this to avoid re-proposing a
        reorder for something already on its way — a received or cancelled
        order no longer counts."""
        open_statuses = (PurchaseStatus.BORRADOR, PurchaseStatus.EN_CAMINO, PurchaseStatus.ADUANA)
        result = await self.session.exec(  # type: ignore
            select(PurchaseLine.product_id)
            .join(Purchase, PurchaseLine.purchase_id == Purchase.id)
            .where(Purchase.company_id == company_id, Purchase.status.in_(open_statuses))
        )
        return set(result.all())

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

    async def replace_lines(self, purchase_id: str, lines: list[PurchaseLine]) -> list[PurchaseLine]:
        existing = await self.get_lines(purchase_id)
        for line in existing:
            await self.session.delete(line)
        for line in lines:
            self.session.add(line)
        await self.session.commit()
        for line in lines:
            await self.session.refresh(line)
        return lines

    async def delete(self, purchase: Purchase) -> None:
        await self.session.delete(purchase)
        await self.session.commit()
