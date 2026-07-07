from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.accounts.repository import AccountsRepository
from src.domains.accounts.schemas import (
    CompanyRead,
    CompanySettingsRead,
    CompanySettingsUpdate,
    CompanyUserCreate,
    CompanyUserRead,
    CompanyUserUpdate,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    SwitchCompanyRequest,
    TokenResponse,
)
from src.domains.accounts.service import AccountsService
from src.shared.database import get_session
from src.shared.middleware.auth import CurrentUser, require_owner_or_admin

router = APIRouter(prefix="/auth", tags=["auth"])


def get_service(session: Annotated[AsyncSession, Depends(get_session)]) -> AccountsService:
    return AccountsService(AccountsRepository(session))


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: RegisterRequest, service: Annotated[AccountsService, Depends(get_service)]):
    token, _user, _company = await service.register(data)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, service: Annotated[AccountsService, Depends(get_service)]):
    token, _user, _company = await service.login(data)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
async def me(current_user: CurrentUser, service: Annotated[AccountsService, Depends(get_service)]):
    user, company, membership = await service.get_me(current_user.user_id, current_user.company_id)
    return MeResponse(
        user_id=user.id,
        email=user.email,
        name=user.name,
        company_id=company.id,
        company_name=company.name,
        role=membership.role,
        modules=membership.modules,
    )


@router.get("/companies", response_model=list[CompanyRead])
async def list_companies(current_user: CurrentUser, service: Annotated[AccountsService, Depends(get_service)]):
    pairs = await service.list_companies(current_user.user_id)
    return [
        CompanyRead(id=company.id, name=company.name, slug=company.slug, role=role)
        for company, role in pairs
    ]


@router.post("/switch-company", response_model=TokenResponse)
async def switch_company(
    current_user: CurrentUser,
    data: SwitchCompanyRequest,
    service: Annotated[AccountsService, Depends(get_service)],
):
    token, _company = await service.switch_company(current_user.user_id, data.company_id)
    return TokenResponse(access_token=token)


@router.get("/settings", response_model=CompanySettingsRead)
async def get_settings(current_user: CurrentUser, service: Annotated[AccountsService, Depends(get_service)]):
    return await service.get_settings(current_user.company_id)


@router.put("/settings", response_model=CompanySettingsRead, dependencies=[Depends(require_owner_or_admin)])
async def update_settings(
    current_user: CurrentUser,
    data: CompanySettingsUpdate,
    service: Annotated[AccountsService, Depends(get_service)],
):
    return await service.update_settings(current_user.company_id, data.model_dump(exclude_unset=True))


def _to_user_read(membership, user) -> CompanyUserRead:
    return CompanyUserRead(
        user_id=user.id,
        name=user.name,
        email=user.email,
        role=membership.role,
        modules=membership.modules,
        is_active=user.is_active,
    )


@router.get("/users", response_model=list[CompanyUserRead], dependencies=[Depends(require_owner_or_admin)])
async def list_users(current_user: CurrentUser, service: Annotated[AccountsService, Depends(get_service)]):
    pairs = await service.list_company_users(current_user.company_id)
    return [_to_user_read(m, u) for m, u in pairs]


@router.post(
    "/users",
    response_model=CompanyUserRead,
    status_code=201,
    dependencies=[Depends(require_owner_or_admin)],
)
async def create_user(
    current_user: CurrentUser,
    data: CompanyUserCreate,
    service: Annotated[AccountsService, Depends(get_service)],
):
    membership, user = await service.create_company_user(current_user.company_id, data)
    return _to_user_read(membership, user)


@router.put("/users/{user_id}", response_model=CompanyUserRead, dependencies=[Depends(require_owner_or_admin)])
async def update_user(
    current_user: CurrentUser,
    user_id: str,
    data: CompanyUserUpdate,
    service: Annotated[AccountsService, Depends(get_service)],
):
    membership, user = await service.update_company_user(current_user.company_id, user_id, data)
    return _to_user_read(membership, user)


@router.delete("/users/{user_id}", dependencies=[Depends(require_owner_or_admin)])
async def remove_user(
    current_user: CurrentUser,
    user_id: str,
    service: Annotated[AccountsService, Depends(get_service)],
):
    await service.remove_company_user(current_user.company_id, user_id)
    return {"message": "User removed"}
