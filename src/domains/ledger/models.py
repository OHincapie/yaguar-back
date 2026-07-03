from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from sqlmodel import Field, SQLModel


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
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    concept: str = Field(max_length=300)
    category: LedgerCategory
    debit: float = Field(default=0.0)
    credit: float = Field(default=0.0)
    type: LedgerType
    reference_id: Optional[str] = Field(default=None, max_length=50)
    reference_type: Optional[str] = Field(default=None, max_length=50)
