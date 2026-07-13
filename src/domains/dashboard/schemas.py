from pydantic import BaseModel


class KpiPanel(BaseModel):
    sales_today: float
    sales_week: float
    sales_month: float
    receivables: float
    # Portion of receivables past due (open credit sales with
    # due_date < now, abonos already subtracted).
    receivables_overdue: float
    # Kept for back-compat (sum of Supplier.saldo — dormant seed data);
    # the dashboard shows open_purchases_total instead.
    payables: float
    # Committed spend: purchase orders not yet received/cancelled.
    open_purchases_total: float
    critical_stock_count: int
    # Catalog-wide average margin (price vs cost of every product).
    avg_margin_pct: float
    # Realized margin over the last 30 days of actual sale lines —
    # None when there were no sales in the window (the UI falls back
    # to the catalog average).
    margin_30d_pct: float | None


class CashflowMonth(BaseModel):
    month: str  # "2026-02", for keys/sorting
    label: str  # "feb", for the axis
    inflow: float
    outflow: float


class TopProduct(BaseModel):
    product_id: str
    sku: str
    name: str
    qty_sold: float
    revenue: float


class DashboardCharts(BaseModel):
    """Everything the dashboard renders that isn't a single number:
    real monthly cashflow from the ledger (replaces the illustrative
    flowMonths mock the frontend shipped with) and the actually-sold
    top products (the old list was just the 5 most expensive ones)."""

    cashflow: list[CashflowMonth]  # 6 buckets, oldest first, zero-filled
    top_products: list[TopProduct]  # by revenue, last 30 days, max 5
