from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.customers.models import CustomerStatus, CustomerType
from src.domains.customers.repository import CustomerRepository
from src.domains.customers.schemas import CustomerCreate, CustomerRead, CustomerUpdate
from src.domains.customers.service import CustomerService
from src.shared.database import get_session
from src.shared.middleware.auth import CurrentUser, require_module
from src.shared.types import MessageResponse, PaginatedResponse

router = APIRouter(prefix="/customers", tags=["customers"])
# Only mutating endpoints are module-gated — customer names are read from
# Ventas, POS and Dashboard too.
_require_clientes = Depends(require_module("clientes"))


def get_service(session: Annotated[AsyncSession, Depends(get_session)]) -> CustomerService:
    return CustomerService(CustomerRepository(session))


@router.get("", response_model=PaginatedResponse[CustomerRead])
async def list_customers(
    current_user: CurrentUser,
    service: Annotated[CustomerService, Depends(get_service)],
    type: CustomerType | None = None,
    status: CustomerStatus | None = None,
    city: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    customers, total = await service.list_customers(
        current_user.company_id, type=type, status=status, city=city, page=page, page_size=page_size
    )
    pages = (total + page_size - 1) // page_size
    return PaginatedResponse(data=customers, total=total, page=page, page_size=page_size, pages=pages)


@router.post("", response_model=CustomerRead, status_code=201, dependencies=[_require_clientes])
async def create_customer(current_user: CurrentUser, data: CustomerCreate, service: Annotated[CustomerService, Depends(get_service)]):
    return await service.create_customer(current_user.company_id, data)


@router.get("/{id}", response_model=CustomerRead)
async def get_customer(current_user: CurrentUser, id: str, service: Annotated[CustomerService, Depends(get_service)]):
    return await service.get_customer(current_user.company_id, id)


@router.put("/{id}", response_model=CustomerRead, dependencies=[_require_clientes])
async def update_customer(current_user: CurrentUser, id: str, data: CustomerUpdate, service: Annotated[CustomerService, Depends(get_service)]):
    return await service.update_customer(current_user.company_id, id, data)


@router.delete("/{id}", response_model=MessageResponse, dependencies=[_require_clientes])
async def delete_customer(current_user: CurrentUser, id: str, service: Annotated[CustomerService, Depends(get_service)]):
    await service.delete_customer(current_user.company_id, id)
    return MessageResponse(message=f"Customer '{id}' deleted")
