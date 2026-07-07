from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.customers.models import Customer
from src.domains.dashboard.schemas import KpiPanel
from src.domains.inventory.models import InventoryLevel
from src.domains.products.models import Product
from src.domains.sales.models import Sale, SaleStatus
from src.domains.suppliers.models import Supplier
from src.shared.database import get_session
from src.shared.middleware.auth import CurrentUser, require_module

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_module("dashboard"))])


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

    payables_result = await session.exec(  # type: ignore
        select(func.coalesce(func.sum(Supplier.saldo), 0)).where(Supplier.company_id == company_id)
    )
    payables = float(payables_result.one())

    critical_result = await session.exec(  # type: ignore
        select(func.count()).where(
            InventoryLevel.company_id == company_id,
            InventoryLevel.stock_qty <= InventoryLevel.min_stock,
        )
    )
    critical_stock_count = int(critical_result.one())

    products_result = await session.exec(select(Product).where(Product.company_id == company_id))  # type: ignore
    products = products_result.all()
    if products:
        margins = [(p.price - p.cost) / p.price * 100 for p in products if p.price > 0]
        avg_margin = sum(margins) / len(margins) if margins else 0.0
    else:
        avg_margin = 0.0

    return KpiPanel(
        sales_today=sales_today,
        sales_week=sales_week,
        sales_month=sales_month,
        receivables=receivables,
        payables=payables,
        critical_stock_count=critical_stock_count,
        avg_margin_pct=round(avg_margin, 1),
    )
