from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.inventory.models import MovementType
from src.domains.inventory.repository import InventoryRepository
from src.domains.inventory.schemas import InventoryAdjust, InventoryLevelRead, InventoryMovementRead
from src.domains.inventory.service import InventoryService
from src.domains.products.repository import ProductRepository
from src.shared.database import get_session
from src.shared.middleware.auth import CurrentUser
from src.shared.types import PaginatedResponse

router = APIRouter(prefix="/inventory", tags=["inventory"])


def get_service(session: Annotated[AsyncSession, Depends(get_session)]) -> InventoryService:
    return InventoryService(InventoryRepository(session), ProductRepository(session))


@router.get("", response_model=PaginatedResponse[InventoryLevelRead])
async def list_inventory(
    current_user: CurrentUser,
    service: Annotated[InventoryService, Depends(get_service)],
    below_min: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    levels, total = await service.list_levels(current_user.company_id, below_min=below_min, page=page, page_size=page_size)
    pages = (total + page_size - 1) // page_size
    data = [
        InventoryLevelRead(**level.model_dump(), is_below_min=level.stock_qty <= level.min_stock)
        for level in levels
    ]
    return PaginatedResponse(data=data, total=total, page=page, page_size=page_size, pages=pages)


@router.get("/movements", response_model=PaginatedResponse[InventoryMovementRead])
async def list_movements(
    current_user: CurrentUser,
    service: Annotated[InventoryService, Depends(get_service)],
    product_id: str | None = None,
    type: MovementType | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    movements, total = await service.list_movements(
        current_user.company_id, product_id=product_id, type=type, from_date=from_date, to_date=to_date,
        page=page, page_size=page_size,
    )
    pages = (total + page_size - 1) // page_size
    return PaginatedResponse(data=movements, total=total, page=page, page_size=page_size, pages=pages)


@router.get("/{product_id}", response_model=InventoryLevelRead)
async def get_level(current_user: CurrentUser, product_id: str, service: Annotated[InventoryService, Depends(get_service)]):
    level = await service.get_level(current_user.company_id, product_id)
    return InventoryLevelRead(**level.model_dump(), is_below_min=level.stock_qty <= level.min_stock)


@router.post("/{product_id}/adjust", response_model=InventoryLevelRead)
async def adjust_inventory(
    current_user: CurrentUser, product_id: str, data: InventoryAdjust, service: Annotated[InventoryService, Depends(get_service)]
):
    level = await service.adjust(
        current_user.company_id, product_id, data.qty, min_stock=data.min_stock, notes=data.notes
    )
    return InventoryLevelRead(**level.model_dump(), is_below_min=level.stock_qty <= level.min_stock)
