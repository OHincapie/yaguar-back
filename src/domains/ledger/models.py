from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from sqlalchemy import DateTime
from sqlmodel import AutoString, Field, SQLModel


class LedgerCategory(StrEnum):
    VENTAS = "Ventas"
    COMPRAS = "Compras"
    GASTOS = "Gastos"
    NOMINA = "Nómina"
    OTROS = "Otros"


class LedgerType(StrEnum):
    IN = "in"
    OUT = "out"


class LedgerEntry(SQLModel, table=True):
    __tablename__ = "ledger_entries"

    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: str = Field(foreign_key="companies.id", max_length=36, index=True)
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))
    concept: str = Field(max_length=300)
    category: LedgerCategory = Field(sa_type=AutoString)
    debit: float = Field(default=0.0)
    credit: float = Field(default=0.0)
    type: LedgerType = Field(sa_type=AutoString)
    reference_id: Optional[str] = Field(default=None, max_length=50)
    reference_type: Optional[str] = Field(default=None, max_length=50)
    # Set only on manual operational expenses (Gastos module) — points at the
    # company-configurable ExpenseAccount, which carries the display name,
    # optional PUC code and color. Null for auto entries (sales/purchases)
    # and for the broad enum categories.
    account_id: Optional[str] = Field(default=None, foreign_key="expense_accounts.id", max_length=36)
