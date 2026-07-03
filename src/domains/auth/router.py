import bcrypt
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.shared.middleware.auth import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

# Demo users: username -> bcrypt hash of password
# "admin" / "admin123" — replace with DB-backed users in production
_DEMO_USERS: dict[str, bytes] = {}


def _get_demo_users() -> dict[str, bytes]:
    if not _DEMO_USERS:
        _DEMO_USERS["admin"] = bcrypt.hashpw(b"admin123", bcrypt.gensalt())
    return _DEMO_USERS


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest):
    users = _get_demo_users()
    hashed = users.get(data.username)
    if not hashed or not bcrypt.checkpw(data.password.encode(), hashed):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token(data.username)
    return TokenResponse(access_token=token)
