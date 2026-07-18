from datetime import datetime, timedelta, timezone

from src.domains.accounts.repository import AccountsRepository
from src.domains.agents.models import PendingAgentTrigger
from src.domains.agents.repository import AgentRepository
from src.domains.customers.repository import CustomerRepository
from src.domains.inventory.service import InventoryService
from src.domains.ledger.models import LedgerCategory, LedgerEntry, LedgerType
from src.domains.ledger.repository import LedgerRepository
from src.domains.sales.models import PaymentMethodConfig, Sale, SaleAbono, SaleLine, SalePayment, SaleStatus
from src.domains.sales.repository import PaymentMethodRepository, SaleRepository
from src.domains.sales.schemas import (
    AbonoCreate,
    AbonoRead,
    AbonoResult,
    CarteraItemRead,
    PaymentLine,
    PaymentMethodCreate,
    PaymentMethodUpdate,
    SaleCreate,
    SaleLineCreate,
    SaleStatusUpdate,
    SaleUpdate,
)
from src.shared.middleware.errors import BusinessError, ConflictError, NotFoundError

# Statuses that mean "this credit sale is still waiting to be collected".
# VENCIDO is never set automatically (overdue is computed at read time from
# due_date) but the manual status endpoint can set it, so treat it as open.
OPEN_STATUSES = (SaleStatus.PENDIENTE, SaleStatus.VENCIDO)


