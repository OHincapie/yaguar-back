"""Deterministic business-rule detection — no LLM involved here.

Deciding *whether* something is wrong (stock below minimum, no sales in
30 days) and *what* the concrete fix looks like (reorder qty, new price)
is arithmetic we already trust our own database for. The LLM's job,
downstream in graph.py, is only to turn these facts into a clear message
for the user — never to invent the numbers itself.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.inventory.models import MovementType
from src.domains.inventory.repository import InventoryRepository
from src.domains.inventory.service import InventoryService
from src.domains.products.repository import ProductRepository
from src.domains.suppliers.repository import SupplierRepository

STOCKOUT_LOOKBACK_DAYS = 14
SLOW_MOVING_DAYS = 30
REORDER_TARGET_MULTIPLE = 2.5  # reorder up to 2.5x the minimum
SLOW_MOVING_DISCOUNT = 0.15  # suggest a 15% price cut


async def detect_stock_issues(company_id: str, session: AsyncSession) -> list[dict[str, Any]]:
    product_repo = ProductRepository(session)
    supplier_repo = SupplierRepository(session)
    inventory_repo = InventoryRepository(session)
    inventory_service = InventoryService(inventory_repo, product_repo)

    candidates: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    # --- 1. Stock at or below the minimum: propose a reorder -----------
    low_levels, _ = await inventory_service.list_levels(company_id, below_min=True, page=1, page_size=200)
    for level in low_levels:
        product = await product_repo.get_by_id(company_id, level.product_id)
        if not product or product.is_bundle or not product.supplier_id:
            continue  # a kit has no purchasable stock; no supplier means nobody to order from

        movements, _ = await inventory_repo.get_movements(
            company_id,
            product_id=product.id,
            type=MovementType.SALIDA,
            from_date=now - timedelta(days=STOCKOUT_LOOKBACK_DAYS),
            limit=500,
        )
        outflow = sum(-m.qty for m in movements)  # SALIDA is stored negative
        daily_rate = outflow / STOCKOUT_LOOKBACK_DAYS
        days_to_stockout = round(level.stock_qty / daily_rate, 1) if daily_rate > 0 else None

        target = product.cost  # unit cost for the reorder estimate
        suggested_qty = max(round(level.min_stock * REORDER_TARGET_MULTIPLE - level.stock_qty), level.min_stock or 1)

        supplier = await supplier_repo.get_by_id(company_id, product.supplier_id)

        candidates.append(
            {
                "type": "quiebre",
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "stock_qty": level.stock_qty,
                "min_stock": level.min_stock,
                "days_to_stockout": days_to_stockout,
                "supplier_id": product.supplier_id,
                "supplier_name": supplier.name if supplier else "proveedor desconocido",
                "unit_cost": target,
                "suggested_qty": suggested_qty,
                "total_cost": round(suggested_qty * target, 2),
            }
        )

    # --- 2. No sales in a month: propose a price cut to free up capital --
    all_products, _ = await product_repo.get_all(company_id, category_id=None, search=None, offset=0, limit=500)
    for product in all_products:
        if product.is_bundle:
            continue
        level = await inventory_repo.get_level(company_id, product.id)
        if not level or level.stock_qty <= 0:
            continue

        last_sale, _ = await inventory_repo.get_movements(
            company_id, product_id=product.id, type=MovementType.SALIDA, limit=1
        )
        if last_sale and last_sale[0].date >= now - timedelta(days=SLOW_MOVING_DAYS):
            continue  # sold recently, not slow-moving

        days_since_last_sale = (now - last_sale[0].date).days if last_sale else None
        suggested_price = round(product.price * (1 - SLOW_MOVING_DISCOUNT), 2)
        candidates.append(
            {
                "type": "baja_rotacion",
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "stock_qty": level.stock_qty,
                "days_since_last_sale": days_since_last_sale,  # None means never sold
                "stock_value": round(level.stock_qty * product.cost, 2),
                "current_price": product.price,
                "suggested_price": suggested_price,
            }
        )

    return candidates
