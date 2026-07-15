from datetime import datetime, timezone

from src.domains.expenses.models import ExpenseAccount
from src.domains.expenses.repository import ExpenseAccountRepository
from src.domains.expenses.schemas import (
    ExpenseAccountCreate,
    ExpenseAccountUpdate,
    GastoCreate,
    GastoRead,
    GastoUpdate,
)
from src.domains.ledger.models import LedgerCategory, LedgerEntry, LedgerType
from src.domains.ledger.repository import LedgerRepository
from src.shared.middleware.errors import BusinessError, ConflictError, NotFoundError

# Distinct default colors for auto-assigned expense-account colors.
_PALETTE = (
    "#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899", "#EF4444",
    "#14B8A6", "#F97316", "#6366F1", "#84CC16", "#06B6D4", "#D946EF",
)


class ExpenseService:
    def __init__(self, account_repo: ExpenseAccountRepository, ledger_repo: LedgerRepository):
        self.account_repo = account_repo
        self.ledger_repo = ledger_repo

    # --- Expense accounts (configurable chart) --------------------------

    async def list_accounts(self, company_id: str, active_only: bool = False) -> list[ExpenseAccount]:
        return await self.account_repo.get_all(company_id, active_only=active_only)

    async def create_account(self, company_id: str, data: ExpenseAccountCreate) -> ExpenseAccount:
        name = data.name.strip()
        if not name:
            raise BusinessError("La cuenta necesita un nombre")
        existing = await self.account_repo.get_all(company_id)
        if any(a.name.strip().lower() == name.lower() for a in existing):
            raise ConflictError(f"Ya existe una cuenta '{name}'")
        color = data.color or self._pick_color(existing)
        return await self.account_repo.create(
            ExpenseAccount(company_id=company_id, name=name, puc_code=data.puc_code, color=color)
        )

    async def update_account(self, company_id: str, id: str, data: ExpenseAccountUpdate) -> ExpenseAccount:
        account = await self.account_repo.get_by_id(company_id, id)
        if not account:
            raise NotFoundError("ExpenseAccount", id)
        if data.name is not None:
            name = data.name.strip()
            if not name:
                raise BusinessError("La cuenta necesita un nombre")
            existing = await self.account_repo.get_all(company_id)
            if any(a.id != id and a.name.strip().lower() == name.lower() for a in existing):
                raise ConflictError(f"Ya existe una cuenta '{name}'")
            account.name = name
        if data.puc_code is not None:
            account.puc_code = data.puc_code or None
        if data.color is not None:
            account.color = data.color
        if data.is_active is not None:
            account.is_active = data.is_active
        return await self.account_repo.update(account)

    @classmethod
    def _pick_color(cls, existing: list[ExpenseAccount]) -> str:
        used = {a.color.upper() for a in existing}
        for c in _PALETTE:
            if c.upper() not in used:
                return c
        return _PALETTE[len(existing) % len(_PALETTE)]

    # --- Gastos (manual expenses = ledger OUT entries) ------------------

    async def _to_read(self, entry: LedgerEntry, accounts: dict[str, ExpenseAccount]) -> GastoRead:
        account = accounts.get(entry.account_id) if entry.account_id else None
        return GastoRead(
            id=entry.id,
            date=entry.date,
            concept=entry.concept,
            amount=entry.debit,
            account_id=entry.account_id,
            account_name=account.name if account else "Cuenta eliminada",
            account_code=account.puc_code if account else None,
            account_color=account.color if account else "#94A3B8",
        )

    async def list_gastos(self, company_id: str, page: int, page_size: int) -> tuple[list[GastoRead], int]:
        offset = (page - 1) * page_size
        entries, total = await self.ledger_repo.get_expenses(company_id, offset=offset, limit=page_size)
        accounts = {a.id: a for a in await self.account_repo.get_all(company_id)}
        return [await self._to_read(e, accounts) for e in entries], total

    async def register_gasto(self, company_id: str, data: GastoCreate) -> GastoRead:
        account = await self.account_repo.get_by_id(company_id, data.account_id)
        if not account or not account.is_active:
            raise BusinessError("Cuenta de gasto desconocida o inactiva")
        if data.amount <= 0:
            raise BusinessError("El monto del gasto debe ser positivo")

        entry = LedgerEntry(
            company_id=company_id,
            date=data.date or datetime.now(timezone.utc),
            concept=data.concept.strip() or account.name,
            category=LedgerCategory.GASTOS,
            debit=round(data.amount, 2),
            type=LedgerType.OUT,
            account_id=account.id,
        )
        entry = await self.ledger_repo.create(entry)
        return await self._to_read(entry, {account.id: account})

    async def update_gasto(self, company_id: str, id: int, data: GastoUpdate) -> GastoRead:
        entry = await self.ledger_repo.get_by_id(company_id, id)
        if not entry or entry.account_id is None:
            raise NotFoundError("Gasto", str(id))
        if data.concept is not None:
            entry.concept = data.concept.strip() or entry.concept
        if data.amount is not None:
            if data.amount <= 0:
                raise BusinessError("El monto del gasto debe ser positivo")
            entry.debit = round(data.amount, 2)
        if data.account_id is not None:
            account = await self.account_repo.get_by_id(company_id, data.account_id)
            if not account or not account.is_active:
                raise BusinessError("Cuenta de gasto desconocida o inactiva")
            entry.account_id = account.id
        if data.date is not None:
            entry.date = data.date
        entry = await self.ledger_repo.update(entry)
        accounts = {a.id: a for a in await self.account_repo.get_all(company_id)}
        return await self._to_read(entry, accounts)

    async def delete_gasto(self, company_id: str, id: int) -> None:
        entry = await self.ledger_repo.get_by_id(company_id, id)
        # Only manual expenses (with an account) can be deleted here — never
        # the auto entries from sales/purchases (managed in their modules).
        if not entry or entry.account_id is None:
            raise NotFoundError("Gasto", str(id))
        await self.ledger_repo.delete(entry)
