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
from src.domains.sales.repository import PaymentMethodRepository, SaleRepository
from src.domains.sales.schemas import (
    PaymentMethodCreate,
    PaymentMethodRead,
    PaymentMethodUpdate,
    SaleCreate,
    SaleLineRead,
    SalePaymentRead,
    SaleRead,
    SaleStatusUpdate,
    SaleUpdate,
)
from src.domains.sales.service import PaymentMethodService, SaleService
from src.shared.database import get_session
from src.shared.middleware.auth import CurrentUser, require_module, require_owner_or_admin
from src.shared.types import PaginatedResponse

router = APIRouter(prefix="/sales", tags=["sales"])
# Only mutating endpoints are module-gated — sales are read by Dashboard too.
_require_ventas = Depends(require_module("ventas"))


def get_service(session: Annotated[AsyncSession, Depends(get_session)]) -> SaleService:
    return SaleService(
        SaleRepository(session),
        InventoryService(InventoryRepository(session), ProductRepository(session)),
        LedgerRepository(session),
        AccountsRepository(session),
        PaymentMethodRepository(session),
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


@router.post("", response_model=SaleRead, status_code=201, dependencies=[_require_ventas])
async def create_sale(current_user: CurrentUser, data: SaleCreate, service: Annotated[SaleService, Depends(get_service)]):
    return await service.create_sale(current_user.company_id, data)


@router.get("/{code}", response_model=SaleRead)
async def get_sale(current_user: CurrentUser, code: str, service: Annotated[SaleService, Depends(get_service)]):
    return await service.get_sale(current_user.company_id, code)


@router.put("/{code}/status", response_model=SaleRead, dependencies=[_require_ventas])
async def update_status(current_user: CurrentUser, code: str, data: SaleStatusUpdate, service: Annotated[SaleService, Depends(get_service)]):
    return await service.update_status(current_user.company_id, code, data)


@router.put("/{code}", response_model=SaleRead, dependencies=[_require_ventas])
async def update_sale(current_user: CurrentUser, code: str, data: SaleUpdate, service: Annotated[SaleService, Depends(get_service)]):
    return await service.update_sale(current_user.company_id, code, data)


@router.get("/{code}/lines", response_model=list[SaleLineRead])
async def get_lines(current_user: CurrentUser, code: str, service: Annotated[SaleService, Depends(get_service)]):
    return await service.get_lines(current_user.company_id, code)


@router.get("/{code}/payments", response_model=list[SalePaymentRead])
async def get_payments(
    current_user: CurrentUser,
    code: str,
    service: Annotated[SaleService, Depends(get_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    payments = await service.get_payments(current_user.company_id, code)
    methods = {m.id: m for m in await PaymentMethodRepository(session).get_all(current_user.company_id)}
    return [
        SalePaymentRead(
            id=p.id,
            sale_id=p.sale_id,
            payment_method_id=p.payment_method_id,
            payment_method_name=methods[p.payment_method_id].name if p.payment_method_id in methods else "—",
            amount=p.amount,
        )
        for p in payments
    ]


# Payment methods are company-wide configuration, not tied to the "ventas"
# module specifically (POS/chat use them too) — reads open to any
# authenticated member, writes owner/admin-only, same pattern as
# /auth/settings.
payment_methods_router = APIRouter(prefix="/payment-methods", tags=["sales"])


def get_payment_method_service(session: Annotated[AsyncSession, Depends(get_session)]) -> PaymentMethodService:
    return PaymentMethodService(PaymentMethodRepository(session))


@payment_methods_router.get("", response_model=list[PaymentMethodRead])
async def list_payment_methods(
    current_user: CurrentUser,
    service: Annotated[PaymentMethodService, Depends(get_payment_method_service)],
    active_only: bool = False,
):
    return await service.list_methods(current_user.company_id, active_only=active_only)


@payment_methods_router.post(
    "", response_model=PaymentMethodRead, status_code=201, dependencies=[Depends(require_owner_or_admin)]
)
async def create_payment_method(
    current_user: CurrentUser,
    data: PaymentMethodCreate,
    service: Annotated[PaymentMethodService, Depends(get_payment_method_service)],
):
    return await service.create_method(current_user.company_id, data)


@payment_methods_router.put(
    "/{id}", response_model=PaymentMethodRead, dependencies=[Depends(require_owner_or_admin)]
)
async def update_payment_method(
    current_user: CurrentUser,
    id: str,
    data: PaymentMethodUpdate,
    service: Annotated[PaymentMethodService, Depends(get_payment_method_service)],
):
    return await service.update_method(current_user.company_id, id, data)
