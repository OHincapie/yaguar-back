from pydantic import BaseModel, EmailStr

from src.domains.accounts.models import CompanyRole


class RegisterRequest(BaseModel):
    company_name: str
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SwitchCompanyRequest(BaseModel):
    company_id: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CompanyRead(BaseModel):
    id: str
    name: str
    slug: str
    role: CompanyRole

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    user_id: str
    email: str
    name: str
    company_id: str
    company_name: str
    role: CompanyRole


class CompanySettingsRead(BaseModel):
    discount_enabled: bool
    discount_pct: float
    tax_enabled: bool
    tax_pct: float

    model_config = {"from_attributes": True}


class CompanySettingsUpdate(BaseModel):
    discount_enabled: bool | None = None
    discount_pct: float | None = None
    tax_enabled: bool | None = None
    tax_pct: float | None = None
