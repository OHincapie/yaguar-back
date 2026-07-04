from src.domains.suppliers.models import Supplier
from src.domains.suppliers.repository import SupplierRepository
from src.domains.suppliers.schemas import SupplierCreate, SupplierUpdate
from src.shared.middleware.errors import ConflictError, NotFoundError


class SupplierService:
    def __init__(self, repo: SupplierRepository):
        self.repo = repo

    async def list_suppliers(self, company_id: str, status, page: int, page_size: int):
        offset = (page - 1) * page_size
        return await self.repo.get_all(company_id, status=status, offset=offset, limit=page_size)

    async def get_supplier(self, company_id: str, code: str) -> Supplier:
        supplier = await self.repo.get_by_code(company_id, code)
        if not supplier:
            raise NotFoundError("Supplier", code)
        return supplier

    async def create_supplier(self, company_id: str, data: SupplierCreate) -> Supplier:
        existing = await self.repo.get_by_code(company_id, data.code)
        if existing:
            raise ConflictError(f"Supplier '{data.code}' already exists")
        supplier = Supplier(company_id=company_id, **data.model_dump())
        return await self.repo.create(supplier)

    async def update_supplier(self, company_id: str, code: str, data: SupplierUpdate) -> Supplier:
        supplier = await self.get_supplier(company_id, code)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(supplier, field, value)
        return await self.repo.update(supplier)

    async def delete_supplier(self, company_id: str, code: str) -> None:
        supplier = await self.get_supplier(company_id, code)
        await self.repo.delete(supplier)
