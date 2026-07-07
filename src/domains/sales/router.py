from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.accounts.repository import AccountsRepository
from src.domains.inventory.repository import InventoryRepository
from src.domains.inventory.service import InventoryService
from src.domains.ledger.repository import LedgerRepository
from src.domains.products.repository import ProductRepository
from src.domains.sales.models import SaleStatus
from src.domains.sales.repository import SaleRepository
from src.domains.sales.schemas import SaleCreate, SaleLineRead, SaleRead, SaleStatusUpdate, SaleUpdate
from src.domains.sales.service import SaleService
from src.shared.database import get_session
from src.shared.middleware.auth import CurrentUser, require_module
from src.shared.types import PaginatedResponse

router = APIRouter(prefix="/sales", tags=["sales"], dependencies=[Depends(require_module("ventas"))])


def get_service(session: Annotated[AsyncSession, Depends(get_session)]) -> SaleService:
    return SaleService(
        SaleRepository(session),
        InventoryService(InventoryRepository(session), ProductRepository(session)),
        LedgerRepository(session),
        AccountsRepository(session),
    )


@router.get("", response_model=PaginatedResponse[SaleRead])
async def list_sales(
    current_user: CurrentUser,
    service: Annotated[SaleService, Depends(get_service)],
    status: SaleStatus | None = None,
    customer: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    sales, total = await service.list_sales(
        current_user.company_id, status=status, customer_id=customer, from_date=from_date, to_date=to_date,
        page=page, page_size=page_size,
    )
    pages = (total + page_size - 1) // page_size
    return PaginatedResponse(data=sales, total=total, page=page, page_size=page_size, pages=pages)


@router.post("", response_model=SaleRead, status_code=201)
async def create_sale(current_user: CurrentUser, data: SaleCreate, service: Annotated[SaleService, Depends(get_service)]):
    return await service.create_sale(current_user.company_id, data)


@router.get("/{code}", response_model=SaleRead)
async def get_sale(current_user: CurrentUser, code: str, service: Annotated[SaleService, Depends(get_service)]):
    return await service.get_sale(current_user.company_id, code)


@router.put("/{code}/status", response_model=SaleRead)
async def update_status(current_user: CurrentUser, code: str, data: SaleStatusUpdate, service: Annotated[SaleService, Depends(get_service)]):
    return await service.update_status(current_user.company_id, code, data)


@router.put("/{code}", response_model=SaleRead)
async def update_sale(current_user: CurrentUser, code: str, data: SaleUpdate, service: Annotated[SaleService, Depends(get_service)]):
    return await service.update_sale(current_user.company_id, code, data)


@router.get("/{code}/lines", response_model=list[SaleLineRead])
async def get_lines(current_user: CurrentUser, code: str, service: Annotated[SaleService, Depends(get_service)]):
    return await service.get_lines(current_user.company_id, code)
