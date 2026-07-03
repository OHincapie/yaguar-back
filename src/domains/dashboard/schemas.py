from pydantic import BaseModel


class KpiPanel(BaseModel):
    sales_today: float
    sales_week: float
    sales_month: float
    receivables: float
    payables: float
    critical_stock_count: int
    avg_margin_pct: float
