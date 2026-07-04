from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.shared.middleware.errors import UnauthorizedError
from src.shared.settings import settings

bearer = HTTPBearer()


@dataclass
class AuthContext:
    user_id: str
    company_id: str


def create_access_token(user_id: str, company_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "cid": company_id, "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
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
    return AuthContext(user_id=user_id, company_id=company_id)


CurrentUser = Annotated[AuthContext, Depends(get_current_user)]
