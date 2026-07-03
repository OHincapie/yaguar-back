from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.inventory.repository import InventoryRepository
from src.domains.inventory.service import InventoryService
from src.domains.ledger.repository import LedgerRepository
from src.domains.purchases.models import PurchaseStatus
from src.domains.purchases.repository import PurchaseRepository
from src.domains.purchases.schemas import (
    PurchaseCreate,
    PurchaseLineRead,
    PurchaseRead,
    PurchaseStatusUpdate,
)
from src.domains.purchases.service import PurchaseService
from src.shared.database import get_session
from src.shared.middleware.auth import CurrentUser
from src.shared.types import PaginatedResponse

router = APIRouter(prefix="/purchases", tags=["purchases"])


def get_service(session: Annotated[AsyncSession, Depends(get_session)]) -> PurchaseService:
    return PurchaseService(
        PurchaseRepository(session),
        InventoryService(InventoryRepository(session)),
        LedgerRepository(session),
    )


@router.get("", response_model=PaginatedResponse[PurchaseRead])
async def list_purchases(
    _: CurrentUser,
    service: Annotated[PurchaseService, Depends(get_service)],
    status: PurchaseStatus | None = None,
    supplier: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    purchases, total = await service.list_purchases(status=status, supplier_id=supplier, page=page, page_size=page_size)
    pages = (total + page_size - 1) // page_size
    return PaginatedResponse(data=purchases, total=total, page=page, page_size=page_size, pages=pages)


@router.post("", response_model=PurchaseRead, status_code=201)
async def create_purchase(_: CurrentUser, data: PurchaseCreate, service: Annotated[PurchaseService, Depends(get_service)]):
    return await service.create_purchase(data)


@router.get("/{id}", response_model=PurchaseRead)
async def get_purchase(_: CurrentUser, id: str, service: Annotated[PurchaseService, Depends(get_service)]):
    return await service.get_purchase(id)


@router.put("/{id}/status", response_model=PurchaseRead)
async def update_status(_: CurrentUser, id: str, data: PurchaseStatusUpdate, service: Annotated[PurchaseService, Depends(get_service)]):
    return await service.update_status(id, data)


@router.get("/{id}/lines", response_model=list[PurchaseLineRead])
async def get_lines(_: CurrentUser, id: str, service: Annotated[PurchaseService, Depends(get_service)]):
    return await service.get_lines(id)


@router.post("/{id}/receive", response_model=PurchaseRead)
async def receive_purchase(_: CurrentUser, id: str, service: Annotated[PurchaseService, Depends(get_service)]):
    return await service.receive(id)
