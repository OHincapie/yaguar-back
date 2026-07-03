from src.domains.ledger.models import LedgerEntry
from src.domains.ledger.repository import LedgerRepository
from src.domains.ledger.schemas import LedgerEntryCreate


class LedgerService:
    def __init__(self, repo: LedgerRepository):
        self.repo = repo

    async def list_entries(self, category, from_date, to_date, page: int, page_size: int):
        offset = (page - 1) * page_size
        return await self.repo.get_all(category=category, from_date=from_date, to_date=to_date, offset=offset, limit=page_size)

    async def create_entry(self, data: LedgerEntryCreate) -> LedgerEntry:
        entry = LedgerEntry(**data.model_dump())
        return await self.repo.create(entry)
