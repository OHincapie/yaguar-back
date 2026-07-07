from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.suppliers.models import SupplierStatus
from src.domains.suppliers.repository import SupplierRepository
from src.domains.suppliers.schemas import SupplierCreate, SupplierRead, SupplierUpdate
from src.domains.suppliers.service import SupplierService
from src.shared.database import get_session
from src.shared.middleware.auth import CurrentUser, require_module
from src.shared.types import MessageResponse, PaginatedResponse

router = APIRouter(prefix="/suppliers", tags=["suppliers"], dependencies=[Depends(require_module("proveedores"))])


def get_service(session: Annotated[AsyncSession, Depends(get_session)]) -> SupplierService:
    return SupplierService(SupplierRepository(session))


@router.get("", response_model=PaginatedResponse[SupplierRead])
async def list_suppliers(
    current_user: CurrentUser,
    service: Annotated[SupplierService, Depends(get_service)],
    status: SupplierStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    suppliers, total = await service.list_suppliers(current_user.company_id, status=status, page=page, page_size=page_size)
    pages = (total + page_size - 1) // page_size
    return PaginatedResponse(data=suppliers, total=total, page=page, page_size=page_size, pages=pages)


@router.post("", response_model=SupplierRead, status_code=201)
async def create_supplier(current_user: CurrentUser, data: SupplierCreate, service: Annotated[SupplierService, Depends(get_service)]):
    return await service.create_supplier(current_user.company_id, data)


@router.get("/{id}", response_model=SupplierRead)
async def get_supplier(current_user: CurrentUser, id: str, service: Annotated[SupplierService, Depends(get_service)]):
    return await service.get_supplier(current_user.company_id, id)


@router.put("/{id}", response_model=SupplierRead)
async def update_supplier(current_user: CurrentUser, id: str, data: SupplierUpdate, service: Annotated[SupplierService, Depends(get_service)]):
    return await service.update_supplier(current_user.company_id, id, data)


@router.delete("/{id}", response_model=MessageResponse)
async def delete_supplier(current_user: CurrentUser, id: str, service: Annotated[SupplierService, Depends(get_service)]):
    await service.delete_supplier(current_user.company_id, id)
    return MessageResponse(message=f"Supplier '{id}' deleted")
