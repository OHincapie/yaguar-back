from src.domains.suppliers.models import Supplier
from src.domains.suppliers.repository import SupplierRepository
from src.domains.suppliers.schemas import SupplierCreate, SupplierUpdate
from src.shared.middleware.errors import ConflictError, NotFoundError


class SupplierService:
    def __init__(self, repo: SupplierRepository):
        self.repo = repo

    async def list_suppliers(self, status, page: int, page_size: int):
        offset = (page - 1) * page_size
        return await self.repo.get_all(status=status, offset=offset, limit=page_size)

    async def get_supplier(self, id: str) -> Supplier:
        supplier = await self.repo.get_by_id(id)
        if not supplier:
            raise NotFoundError("Supplier", id)
        return supplier

    async def create_supplier(self, data: SupplierCreate) -> Supplier:
        existing = await self.repo.get_by_id(data.id)
        if existing:
            raise ConflictError(f"Supplier '{data.id}' already exists")
        supplier = Supplier(**data.model_dump())
        return await self.repo.create(supplier)

    async def update_supplier(self, id: str, data: SupplierUpdate) -> Supplier:
        supplier = await self.get_supplier(id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(supplier, field, value)
        return await self.repo.update(supplier)

    async def delete_supplier(self, id: str) -> None:
        supplier = await self.get_supplier(id)
        await self.repo.delete(supplier)
