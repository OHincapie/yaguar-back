import re

import bcrypt

from src.domains.accounts.models import Company, CompanyRole, User, UserCompany
from src.domains.accounts.repository import AccountsRepository
from src.domains.accounts.schemas import LoginRequest, RegisterRequest
from src.shared.middleware.auth import create_access_token
from src.shared.middleware.errors import ConflictError, NotFoundError, UnauthorizedError


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "empresa"


class AccountsService:
    def __init__(self, repo: AccountsRepository):
        self.repo = repo

    async def register(self, data: RegisterRequest) -> tuple[str, User, Company]:
        existing = await self.repo.get_user_by_email(data.email)
        if existing:
            raise ConflictError(f"Email '{data.email}' already registered")

        base_slug = _slugify(data.company_name)
        slug = base_slug
        suffix = 1
        while await self.repo.slug_exists(slug):
            suffix += 1
            slug = f"{base_slug}-{suffix}"

        password_hash = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
        user = await self.repo.create_user(
            User(email=data.email, password_hash=password_hash, name=data.name)
        )
        company = await self.repo.create_company(Company(name=data.company_name, slug=slug))
        await self.repo.add_membership(
            UserCompany(user_id=user.id, company_id=company.id, role=CompanyRole.OWNER)
        )

        token = create_access_token(user_id=user.id, company_id=company.id)
        return token, user, company

    async def login(self, data: LoginRequest) -> tuple[str, User, Company]:
        user = await self.repo.get_user_by_email(data.email)
        if not user or not user.is_active:
            raise UnauthorizedError("Invalid credentials")
        if not bcrypt.checkpw(data.password.encode(), user.password_hash.encode()):
            raise UnauthorizedError("Invalid credentials")

        memberships = await self.repo.list_memberships(user.id)
        if not memberships:
            raise UnauthorizedError("User has no company access")

        company = await self.repo.get_company(memberships[0].company_id)
        assert company is not None
        token = create_access_token(user_id=user.id, company_id=company.id)
        return token, user, company

    async def switch_company(self, user_id: str, company_id: str) -> tuple[str, Company]:
        membership = await self.repo.get_membership(user_id, company_id)
        if not membership:
            raise NotFoundError("Company", company_id)
        company = await self.repo.get_company(company_id)
        assert company is not None
        token = create_access_token(user_id=user_id, company_id=company_id)
        return token, company

    async def list_companies(self, user_id: str) -> list[tuple[Company, CompanyRole]]:
        memberships = await self.repo.list_memberships(user_id)
        results = []
        for m in memberships:
            company = await self.repo.get_company(m.company_id)
            if company:
                results.append((company, m.role))
        return results

    async def get_me(self, user_id: str, company_id: str):
        user = await self.repo.get_user(user_id)
        company = await self.repo.get_company(company_id)
        membership = await self.repo.get_membership(user_id, company_id)
        if not user or not company or not membership:
            raise NotFoundError("User", user_id)
        return user, company, membership.role

    async def get_settings(self, company_id: str) -> Company:
        company = await self.repo.get_company(company_id)
        if not company:
            raise NotFoundError("Company", company_id)
        return company

    async def update_settings(self, company_id: str, data: dict) -> Company:
        company = await self.repo.get_company(company_id)
        if not company:
            raise NotFoundError("Company", company_id)
        for field, value in data.items():
            setattr(company, field, value)
        return await self.repo.update_company(company)
