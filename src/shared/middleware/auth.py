from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.shared.database import get_session
from src.shared.middleware.errors import ForbiddenError, UnauthorizedError
from src.shared.settings import settings

bearer = HTTPBearer()

OWNER_ROLES = ("owner", "admin")


@dataclass
class AuthContext:
    user_id: str
    company_id: str
    # role/modules are looked up fresh from the DB on every request (not
    # embedded in the JWT) so revoking a user's access to a module takes
    # effect immediately, not on their next login/company-switch like the
    # JWT's user_id/company_id claims do. Costs one extra query per request.
    role: str = "member"
    modules: list[str] = field(default_factory=list)

    def has_module(self, module: str) -> bool:
        return self.role in OWNER_ROLES or module in self.modules


def create_access_token(user_id: str, company_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "cid": company_id, "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthContext:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid token")

    user_id = payload.get("sub")
    company_id = payload.get("cid")
    if not user_id or not company_id:
        raise UnauthorizedError("Invalid token")

    # Import here, not at module load, to avoid a circular import with
    # src.domains.accounts.service (which imports create_access_token from
    # this module).
    from src.domains.accounts.models import UserCompany

    result = await session.exec(  # type: ignore
        select(UserCompany).where(UserCompany.user_id == user_id, UserCompany.company_id == company_id)
    )
    membership = result.first()
    if not membership:
        raise UnauthorizedError("No longer a member of this company")

    return AuthContext(
        user_id=user_id,
        company_id=company_id,
        role=membership.role.value if hasattr(membership.role, "value") else str(membership.role),
        modules=membership.modules,
    )


CurrentUser = Annotated[AuthContext, Depends(get_current_user)]


def require_module(module: str):
    """Use as a router-level dependency: gates every route in that router
    behind the given module key unless the caller is owner/admin (who
    always have full access, by design — see AuthContext.has_module)."""

    async def check(current_user: CurrentUser) -> None:
        if not current_user.has_module(module):
            raise ForbiddenError(f"Your account doesn't have access to '{module}'")

    return check


async def require_owner_or_admin(current_user: CurrentUser) -> None:
    """For account-level actions (managing users) that aren't tied to a
    business module — only owner/admin, regardless of any module grant."""
    if current_user.role not in OWNER_ROLES:
        raise ForbiddenError("Only an owner or admin can do this")
