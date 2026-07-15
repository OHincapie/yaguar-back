from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.accounts.repository import AccountsRepository
from src.domains.customers.models import Customer
from src.domains.dashboard.schemas import CashflowMonth, DashboardCharts, KpiPanel, OutflowSegment, TopProduct
from src.domains.expenses.repository import ExpenseAccountRepository
from src.domains.inventory.models import InventoryLevel
from src.domains.ledger.models import LedgerEntry, LedgerType
from src.domains.products.models import Product
from src.domains.purchases.models import Purchase, PurchaseStatus
from src.domains.sales.models import Sale, SaleAbono, SaleLine, SaleStatus
from src.domains.suppliers.models import Supplier
from src.shared.database import get_session
from src.shared.margin import MarginBasis, margin_pct, normalize_basis
from src.shared.middleware.auth import CurrentUser

MONTH_LABELS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")

# Not module-gated on purpose: this is read-only (a single GET /kpis) and it
# aggregates across every other domain (sales, products, customers,
# inventory) — there's nothing meaningful left to restrict once every
# domain's own reads are open to any authenticated company member. The
# "dashboard" module key still exists in the frontend's module picker purely
# as a nav-visibility toggle (Sidebar/AppShell), not a backend permission.
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/kpis", response_model=KpiPanel)
async def get_kpis(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    company_id = current_user.company_id
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)

    async def sum_sales(from_dt: datetime) -> float:
        result = await session.exec(  # type: ignore
            select(func.coalesce(func.sum(Sale.total), 0)).where(
                Sale.company_id == company_id,
                Sale.date >= from_dt,
                Sale.status != SaleStatus.CANCELADO,
            )
        )
        return float(result.one())

    sales_today = await sum_sales(today_start)
    sales_week = await sum_sales(week_start)
    sales_month = await sum_sales(month_start)

    receivables_result = await session.exec(  # type: ignore
        select(func.coalesce(func.sum(Customer.saldo), 0)).where(Customer.company_id == company_id)
    )
    receivables = float(receivables_result.one())

    # Past-due portion of the receivables: open credit sales whose due_date
    # already passed, minus whatever was already paid down (abonos). Same
    # read-time computation the cartera view uses — nothing persists
    # "vencido".
    abonos_subq = (
        select(func.coalesce(func.sum(SaleAbono.amount), 0.0)).where(SaleAbono.sale_id == Sale.id).scalar_subquery()
    )
    overdue_result = await session.exec(  # type: ignore
        select(func.coalesce(func.sum(Sale.total - abonos_subq), 0)).where(
            Sale.company_id == company_id,
            Sale.status.in_([SaleStatus.PENDIENTE, SaleStatus.VENCIDO]),
            Sale.due_date.is_not(None),
            Sale.due_date < now,
        )
    )
    receivables_overdue = round(float(overdue_result.one()), 2)

    payables_result = await session.exec(  # type: ignore
        select(func.coalesce(func.sum(Supplier.saldo), 0)).where(Supplier.company_id == company_id)
    )
    payables = float(payables_result.one())

    # Committed spend: purchase orders that will cost money but haven't
    # been received (or cancelled) yet. Purchases have no payment tracking,
    # so this is the honest "por pagar"-adjacent number the dashboard can
    # actually stand behind — Supplier.saldo above is dormant seed data.
    open_po_result = await session.exec(  # type: ignore
        select(func.coalesce(func.sum(Purchase.total), 0)).where(
            Purchase.company_id == company_id,
            Purchase.status.in_([PurchaseStatus.BORRADOR, PurchaseStatus.EN_CAMINO, PurchaseStatus.ADUANA]),
        )
    )
    open_purchases_total = round(float(open_po_result.one()), 2)

    # Margins follow the company's configured basis (price vs cost) so the
    # dashboard matches Inventario and Kuri.
    company = await AccountsRepository(session).get_company(company_id)
    basis = normalize_basis(company.margin_basis if company else None)

    # Realized margin over the last 30 days of actual sale lines — what was
    # really earned, unlike avg_margin_pct below which is a catalog-wide
    # average whether products sell or not. Numerator is gross profit; the
    # denominator is revenue (price basis) or cost (cost basis).
    margin_result = (
        await session.exec(  # type: ignore
            select(
                func.coalesce(func.sum((SaleLine.unit_price - SaleLine.unit_cost) * SaleLine.qty), 0.0),
                func.coalesce(func.sum(SaleLine.unit_price * SaleLine.qty), 0.0),
                func.coalesce(func.sum(SaleLine.unit_cost * SaleLine.qty), 0.0),
            )
            .join(Sale, Sale.id == SaleLine.sale_id)  # type: ignore
            .where(
                Sale.company_id == company_id,
                Sale.status != SaleStatus.CANCELADO,
                Sale.date >= now - timedelta(days=30),
            )
        )
    ).one()
    profit_30d = float(margin_result[0])
    denom_30d = float(margin_result[2]) if basis == MarginBasis.COST else float(margin_result[1])
    margin_30d_pct = round(profit_30d / denom_30d * 100, 1) if denom_30d > 0 else None

    critical_result = await session.exec(  # type: ignore
        select(func.count()).where(
            InventoryLevel.company_id == company_id,
            InventoryLevel.stock_qty <= InventoryLevel.min_stock,
        )
    )
    critical_stock_count = int(critical_result.one())

    products_result = await session.exec(select(Product).where(Product.company_id == company_id))  # type: ignore
    products = products_result.all()
    denom_ok = (lambda p: p.cost > 0) if basis == MarginBasis.COST else (lambda p: p.price > 0)
    margins = [margin_pct(p.price, p.cost, basis) for p in products if denom_ok(p)]
    avg_margin = sum(margins) / len(margins) if margins else 0.0

    return KpiPanel(
        sales_today=sales_today,
        sales_week=sales_week,
        sales_month=sales_month,
        receivables=receivables,
        receivables_overdue=receivables_overdue,
        payables=payables,
        open_purchases_total=open_purchases_total,
        critical_stock_count=critical_stock_count,
        avg_margin_pct=round(avg_margin, 1),
        margin_30d_pct=margin_30d_pct,
        margin_basis=basis.value,
    )


