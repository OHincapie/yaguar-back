from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.accounts.repository import AccountsRepository
from src.domains.accounts.schemas import (
    CompanyRead,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    SwitchCompanyRequest,
    TokenResponse,
)
from src.domains.accounts.service import AccountsService
from src.shared.database import get_session
from src.shared.middleware.auth import CurrentUser

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
    user, company, role = await service.get_me(current_user.user_id, current_user.company_id)
    return MeResponse(
        user_id=user.id,
        email=user.email,
        name=user.name,
        company_id=company.id,
        company_name=company.name,
        role=role,
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
