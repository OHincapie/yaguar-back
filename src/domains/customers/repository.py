from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.customers.models import Customer, CustomerStatus, CustomerType


class CustomerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(
        self,
        type: CustomerType | None = None,
        status: CustomerStatus | None = None,
        city: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Customer], int]:
        query = select(Customer)
        if type:
            query = query.where(Customer.type == type)
        if status:
            query = query.where(Customer.status == status)
        if city:
            query = query.where(Customer.city.ilike(f"%{city}%"))

        count_result = await self.session.exec(select(Customer))  # type: ignore
        total = len(count_result.all())

        result = await self.session.exec(query.offset(offset).limit(limit))  # type: ignore
        return result.all(), total

    async def get_by_id(self, id: str) -> Customer | None:
        result = await self.session.exec(select(Customer).where(Customer.id == id))  # type: ignore
        return result.first()

    async def create(self, customer: Customer) -> Customer:
        self.session.add(customer)
        await self.session.commit()
        await self.session.refresh(customer)
        return customer

    async def update(self, customer: Customer) -> Customer:
        self.session.add(customer)
        await self.session.commit()
        await self.session.refresh(customer)
        return customer

    async def delete(self, customer: Customer) -> None:
        await self.session.delete(customer)
        await self.session.commit()