@router.get("/charts", response_model=DashboardCharts)
async def get_charts(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    company_id = current_user.company_id
    now = datetime.now(timezone.utc)

    # --- Cashflow: real monthly in/out from the ledger, last 6 months
    # (current month included). One row per (month, type); zero-filled
    # buckets assembled in Python so a month with no movement still shows
    # up on the axis. Walk back month by month — a fixed day stride (e.g.
    # 31*5 days) overshoots and drops the current month off the window.
    first_bucket = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for _ in range(5):
        first_bucket = (first_bucket - timedelta(days=1)).replace(day=1)
    month_col = func.date_trunc("month", LedgerEntry.date)
    rows = (
        await session.exec(  # type: ignore
            select(
                month_col,
                LedgerEntry.type,
                func.coalesce(func.sum(LedgerEntry.credit), 0.0),
                func.coalesce(func.sum(LedgerEntry.debit), 0.0),
            )
            .where(LedgerEntry.company_id == company_id, LedgerEntry.date >= first_bucket)
            .group_by(month_col, LedgerEntry.type)
        )
    ).all()

    by_month: dict[str, dict[str, float]] = {}
    for month_dt, entry_type, credit_sum, debit_sum in rows:
        key = month_dt.strftime("%Y-%m")
        bucket = by_month.setdefault(key, {"in": 0.0, "out": 0.0})
        # IN entries carry their amount in `credit`, OUT entries in `debit`
        # (how SaleService/PurchaseService write them).
        if entry_type == LedgerType.IN:
            bucket["in"] += float(credit_sum)
        else:
            bucket["out"] += float(debit_sum)

    # Outflow breakdown per month: group OUT debit by expense account (each
    # with its own color) and lump account-less OUT entries (purchases) into
    # "Compras". Feeds the stacked egresos bars.
    breakdown_rows = (
        await session.exec(  # type: ignore
            select(
                month_col,
                LedgerEntry.account_id,
                func.coalesce(func.sum(LedgerEntry.debit), 0.0),
            )
            .where(
                LedgerEntry.company_id == company_id,
                LedgerEntry.date >= first_bucket,
                LedgerEntry.type == LedgerType.OUT,
            )
            .group_by(month_col, LedgerEntry.account_id)
        )
    ).all()
    accounts_by_id = {a.id: a for a in await ExpenseAccountRepository(session).get_all(company_id)}
    COMPRAS_COLOR = "#64748B"  # slate — the non-account (purchases) segment
    # {month_key: {segment_label: {"amount": x, "color": y}}}
    seg_by_month: dict[str, dict[str, dict]] = {}
    for month_dt, account_id, debit_sum in breakdown_rows:
        amount = float(debit_sum)
        if amount <= 0:
            continue
        account = accounts_by_id.get(account_id) if account_id else None
        label = account.name if account else "Compras"
        color = account.color if account else COMPRAS_COLOR
        seg = seg_by_month.setdefault(month_dt.strftime("%Y-%m"), {})
        entry = seg.setdefault(label, {"amount": 0.0, "color": color})
        entry["amount"] += amount

    cashflow: list[CashflowMonth] = []
    cursor = first_bucket
    for _ in range(6):
        key = cursor.strftime("%Y-%m")
        bucket = by_month.get(key, {"in": 0.0, "out": 0.0})
        segments = [
            OutflowSegment(label=lbl, color=v["color"], amount=round(v["amount"], 2))
            for lbl, v in sorted(seg_by_month.get(key, {}).items(), key=lambda kv: kv[1]["amount"], reverse=True)
        ]
        cashflow.append(
            CashflowMonth(
                month=key,
                label=MONTH_LABELS[cursor.month - 1],
                inflow=round(bucket["in"], 2),
                outflow=round(bucket["out"], 2),
                outflow_breakdown=segments,
            )
        )
        cursor = (cursor + timedelta(days=32)).replace(day=1)

    # --- Top products by revenue actually sold in the last 30 days. ---
    top_rows = (
        await session.exec(  # type: ignore
            select(
                SaleLine.product_id,
                func.sum(SaleLine.qty),
                func.sum(SaleLine.qty * SaleLine.unit_price),
            )
            .join(Sale, Sale.id == SaleLine.sale_id)  # type: ignore
            .where(
                Sale.company_id == company_id,
                Sale.status != SaleStatus.CANCELADO,
                Sale.date >= now - timedelta(days=30),
            )
            .group_by(SaleLine.product_id)
            .order_by(func.sum(SaleLine.qty * SaleLine.unit_price).desc())
            .limit(5)
        )
    ).all()

    products_by_id: dict[str, Product] = {}
    if top_rows:
        product_rows = await session.exec(  # type: ignore
            select(Product).where(Product.company_id == company_id, Product.id.in_([r[0] for r in top_rows]))
        )
        products_by_id = {p.id: p for p in product_rows.all()}

    top_products = [
        TopProduct(
            product_id=product_id,
            sku=products_by_id[product_id].sku if product_id in products_by_id else "—",
            name=products_by_id[product_id].name if product_id in products_by_id else "Producto eliminado",
            qty_sold=float(qty),
            revenue=round(float(revenue), 2),
        )
        for product_id, qty, revenue in top_rows
    ]

    return DashboardCharts(cashflow=cashflow, top_products=top_products)
