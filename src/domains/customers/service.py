from src.domains.customers.models import Customer
from src.domains.customers.repository import CustomerRepository
from src.domains.customers.schemas import CustomerCreate, CustomerUpdate
from src.shared.middleware.errors import ConflictError, NotFoundError


class CustomerService:
    def __init__(self, repo: CustomerRepository):
        self.repo = repo

    async def list_customers(self, type, status, city: str | None, page: int, page_size: int):
        offset = (page - 1) * page_size
        return await self.repo.get_all(type=type, status=status, city=city, offset=offset, limit=page_size)

    async def get_customer(self, id: str) -> Customer:
        customer = await self.repo.get_by_id(id)
        if not customer:
            raise NotFoundError("Customer", id)
        return customer

    async def create_customer(self, data: CustomerCreate) -> Customer:
        existing = await self.repo.get_by_id(data.id)
        if existing:
            raise ConflictError(f"Customer '{data.id}' already exists")
        customer = Customer(**data.model_dump())
        return await self.repo.create(customer)

    async def update_customer(self, id: str, data: CustomerUpdate) -> Customer:
        customer = await self.get_customer(id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(customer, field, value)
        return await self.repo.update(customer)

    async def delete_customer(self, id: str) -> None:
        customer = await self.get_customer(id)
        await self.repo.delete(customer)
