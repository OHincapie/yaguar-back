from datetime import datetime

from pydantic import BaseModel

from src.domains.ledger.models import LedgerCategory, LedgerType


class LedgerEntryCreate(BaseModel):
    concept: str
    category: LedgerCategory
    debit: float = 0.0
    credit: float = 0.0
    type: LedgerType
    reference_id: str | None = None
    reference_type: str | None = None


class LedgerEntryRead(BaseModel):
    id: int
    date: datetime
    concept: str
    category: LedgerCategory
    debit: float
    credit: float
    type: LedgerType
    reference_id: str | None
    reference_type: str | None

    model_config = {"from_attributes": True}
