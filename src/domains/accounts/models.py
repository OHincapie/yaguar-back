import uuid
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import DateTime
from sqlmodel import AutoString, Field, SQLModel


class CompanyRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class Company(SQLModel, table=True):
    __tablename__ = "companies"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    name: str = Field(max_length=200)
    slug: str = Field(max_length=100, unique=True, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True)
    )


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
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True)
    )
