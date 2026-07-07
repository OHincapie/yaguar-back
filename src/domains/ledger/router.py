from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.ledger.models import LedgerCategory
from src.domains.ledger.repository import LedgerRepository
from src.domains.ledger.schemas import LedgerEntryCreate, LedgerEntryRead
from src.domains.ledger.service import LedgerService
from src.shared.database import get_session
from src.shared.middleware.auth import CurrentUser, require_module
from src.shared.types import PaginatedResponse

router = APIRouter(prefix="/ledger", tags=["ledger"])
_require_libro = Depends(require_module("libro"))


def get_service(session: Annotated[AsyncSession, Depends(get_session)]) -> LedgerService:
    return LedgerService(LedgerRepository(session))


@router.get("", response_model=PaginatedResponse[LedgerEntryRead])
async def list_entries(
    current_user: CurrentUser,
    service: Annotated[LedgerService, Depends(get_service)],
    cat: LedgerCategory | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    entries, total = await service.list_entries(
        current_user.company_id, category=cat, from_date=from_date, to_date=to_date, page=page, page_size=page_size
    )
    pages = (total + page_size - 1) // page_size
    return PaginatedResponse(data=entries, total=total, page=page, page_size=page_size, pages=pages)


@router.post("", response_model=LedgerEntryRead, status_code=201, dependencies=[_require_libro])
async def create_entry(current_user: CurrentUser, data: LedgerEntryCreate, service: Annotated[LedgerService, Depends(get_service)]):
    return await service.create_entry(current_user.company_id, data)