class SaleService:
    def __init__(
        self,
        repo: SaleRepository,
        inventory_service: InventoryService,
        ledger_repo: LedgerRepository,
        accounts_repo: AccountsRepository,
        payment_method_repo: PaymentMethodRepository,
        customer_repo: CustomerRepository,
        agent_repo: AgentRepository,
    ):
        self.repo = repo
        self.inventory_service = inventory_service
        self.ledger_repo = ledger_repo
        self.accounts_repo = accounts_repo
        self.payment_method_repo = payment_method_repo
        self.customer_repo = customer_repo
        self.agent_repo = agent_repo

    async def _adjust_saldo(self, company_id: str, customer_id: str | None, delta: float) -> None:
        """Keeps Customer.saldo (outstanding receivable) in sync. No-op for
        walk-in sales and near-zero deltas. Clamps at 0 from below so a
        legacy/seeded saldo that never matched real sales can't go negative."""
        if customer_id is None or abs(delta) < 0.005:
            return
        customer = await self.customer_repo.get_by_id(company_id, customer_id)
        if customer is None:
            return
        customer.saldo = round(max(0.0, customer.saldo + delta), 2)
        await self.customer_repo.update(customer)

    async def _abonado(self, sale_id: str) -> float:
        return round(sum(a.amount for a in await self.repo.get_abonos(sale_id)), 2)

    async def list_sales(self, company_id: str, status, customer_id: str | None, from_date, to_date, page: int, page_size: int):
        offset = (page - 1) * page_size
        return await self.repo.get_all(
            company_id, status=status, customer_id=customer_id, from_date=from_date, to_date=to_date,
            offset=offset, limit=page_size,
        )

    async def get_sale(self, company_id: str, code: str) -> Sale:
        sale = await self.repo.get_by_code(company_id, code)
        if not sale:
            raise NotFoundError("Sale", code)
        return sale

    async def get_lines(self, company_id: str, code: str) -> list[SaleLine]:
        sale = await self.get_sale(company_id, code)
        return await self.repo.get_lines(sale.id)

    async def get_payments(self, company_id: str, code: str) -> list[SalePayment]:
        sale = await self.get_sale(company_id, code)
        return await self.repo.get_payments(sale.id)

    async def _compute_amounts(self, company_id: str, lines: list[SaleLineCreate]) -> tuple[float, float, float, float]:
        """Returns (subtotal, discount_amount, tax_amount, total) using the
        company's current discount_pct/tax_pct — same rule for create and edit,
        so a sale never silently drifts from what checkout would compute today."""
        company = await self.accounts_repo.get_company(company_id)
        assert company is not None
        subtotal = sum(line.qty * line.unit_price for line in lines)
        discount_amount = subtotal * (company.discount_pct / 100) if company.discount_enabled else 0.0
        tax_amount = (subtotal - discount_amount) * (company.tax_pct / 100) if company.tax_enabled else 0.0
        total = subtotal - discount_amount + tax_amount
        return subtotal, discount_amount, tax_amount, total

    async def _resolve_payments(
        self, company_id: str, payments: list[PaymentLine], total: float, customer_id: str | None
    ) -> tuple[list[PaymentMethodConfig], str, SaleStatus]:
        """Validates a proposed set of payment lines against the sale total
        and the company's payment-method rules. Returns the resolved
        PaymentMethodConfig rows (same order as `payments`), a display
        summary string (e.g. "Efectivo + Transferencia"), and the resulting
        SaleStatus. Doesn't create SalePayment rows — the caller does that
        once it has a Sale.id (mirrors how SaleLine is built)."""
        methods_by_id = {m.id: m for m in await self.payment_method_repo.get_by_ids(company_id, [p.payment_method_id for p in payments])}

        # A fully-free sale (every line given away / priced at 0) has a total
        # of 0 — no money changes hands, so it's paid on the spot and the
        # per-line "amount must be positive" rule below is relaxed to allow
        # the single 0 amount. Stock is still deducted normally; this is just
        # the payment side. Anything above ~a cent is a normal sale.
        is_free = abs(total) < 0.01

        # A single payment with no amount means "the whole total". Filled in
        # by mutating the PaymentLine (not a local copy) on purpose: the
        # callers build SalePayment rows from these same objects afterward,
        # so the resolved amount has to land on them.
        if len(payments) == 1 and payments[0].amount is None:
            payments[0].amount = total

        resolved: list[PaymentMethodConfig] = []
        paid_sum = 0.0
        for p in payments:
            method = methods_by_id.get(p.payment_method_id)
            if not method or not method.is_active:
                raise BusinessError(f"Unknown or inactive payment method: '{p.payment_method_id}'")
            if p.amount is None:
                raise BusinessError("Each payment line needs an explicit amount when the payment is split")
            if p.amount < 0 or (p.amount == 0 and not is_free):
                raise BusinessError("Each payment line needs a positive amount")
            resolved.append(method)
            paid_sum += p.amount

        # Floating point tolerance, not an exact-cents requirement.
        if abs(paid_sum - total) > 0.01:
            raise BusinessError(f"Payments must add up to the total ({total:.2f}), got {paid_sum:.2f}")

        # A free sale is always settled — nothing to owe, so credit rules
        # don't apply (a "free credit" line would create a bogus receivable).
        credit_methods = [m for m in resolved if m.is_credit]
        if credit_methods and not is_free:
            # Deliberately all-or-nothing — not a partial-payment/accounts
            # receivable feature. Splitting real money across several
            # methods is fine; mixing real money with "owed" isn't
            # supported (Customer.saldo isn't wired to anything yet, so
            # there's nowhere for a partial credit balance to live).
            if len(payments) > 1:
                raise BusinessError("A credit payment can't be combined with other payment methods")
            if customer_id is None:
                raise BusinessError("A walk-in sale (no customer) can't be paid on credit")

        status = SaleStatus.PAGADO if is_free else (SaleStatus.PENDIENTE if credit_methods else SaleStatus.PAGADO)
        # dict.fromkeys instead of set(): de-dupes repeated methods while
        # keeping the order the user entered them in.
        display = " + ".join(dict.fromkeys(m.name for m in resolved))
        return resolved, display, status

    async def create_sale(self, company_id: str, data: SaleCreate) -> Sale:
        count = await self.repo.count_for_company(company_id)
        code = f"V-{count + 1:05d}"

        subtotal, discount_amount, tax_amount, total = await self._compute_amounts(company_id, data.lines)
        _methods, payment_display, status = await self._resolve_payments(company_id, data.payments, total, data.customer_id)

        # A credit sale gets a collection deadline: explicit from the caller,
        # or the company's default term. Cash/card/transfer sales carry none.
        due_date = None
        if status == SaleStatus.PENDIENTE:
            if data.due_date is not None:
                due_date = data.due_date
            else:
                company = await self.accounts_repo.get_company(company_id)
                assert company is not None
                due_date = datetime.now(timezone.utc) + timedelta(days=company.credit_days)

        sale = Sale(
            company_id=company_id,
            code=code,
            customer_id=data.customer_id,
            subtotal=subtotal,
            discount_amount=discount_amount,
            tax_amount=tax_amount,
            total=total,
            payment_method=payment_display,
            status=status,
            notes=data.notes,
            due_date=due_date,
        )

        # Products this sale pushed to/below their minimum — leave a
        # breadcrumb so Inti reacts on the next Agentes page load instead of
        # waiting for the daily sweep. The LLM work happens later, off the
        # checkout path (see PendingAgentTrigger).
        for line_data in data.lines:
            level = await self.inventory_service.apply_sale(
                company_id=company_id,
                product_id=line_data.product_id,
                qty=line_data.qty,
                sale_id=sale.id,
            )
            if level is not None and level.min_stock and level.stock_qty <= level.min_stock:
                # level.product_id is the level that actually dropped — for a
                # kit that's the depleted component, not the kit itself.
                await self.agent_repo.create_trigger(
                    PendingAgentTrigger(
                        company_id=company_id,
                        agent_key="stock",
                        context={"product_id": level.product_id, "reason": "sale_below_min", "sale_code": code},
                    )
                )

        lines = [SaleLine(sale_id=sale.id, **line.model_dump()) for line in data.lines]
        payments = [SalePayment(sale_id=sale.id, payment_method_id=p.payment_method_id, amount=p.amount) for p in data.payments]
        sale = await self.repo.create(sale, lines, payments)

        await self.ledger_repo.create(
            LedgerEntry(
                company_id=company_id,
                concept=f"Venta {sale.code}",
                category=LedgerCategory.VENTAS,
                credit=total,
                type=LedgerType.IN,
                reference_id=sale.id,
                reference_type="sale",
            )
        )

        # Income is recognized in the ledger at creation regardless of
        # credit (flat-book behavior, unchanged); the receivable side lives
        # on Customer.saldo until abonos cover it.
        if sale.status == SaleStatus.PENDIENTE:
            await self._adjust_saldo(company_id, sale.customer_id, +total)
        return sale

    async def register_abono(self, company_id: str, code: str, data: AbonoCreate) -> AbonoResult:
        sale = await self.get_sale(company_id, code)
        if sale.status not in OPEN_STATUSES:
            raise BusinessError(f"Sale {code} isn't pending collection (status: {sale.status})")

        method = await self.payment_method_repo.get_by_id(company_id, data.payment_method_id)
        if not method or not method.is_active:
            raise BusinessError(f"Unknown or inactive payment method: '{data.payment_method_id}'")
        if method.is_credit:
            raise BusinessError("An abono needs a real payment method — credit can't pay off credit")
        if data.amount <= 0:
            raise BusinessError("An abono needs a positive amount")

        abonado = await self._abonado(sale.id)
        saldo = round(sale.total - abonado, 2)
        if data.amount > saldo + 0.01:
            raise BusinessError(f"Abono ({data.amount:.2f}) exceeds the outstanding balance ({saldo:.2f})")

        abono = await self.repo.add_abono(
            SaleAbono(sale_id=sale.id, payment_method_id=method.id, amount=data.amount, notes=data.notes)
        )
        await self._adjust_saldo(company_id, sale.customer_id, -data.amount)

        abonado = round(abonado + data.amount, 2)
        saldo = round(sale.total - abonado, 2)
        if saldo <= 0.01:
            sale.status = SaleStatus.PAGADO
            saldo = 0.0
            sale = await self.repo.update(sale)

        return AbonoResult(
            abono=AbonoRead(
                id=abono.id,
                sale_id=abono.sale_id,
                payment_method_id=method.id,
                payment_method_name=method.name,
                amount=abono.amount,
                date=abono.date,
                notes=abono.notes,
            ),
            sale_status=sale.status,
            total=sale.total,
            abonado=abonado,
            saldo=saldo,
        )

    async def list_abonos(self, company_id: str, code: str) -> list[AbonoRead]:
        sale = await self.get_sale(company_id, code)
        abonos = await self.repo.get_abonos(sale.id)
        methods = {m.id: m for m in await self.payment_method_repo.get_all(company_id)}
        return [
            AbonoRead(
                id=a.id,
                sale_id=a.sale_id,
                payment_method_id=a.payment_method_id,
                payment_method_name=methods[a.payment_method_id].name if a.payment_method_id in methods else "—",
                amount=a.amount,
                date=a.date,
                notes=a.notes,
            )
            for a in abonos
        ]

    async def get_cartera(self, company_id: str) -> list[CarteraItemRead]:
        sales = await self.repo.get_open_credit_sales(company_id)
        abonos_by_sale = await self.repo.get_abonos_sum_by_sale([s.id for s in sales])
        # limit high enough to cover every customer — the repo's default 50
        # would silently drop names on bigger companies.
        customers = {c.id: c for c in (await self.customer_repo.get_all(company_id, limit=100_000))[0]} if sales else {}
        now = datetime.now(timezone.utc)

        items: list[CarteraItemRead] = []
        for s in sales:
            abonado = round(abonos_by_sale.get(s.id, 0.0), 2)
            overdue = s.due_date is not None and s.due_date < now
            customer = customers.get(s.customer_id) if s.customer_id else None
            items.append(
                CarteraItemRead(
                    sale_id=s.id,
                    code=s.code,
                    customer_id=s.customer_id,
                    customer_name=customer.name if customer else "Cliente ocasional",
                    date=s.date,
                    due_date=s.due_date,
                    total=s.total,
                    abonado=abonado,
                    saldo=round(s.total - abonado, 2),
                    overdue=overdue,
                    days_overdue=max(0, (now - s.due_date).days) if overdue else 0,
                )
            )
        return items

    async def update_status(self, company_id: str, code: str, data: SaleStatusUpdate) -> Sale:
        sale = await self.get_sale(company_id, code)
        # Manual status flips must keep the customer's receivable in sync —
        # marking an open credit sale "pagado" by hand settles its remaining
        # balance, reopening a paid one puts the uncovered part back.
        was_open, now_open = sale.status in OPEN_STATUSES, data.status in OPEN_STATUSES
        if was_open != now_open:
            remaining = round(sale.total - await self._abonado(sale.id), 2)
            await self._adjust_saldo(company_id, sale.customer_id, -remaining if was_open else +remaining)
        sale.status = data.status
        return await self.repo.update(sale)

    async def update_sale(self, company_id: str, code: str, data: SaleUpdate) -> Sale:
        sale = await self.get_sale(company_id, code)
        old_total, old_status = sale.total, sale.status

        if data.notes is not None:
            sale.notes = data.notes

        if data.lines is not None:
            old_lines = await self.repo.get_lines(sale.id)
            for old_line in old_lines:
                await self.inventory_service.reverse_sale(
                    company_id=company_id, product_id=old_line.product_id, qty=old_line.qty, sale_id=sale.id
                )

            for line_data in data.lines:
                await self.inventory_service.apply_sale(
                    company_id=company_id, product_id=line_data.product_id, qty=line_data.qty, sale_id=sale.id
                )

            subtotal, discount_amount, tax_amount, total = await self._compute_amounts(company_id, data.lines)
            sale.subtotal = subtotal
            sale.discount_amount = discount_amount
            sale.tax_amount = tax_amount
            sale.total = total

            await self.repo.replace_lines(sale.id, [SaleLine(sale_id=sale.id, **line.model_dump()) for line in data.lines])

            ledger_entry = await self.ledger_repo.get_by_reference(company_id, sale.id, "sale")
            if ledger_entry:
                ledger_entry.credit = sale.total
                await self.ledger_repo.update(ledger_entry)

        if data.payments is not None:
            # Re-arranging how a sale was paid after abonos were registered
            # against it would leave saldo/abonado in a state nobody can
            # reason about — settle or delete the abonos story first.
            if await self.repo.get_abonos(sale.id):
                raise BusinessError("This sale already has abonos registered — its payment lines can't be replaced")
            _methods, payment_display, status = await self._resolve_payments(
                company_id, data.payments, sale.total, sale.customer_id
            )
            payments = [
                SalePayment(sale_id=sale.id, payment_method_id=p.payment_method_id, amount=p.amount)
                for p in data.payments
            ]
            await self.repo.replace_payments(sale.id, payments)
            sale.payment_method = payment_display
            # A credit sale that just became one needs a deadline; one that
            # stopped being credit sheds it.
            if status == SaleStatus.PENDIENTE and old_status not in OPEN_STATUSES:
                company = await self.accounts_repo.get_company(company_id)
                assert company is not None
                sale.due_date = datetime.now(timezone.utc) + timedelta(days=company.credit_days)
            elif status == SaleStatus.PAGADO:
                sale.due_date = None
            sale.status = status

        # One receivable adjustment covering both edits: the delta between
        # what this sale contributed to Customer.saldo before (old open →
        # old total minus abonos, else 0) and after. Line edits on an open
        # sale move saldo by the total change; credit→paid removes it; paid
        # →credit adds it.
        abonado = await self._abonado(sale.id)
        before = round(old_total - abonado, 2) if old_status in OPEN_STATUSES else 0.0
        after = round(sale.total - abonado, 2) if sale.status in OPEN_STATUSES else 0.0
        await self._adjust_saldo(company_id, sale.customer_id, after - before)

        return await self.repo.update(sale)

    async def delete_sale(self, company_id: str, code: str) -> None:
        sale = await self.get_sale(company_id, code)

        lines = await self.repo.get_lines(sale.id)
        for line in lines:
            await self.inventory_service.reverse_sale(
                company_id=company_id, product_id=line.product_id, qty=line.qty, sale_id=sale.id
            )

        ledger_entry = await self.ledger_repo.get_by_reference(company_id, sale.id, "sale")
        if ledger_entry:
            await self.ledger_repo.delete(ledger_entry)

        # An open credit sale stops being owed when it stops existing.
        if sale.status in OPEN_STATUSES:
            remaining = round(sale.total - await self._abonado(sale.id), 2)
            await self._adjust_saldo(company_id, sale.customer_id, -remaining)

        await self.repo.delete_abonos(sale.id)
        await self.repo.replace_lines(sale.id, [])
        await self.repo.replace_payments(sale.id, [])
        await self.repo.delete(sale)


class PaymentMethodService:
    def __init__(self, repo: PaymentMethodRepository):
        self.repo = repo

    async def list_methods(self, company_id: str, active_only: bool = False) -> list[PaymentMethodConfig]:
        return await self.repo.get_all(company_id, active_only=active_only)

    async def create_method(self, company_id: str, data: PaymentMethodCreate) -> PaymentMethodConfig:
        existing = await self.repo.get_all(company_id)
        if any(m.name.lower() == data.name.lower() for m in existing):
            raise ConflictError(f"Payment method '{data.name}' already exists")
        return await self.repo.create(PaymentMethodConfig(company_id=company_id, name=data.name, is_credit=data.is_credit))

    async def update_method(self, company_id: str, id: str, data: PaymentMethodUpdate) -> PaymentMethodConfig:
        method = await self.repo.get_by_id(company_id, id)
        if not method:
            raise NotFoundError("PaymentMethod", id)
        if data.name is not None:
            method.name = data.name
        if data.is_active is not None:
            method.is_active = data.is_active
        return await self.repo.update(method)
