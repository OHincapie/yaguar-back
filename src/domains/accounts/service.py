import re

import bcrypt

from src.domains.accounts.models import MODULE_KEYS, Company, CompanyRole, User, UserCompany
from src.domains.accounts.repository import AccountsRepository
from src.domains.accounts.schemas import (
    ChangePasswordRequest,
    CompanyUserCreate,
    CompanyUserUpdate,
    LoginRequest,
    RegisterRequest,
)
from src.shared.middleware.auth import OWNER_ROLES, create_access_token
from src.shared.middleware.errors import BusinessError, ConflictError, NotFoundError, UnauthorizedError


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

        # Import here, not at module load, to avoid sales <-> accounts
        # circular imports (SaleService already depends on AccountsRepository).
        from src.domains.expenses.repository import ExpenseAccountRepository
        from src.domains.sales.repository import PaymentMethodRepository

        await PaymentMethodRepository(self.repo.session).seed_defaults(company.id)
        await ExpenseAccountRepository(self.repo.session).seed_defaults(company.id)

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
        return user, company, membership

    async def get_settings(self, company_id: str) -> Company:
        company = await self.repo.get_company(company_id)
        if not company:
            raise NotFoundError("Company", company_id)
        return company

    async def update_settings(self, company_id: str, data: dict) -> Company:
        company = await self.repo.get_company(company_id)
        if not company:
            raise NotFoundError("Company", company_id)
        if "margin_basis" in data and data["margin_basis"] not in ("price", "cost"):
            raise BusinessError("margin_basis debe ser 'price' o 'cost'")
        if "business_context" in data and data["business_context"] and len(data["business_context"]) > 1500:
            raise BusinessError("El contexto del negocio no puede superar 1500 caracteres")
        for field, value in data.items():
            setattr(company, field, value)
        return await self.repo.update_company(company)

    async def list_company_users(self, company_id: str) -> list[tuple[UserCompany, User]]:
        return await self.repo.list_company_members(company_id)

    async def create_company_user(self, company_id: str, data: CompanyUserCreate) -> tuple[UserCompany, User]:
        self._validate_modules(data.modules)

        user = await self.repo.get_user_by_email(data.email)
        if user:
            if await self.repo.get_membership(user.id, company_id):
                raise ConflictError(f"'{data.email}' is already a member of this company")
        else:
            password_hash = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
            # The admin chose this password, not the user — force them to
            # pick their own on first login.
            user = await self.repo.create_user(
                User(email=data.email, password_hash=password_hash, name=data.name, must_change_password=True)
            )

        membership = await self.repo.add_membership(
            UserCompany(user_id=user.id, company_id=company_id, role=data.role, modules=data.modules)
        )
        return membership, user

    async def update_company_user(self, company_id: str, user_id: str, data: CompanyUserUpdate) -> tuple[UserCompany, User]:
        membership = await self.repo.get_membership(user_id, company_id)
        user = await self.repo.get_user(user_id)
        if not membership or not user:
            raise NotFoundError("User", user_id)

        if data.role is not None and data.role != CompanyRole.OWNER and membership.role == CompanyRole.OWNER:
            await self._ensure_not_last_owner(company_id, user_id)
        if data.modules is not None:
            self._validate_modules(data.modules)
            membership.modules = data.modules
        if data.role is not None:
            membership.role = data.role
        await self.repo.update_membership(membership)

        if data.name is not None:
            user.name = data.name
        if data.is_active is not None:
            if not data.is_active and membership.role == CompanyRole.OWNER:
                await self._ensure_not_last_owner(company_id, user_id)
            user.is_active = data.is_active
        if data.password is not None:
            # password_hash lives on the shared User row, not per-membership
            # — if this person belongs to more than one company (possible
            # via UserCompany), resetting it here changes their password
            # everywhere, not just in this company. No "forgot password"
            # email flow exists in this app, so this is the only recovery
            # path for a locked-out user today.
            user.password_hash = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
            # Same reasoning as account creation — the admin chose this
            # password, so force a change on the user's next login.
            user.must_change_password = True
        await self.repo.create_user(user)  # add+commit+refresh, works for updates too

        return membership, user

    async def change_password(self, user_id: str, data: ChangePasswordRequest) -> User:
        """Self-service — the logged-in user changes their own password.
        Requires the current one even though they're already authenticated
        via JWT: a captured/leaked session token shouldn't be enough on its
        own to lock the real owner out by silently rotating the password.
        Clears must_change_password regardless of whether it was set —
        this also serves as a normal "change my password" action, not just
        the forced-after-admin-reset flow."""
        user = await self.repo.get_user(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        if not bcrypt.checkpw(data.current_password.encode(), user.password_hash.encode()):
            raise UnauthorizedError("Current password is incorrect")
        user.password_hash = bcrypt.hashpw(data.new_password.encode(), bcrypt.gensalt()).decode()
        user.must_change_password = False
        return await self.repo.create_user(user)

    async def remove_company_user(self, company_id: str, user_id: str) -> None:
        membership = await self.repo.get_membership(user_id, company_id)
        if not membership:
            raise NotFoundError("User", user_id)
        if membership.role == CompanyRole.OWNER:
            await self._ensure_not_last_owner(company_id, user_id)
        await self.repo.remove_membership(membership)

    def _validate_modules(self, modules: list[str]) -> None:
        unknown = set(modules) - set(MODULE_KEYS)
        if unknown:
            raise BusinessError(f"Unknown module(s): {', '.join(sorted(unknown))}")

    async def _ensure_not_last_owner(self, company_id: str, excluding_user_id: str) -> None:
        members = await self.repo.list_company_members(company_id)
        other_owners = [
            m for m, _u in members if m.role in OWNER_ROLES and m.user_id != excluding_user_id
        ]
        if not other_owners:
            raise BusinessError("A company must keep at least one owner/admin")
