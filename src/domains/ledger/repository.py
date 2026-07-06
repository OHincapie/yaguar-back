from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.ledger.models import LedgerCategory, LedgerEntry


class LedgerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(
        self,
        company_id: str,
        category: LedgerCategory | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[LedgerEntry], int]:
        query = select(LedgerEntry).where(LedgerEntry.company_id == company_id)
        if category:
            query = query.where(LedgerEntry.category == category)
        if from_date:
            query = query.where(LedgerEntry.date >= from_date)
        if to_date:
            query = query.where(LedgerEntry.date <= to_date)

        count_result = await self.session.exec(query)  # type: ignore
        total = len(count_result.all())

        result = await self.session.exec(query.order_by(LedgerEntry.date.desc()).offset(offset).limit(limit))  # type: ignore
        return result.all(), total

    async def create(self, entry: LedgerEntry) -> LedgerEntry:
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def get_by_reference(self, company_id: str, reference_id: str, reference_type: str) -> LedgerEntry | None:
        result = await self.session.exec(  # type: ignore
            select(LedgerEntry).where(
                LedgerEntry.company_id == company_id,
                LedgerEntry.reference_id == reference_id,
                LedgerEntry.reference_type == reference_type,
            )
        )
        return result.first()

    async def update(self, entry: LedgerEntry) -> LedgerEntry:
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry
