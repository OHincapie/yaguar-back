import uuid
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import AutoString, Column, Field, SQLModel


class CompanyRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


# Matches the frontend's nav item ids (src/lib/data.ts's `nav`) — keep them
# in sync when adding a module. "inicio" (the chat) isn't gated; everyone
# with a login can use it.
MODULE_KEYS = (
    "dashboard",
    "pos",
    "agentes",
    "ventas",
    "compras",
    "inventario",
    "proveedores",
    "clientes",
    "libro",
)


class Company(SQLModel, table=True):
    __tablename__ = "companies"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    name: str = Field(max_length=200)
    slug: str = Field(max_length=100, unique=True, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True)
    )
    # POS checkout defaults. Percentages on a 0-100 scale (matches
    # Supplier.on_time_pct elsewhere). Toggling *_enabled off means new
    # sales are recorded with that amount as 0 — it does not touch past sales.
    discount_enabled: bool = Field(default=True)
    discount_pct: float = Field(default=5.0)
    tax_enabled: bool = Field(default=True)
    tax_pct: float = Field(default=18.0)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    email: str = Field(max_length=255, unique=True, index=True)
    password_hash: str = Field(max_length=255)
    name: str = Field(max_length=200)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True)
    )


class UserCompany(SQLModel, table=True):
    __tablename__ = "user_companies"

    user_id: str = Field(foreign_key="users.id", primary_key=True, max_length=36)
    company_id: str = Field(foreign_key="companies.id", primary_key=True, max_length=36)
    role: CompanyRole = Field(default=CompanyRole.OWNER, sa_type=AutoString)
    # Only meaningful for role="member" — owner/admin always have full
    # access regardless of this list (see AuthContext.has_module). Empty
    # list for a member means "no modules granted yet".
    modules: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True)
    )
