from src.domains.ledger.models import LedgerEntry
from src.domains.ledger.repository import LedgerRepository
from src.domains.ledger.schemas import LedgerEntryCreate


class LedgerService:
    def __init__(self, repo: LedgerRepository):
        self.repo = repo

    async def list_entries(self, company_id: str, category, from_date, to_date, page: int, page_size: int):
        offset = (page - 1) * page_size
        return await self.repo.get_all(
            company_id, category=category, from_date=from_date, to_date=to_date, offset=offset, limit=page_size
        )

    async def create_entry(self, company_id: str, data: LedgerEntryCreate) -> LedgerEntry:
        entry = LedgerEntry(company_id=company_id, **data.model_dump())
        return await self.repo.create(entry)
