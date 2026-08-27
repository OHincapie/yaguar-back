from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from src.domains.sales.models import PaymentMethodConfig, Sale
from src.domains.sales.schemas import PaymentLine, SaleCreate, SaleLineCreate
from src.domains.sales.service import SaleService
from src.shared.middleware.errors import ConflictError


COMPANY_ID = "company-1"
PRODUCT_ID = "product-1"
PAYMENT_ID = "payment-1"


@dataclass
class _CheckoutState:
    stock: float = 10.0
    sales: list[Sale] = field(default_factory=list)
    ledger: list[object] = field(default_factory=list)
    staged_stock_delta: float = 0.0
    staged_sales: list[Sale] = field(default_factory=list)
    staged_ledger: list[object] = field(default_factory=list)
    rollback_count: int = 0
    fail_commit: bool = False
    commit_error: BaseException | None = None


class _SaleRepository:
    def __init__(self, state: _CheckoutState):
        self.state = state

    async def count_for_company(self, company_id: str) -> int:
        return 66

    async def reserve_next_code(self, company_id: str) -> str:
        return "V-00068"

    async def create(self, sale, lines, payments, *, commit: bool = True):
        if commit:
            if self.state.fail_commit:
                raise RuntimeError("commit failed")
            self.state.sales.append(sale)
        else:
            self.state.staged_sales.append(sale)
        return sale

    async def commit(self, sale):
        if self.state.commit_error is not None:
            raise self.state.commit_error
        if self.state.fail_commit:
            raise RuntimeError("commit failed")
        self.state.stock += self.state.staged_stock_delta
        self.state.sales.extend(self.state.staged_sales)
        self.state.ledger.extend(self.state.staged_ledger)
        self.state.staged_stock_delta = 0.0
        self.state.staged_sales.clear()
        self.state.staged_ledger.clear()
        return sale

    async def rollback(self):
        self.state.rollback_count += 1
        self.state.staged_stock_delta = 0.0
        self.state.staged_sales.clear()
        self.state.staged_ledger.clear()


class _InventoryService:
    def __init__(self, state: _CheckoutState):
        self.state = state

    async def apply_sale(self, company_id: str, product_id: str, qty: float, sale_id: str, *, commit: bool = True):
        if commit:
            self.state.stock -= qty
            stock = self.state.stock
        else:
            self.state.staged_stock_delta -= qty
            stock = self.state.stock + self.state.staged_stock_delta
        return SimpleNamespace(stock_qty=stock, min_stock=0.0, product_id=product_id)


class _LedgerRepository:
    def __init__(self, state: _CheckoutState):
        self.state = state

    async def create(self, entry, *, commit: bool = True):
        if commit:
            self.state.ledger.append(entry)
        else:
            self.state.staged_ledger.append(entry)
        return entry


class _AccountsRepository:
    async def get_company(self, company_id: str):
        return SimpleNamespace(
            discount_enabled=False,
            discount_pct=0.0,
            tax_enabled=False,
            tax_pct=0.0,
            credit_days=30,
        )


class _PaymentMethodRepository:
    async def get_by_ids(self, company_id: str, ids: list[str]):
        return [
            PaymentMethodConfig(
                id=PAYMENT_ID,
                company_id=company_id,
                name="Efectivo",
                is_credit=False,
                is_active=True,
            )
        ]


class _CustomerRepository:
    pass


class _AgentRepository:
    async def create_trigger(self, trigger, *, commit: bool = True):
        return trigger


def _sale_payload() -> SaleCreate:
    return SaleCreate(
        customer_id=None,
        payments=[PaymentLine(payment_method_id=PAYMENT_ID, amount=10_000.0)],
        lines=[SaleLineCreate(product_id=PRODUCT_ID, qty=1.0, unit_price=10_000.0, unit_cost=5_000.0)],
    )


def _build_service(*, fail_commit: bool = False, commit_error: BaseException | None = None):
    state = _CheckoutState(fail_commit=fail_commit, commit_error=commit_error)
    service = SaleService(
        _SaleRepository(state),
        _InventoryService(state),
        _LedgerRepository(state),
        _AccountsRepository(),
        _PaymentMethodRepository(),
        _CustomerRepository(),
        _AgentRepository(),
    )
    return service, state


@pytest.mark.asyncio
async def test_create_sale_rolls_back_stock_when_final_commit_fails():
    service, state = _build_service(fail_commit=True)

    with pytest.raises(RuntimeError, match="commit failed"):
        await service.create_sale(COMPANY_ID, _sale_payload())

    assert state.stock == 10.0
    assert state.sales == []
    assert state.ledger == []
    assert state.rollback_count == 1


@pytest.mark.asyncio
async def test_create_sale_commits_sale_stock_and_ledger_together():
    service, state = _build_service()

    sale = await service.create_sale(COMPANY_ID, _sale_payload())

    assert sale.code == "V-00068"
    assert state.stock == 9.0
    assert [row.code for row in state.sales] == ["V-00068"]
    assert len(state.ledger) == 1


@pytest.mark.asyncio
async def test_sale_code_integrity_error_becomes_conflict_and_rolls_back():
    database_error = IntegrityError(
        "INSERT INTO sales",
        {},
        RuntimeError("duplicate key value violates unique constraint uq_sales_company_code"),
    )
    service, state = _build_service(commit_error=database_error)

    with pytest.raises(ConflictError, match="Sale code already exists"):
        await service.create_sale(COMPANY_ID, _sale_payload())

    assert state.rollback_count == 1
    assert state.stock == 10.0
