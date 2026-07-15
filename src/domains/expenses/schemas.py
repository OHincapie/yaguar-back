from datetime import datetime

from pydantic import BaseModel


class ExpenseAccountRead(BaseModel):
    id: str
    name: str
    puc_code: str | None
    color: str
    is_active: bool

    model_config = {"from_attributes": True}


class ExpenseAccountCreate(BaseModel):
    name: str
    puc_code: str | None = None
    # Optional — the service picks a palette color when omitted.
    color: str | None = None


class ExpenseAccountUpdate(BaseModel):
    name: str | None = None
    puc_code: str | None = None
    color: str | None = None
    is_active: bool | None = None


class GastoCreate(BaseModel):
    concept: str
    account_id: str
    amount: float
    # Optional; defaults to now on the server.
    date: datetime | None = None


class GastoUpdate(BaseModel):
    concept: str | None = None
    account_id: str | None = None
    amount: float | None = None
    date: datetime | None = None


class GastoRead(BaseModel):
    """A manual operational expense — a ledger OUT entry with an
    ExpenseAccount, flattened with the account's display fields so the UI
    doesn't need a second lookup."""

    id: int
    date: datetime
    concept: str
    amount: float
    account_id: str | None
    account_name: str
    account_code: str | None
    account_color: str
