from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.customers.models import Customer, CustomerStatus, CustomerType
from src.shared.middleware.errors import ConflictError


class CustomerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(
        self,
        company_id: str,
        type: CustomerType | None = None,
        status: CustomerStatus | None = None,
        city: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Customer], int]:
        query = select(Customer).where(Customer.company_id == company_id)
        if type:
            query = query.where(Customer.type == type)
        if status:
            query = query.where(Customer.status == status)
        if city:
            query = query.where(Customer.city.ilike(f"%{city}%"))

        count_result = await self.session.exec(query)  # type: ignore
        total = len(count_result.all())

        result = await self.session.exec(query.offset(offset).limit(limit))  # type: ignore
        return result.all(), total

    async def get_by_id(self, company_id: str, id: str) -> Customer | None:
        result = await self.session.exec(  # type: ignore
            select(Customer).where(Customer.company_id == company_id, Customer.id == id)
        )
        return result.first()

    async def get_by_code(self, company_id: str, code: str) -> Customer | None:
        result = await self.session.exec(  # type: ignore
            select(Customer).where(Customer.company_id == company_id, Customer.code == code)
        )
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
        code = customer.code  # read before rollback expires the instance's attributes
        await self.session.delete(customer)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(f"Can't delete '{code}' — it has sales tied to it") from exc
