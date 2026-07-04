from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.suppliers.models import Supplier, SupplierStatus


class SupplierRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(
        self, company_id: str, status: SupplierStatus | None = None, offset: int = 0, limit: int = 50
    ) -> tuple[list[Supplier], int]:
        query = select(Supplier).where(Supplier.company_id == company_id)
        if status:
            query = query.where(Supplier.status == status)

        count_result = await self.session.exec(query)  # type: ignore
        total = len(count_result.all())

        result = await self.session.exec(query.offset(offset).limit(limit))  # type: ignore
        return result.all(), total

    async def get_by_id(self, company_id: str, id: str) -> Supplier | None:
        result = await self.session.exec(  # type: ignore
            select(Supplier).where(Supplier.company_id == company_id, Supplier.id == id)
        )
        return result.first()

    async def get_by_code(self, company_id: str, code: str) -> Supplier | None:
        result = await self.session.exec(  # type: ignore
            select(Supplier).where(Supplier.company_id == company_id, Supplier.code == code)
        )
        return result.first()

    async def create(self, supplier: Supplier) -> Supplier:
        self.session.add(supplier)
        await self.session.commit()
        await self.session.refresh(supplier)
        return supplier

    async def update(self, supplier: Supplier) -> Supplier:
        self.session.add(supplier)
        await self.session.commit()
        await self.session.refresh(supplier)
        return supplier

    async def delete(self, supplier: Supplier) -> None:
        await self.session.delete(supplier)
        await self.session.commit()
