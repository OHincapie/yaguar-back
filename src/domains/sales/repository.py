from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.sales.models import Sale, SaleLine, SaleStatus


class SaleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(
        self,
        status: SaleStatus | None = None,
        customer_id: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Sale], int]:
        query = select(Sale)
        if status:
            query = query.where(Sale.status == status)
        if customer_id:
            query = query.where(Sale.customer_id == customer_id)
        if from_date:
            query = query.where(Sale.date >= from_date)
        if to_date:
            query = query.where(Sale.date <= to_date)

        count_result = await self.session.exec(select(Sale))  # type: ignore
        total = len(count_result.all())

        result = await self.session.exec(query.order_by(Sale.date.desc()).offset(offset).limit(limit))  # type: ignore
        return result.all(), total

    async def get_by_id(self, id: str) -> Sale | None:
        result = await self.session.exec(select(Sale).where(Sale.id == id))  # type: ignore
        return result.first()

    async def get_lines(self, sale_id: str) -> list[SaleLine]:
        result = await self.session.exec(select(SaleLine).where(SaleLine.sale_id == sale_id))  # type: ignore
        return result.all()

    async def create(self, sale: Sale, lines: list[SaleLine]) -> Sale:
        self.session.add(sale)
        for line in lines:
            self.session.add(line)
        await self.session.commit()
        await self.session.refresh(sale)
        return sale

    async def update(self, sale: Sale) -> Sale:
        self.session.add(sale)
        await self.session.commit()
        await self.session.refresh(sale)
        return sale
