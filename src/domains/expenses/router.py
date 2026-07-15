from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.expenses.repository import ExpenseAccountRepository
from src.domains.expenses.schemas import (
    ExpenseAccountCreate,
    ExpenseAccountRead,
    ExpenseAccountUpdate,
    GastoCreate,
    GastoRead,
    GastoUpdate,
)
from src.domains.expenses.service import ExpenseService
from src.domains.ledger.repository import LedgerRepository
from src.shared.database import get_session
from src.shared.middleware.auth import CurrentUser, require_module
from src.shared.types import MessageResponse, PaginatedResponse

router = APIRouter(prefix="/expenses", tags=["expenses"])
# Reads open to any authenticated member; writes gated by the "gastos" module.
_require_gastos = Depends(require_module("gastos"))


def get_service(session: Annotated[AsyncSession, Depends(get_session)]) -> ExpenseService:
    return ExpenseService(ExpenseAccountRepository(session), LedgerRepository(session))


# --- Expense accounts (configurable) ---------------------------------------

@router.get("/accounts", response_model=list[ExpenseAccountRead])
async def list_accounts(
    current_user: CurrentUser,
    service: Annotated[ExpenseService, Depends(get_service)],
    active_only: bool = False,
):
    return await service.list_accounts(current_user.company_id, active_only=active_only)


@router.post("/accounts", response_model=ExpenseAccountRead, status_code=201, dependencies=[_require_gastos])
async def create_account(
    current_user: CurrentUser, data: ExpenseAccountCreate, service: Annotated[ExpenseService, Depends(get_service)]
):
    return await service.create_account(current_user.company_id, data)


@router.put("/accounts/{id}", response_model=ExpenseAccountRead, dependencies=[_require_gastos])
async def update_account(
    current_user: CurrentUser, id: str, data: ExpenseAccountUpdate, service: Annotated[ExpenseService, Depends(get_service)]
):
    return await service.update_account(current_user.company_id, id, data)


# --- Gastos (manual expenses) ----------------------------------------------

@router.get("", response_model=PaginatedResponse[GastoRead])
async def list_gastos(
    current_user: CurrentUser,
    service: Annotated[ExpenseService, Depends(get_service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    gastos, total = await service.list_gastos(current_user.company_id, page=page, page_size=page_size)
    pages = (total + page_size - 1) // page_size
    return PaginatedResponse(data=gastos, total=total, page=page, page_size=page_size, pages=pages)


@router.post("", response_model=GastoRead, status_code=201, dependencies=[_require_gastos])
async def register_gasto(
    current_user: CurrentUser, data: GastoCreate, service: Annotated[ExpenseService, Depends(get_service)]
):
    return await service.register_gasto(current_user.company_id, data)


@router.put("/{id}", response_model=GastoRead, dependencies=[_require_gastos])
async def update_gasto(
    current_user: CurrentUser, id: int, data: GastoUpdate, service: Annotated[ExpenseService, Depends(get_service)]
):
    return await service.update_gasto(current_user.company_id, id, data)


@router.delete("/{id}", response_model=MessageResponse, dependencies=[_require_gastos])
async def delete_gasto(current_user: CurrentUser, id: int, service: Annotated[ExpenseService, Depends(get_service)]):
    await service.delete_gasto(current_user.company_id, id)
    return MessageResponse(message=f"Gasto {id} eliminado")
