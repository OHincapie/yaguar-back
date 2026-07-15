from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.expenses.models import ExpenseAccount

# Common Colombian PUC (grupo 51 — gastos operacionales de administración)
# expense accounts, seeded per company. Editable/removable afterwards.
DEFAULT_EXPENSE_ACCOUNTS = [
    ("Gastos de personal", "5105", "#EF4444"),
    ("Honorarios", "5110", "#F59E0B"),
    ("Impuestos", "5115", "#8B5CF6"),
    ("Arrendamientos", "5120", "#3B82F6"),
    ("Servicios", "5135", "#10B981"),
    ("Mantenimiento y reparaciones", "5145", "#14B8A6"),
    ("Gastos de viaje", "5155", "#F97316"),
    ("Diversos", "5195", "#6366F1"),
]


class ExpenseAccountRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self, company_id: str, active_only: bool = False) -> list[ExpenseAccount]:
        query = select(ExpenseAccount).where(ExpenseAccount.company_id == company_id)
        if active_only:
            query = query.where(ExpenseAccount.is_active == True)  # noqa: E712
        result = await self.session.exec(query.order_by(ExpenseAccount.name))  # type: ignore
        return result.all()

    async def get_by_id(self, company_id: str, id: str) -> ExpenseAccount | None:
        result = await self.session.exec(  # type: ignore
            select(ExpenseAccount).where(ExpenseAccount.company_id == company_id, ExpenseAccount.id == id)
        )
        return result.first()

    async def create(self, account: ExpenseAccount) -> ExpenseAccount:
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def update(self, account: ExpenseAccount) -> ExpenseAccount:
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def seed_defaults(self, company_id: str) -> list[ExpenseAccount]:
        accounts = [
            ExpenseAccount(company_id=company_id, name=name, puc_code=code, color=color)
            for name, code, color in DEFAULT_EXPENSE_ACCOUNTS
        ]
        for a in accounts:
            self.session.add(a)
        await self.session.commit()
        for a in accounts:
            await self.session.refresh(a)
        return accounts
