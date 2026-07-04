from src.domains.customers.models import Customer
from src.domains.customers.repository import CustomerRepository
from src.domains.customers.schemas import CustomerCreate, CustomerUpdate
from src.shared.middleware.errors import ConflictError, NotFoundError


class CustomerService:
    def __init__(self, repo: CustomerRepository):
        self.repo = repo

    async def list_customers(self, company_id: str, type, status, city: str | None, page: int, page_size: int):
        offset = (page - 1) * page_size
        return await self.repo.get_all(company_id, type=type, status=status, city=city, offset=offset, limit=page_size)

    async def get_customer(self, company_id: str, code: str) -> Customer:
        customer = await self.repo.get_by_code(company_id, code)
        if not customer:
            raise NotFoundError("Customer", code)
        return customer

    async def create_customer(self, company_id: str, data: CustomerCreate) -> Customer:
        existing = await self.repo.get_by_code(company_id, data.code)
        if existing:
            raise ConflictError(f"Customer '{data.code}' already exists")
        customer = Customer(company_id=company_id, **data.model_dump())
        return await self.repo.create(customer)

    async def update_customer(self, company_id: str, code: str, data: CustomerUpdate) -> Customer:
        customer = await self.get_customer(company_id, code)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(customer, field, value)
        return await self.repo.update(customer)

    async def delete_customer(self, company_id: str, code: str) -> None:
        customer = await self.get_customer(company_id, code)
        await self.repo.delete(customer)
