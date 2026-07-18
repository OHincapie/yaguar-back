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
    # Empty for owner/admin — the frontend should treat that as "all
    # modules", not "no modules"; see AuthContext.has_module on the backend.
    modules: list[str]
    # True when someone else (an admin) chose this user's current password —
    # the frontend blocks the whole app behind a "set a new password" screen
    # while this is true. See User.must_change_password.
    must_change_password: bool


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class CompanySettingsRead(BaseModel):
    discount_enabled: bool
    discount_pct: float
    tax_enabled: bool
    tax_pct: float
    credit_days: int
    margin_basis: str
    business_context: str

    model_config = {"from_attributes": True}


class CompanySettingsUpdate(BaseModel):
    discount_enabled: bool | None = None
    discount_pct: float | None = None
    tax_enabled: bool | None = None
    tax_pct: float | None = None
    credit_days: int | None = None
    margin_basis: str | None = None
    business_context: str | None = None


class CompanyUserRead(BaseModel):
    user_id: str
    name: str
    email: str
    role: CompanyRole
    modules: list[str]
    is_active: bool


class CompanyUserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: CompanyRole = CompanyRole.MEMBER
    modules: list[str] = []


class CompanyUserUpdate(BaseModel):
    name: str | None = None
    role: CompanyRole | None = None
    modules: list[str] | None = None
    is_active: bool | None = None
    # Lets an owner/admin reset another user's password directly — there's
    # no "forgot password" email flow in this app, this is the only way a
    # locked-out user gets back in.
    password: str | None = None
