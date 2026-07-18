"""Deterministic business-rule detection — no LLM involved, with ONE
deliberate exception: Khipu's catalog audit (detect_catalog_issues).

Deciding *whether* something is wrong (stock below minimum, no sales in
30 days) and *what* the concrete fix looks like (reorder qty, new price)
is arithmetic we already trust our own database for. The LLM's job,
downstream in graph.py, is only to turn these facts into a clear message
for the user — never to invent the numbers itself.

Khipu is different: "a cellphone filed under Audífonos" is a language
judgment, not arithmetic, so its detector asks an LLM to *suspect* — and
then validates every suspicion in plain Python (real SKU, suggested
category must exist verbatim in the company's real list, confidence
threshold) before it becomes a candidate. The LLM still never writes
anything and can never invent a category; a human approves every fix.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from langchain_core.callbacks import UsageMetadataCallbackHandler
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.accounts.repository import AccountsRepository
from src.domains.agents.llm import get_chat_model
from src.domains.agents.prompts import CATEGORY_AUDIT_SYSTEM_PROMPT, CategoryAuditResult
from src.domains.ai_usage.models import AiUsageEvent
from src.domains.ai_usage.repository import AiUsageRepository
from src.domains.customers.repository import CustomerRepository
from src.domains.inventory.models import MovementType
from src.domains.inventory.repository import InventoryRepository
from src.domains.inventory.service import InventoryService
from src.domains.products.repository import ProductRepository
from src.domains.purchases.repository import PurchaseRepository
from src.domains.sales.models import SaleStatus
from src.domains.sales.repository import SaleRepository
from src.domains.suppliers.repository import SupplierRepository
from src.shared.margin import LOW_MARGIN_THRESHOLD, TARGET_MARGIN, margin_pct, normalize_basis, price_for_target_margin

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


# --- Kuri (márgenes) ---------------------------------------------------


async def detect_margin_issues(company_id: str, session: AsyncSession) -> list[dict[str, Any]]:
    """Flag products whose margin is negative or below the low-margin
    threshold, and propose a price adjustment to restore a healthy margin.

    Margin is computed in the company's configured basis (price vs cost —
    see src/shared/margin.py) so the numbers in the alert match what the
    user sees in Inventario/Dashboard, and the threshold/target follow the
    same basis.

    Same shape as detect_stock_issues — pure arithmetic, no LLM. The
    graph's compose() node turns each candidate into a human-readable
    alert; the LLM never invents the numbers."""
    product_repo = ProductRepository(session)
    company = await AccountsRepository(session).get_company(company_id)
    basis = normalize_basis(company.margin_basis if company else None)
    low = LOW_MARGIN_THRESHOLD[basis]
    target = TARGET_MARGIN[basis]

    candidates: list[dict[str, Any]] = []
    all_products, _ = await product_repo.get_all(company_id, category_id=None, search=None, offset=0, limit=500)
    for product in all_products:
        if product.is_bundle:
            continue  # a kit's cost is derived from components, not stored

        margin = margin_pct(product.price, product.cost, basis) / 100  # fraction
        if margin >= low:
            continue  # healthy margin, nothing to flag

        suggested_price = price_for_target_margin(product.cost, target, basis) if product.cost > 0 else product.price
        candidate_type = "margen_negativo" if margin <= 0 else "margen_bajo"
        candidates.append(
            {
                "type": candidate_type,
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "cost": product.cost,
                "current_price": product.price,
                "margin_pct": round(margin * 100, 1),
                "suggested_price": suggested_price,
                "suggested_margin_pct": round(margin_pct(suggested_price, product.cost, basis), 1),
            }
        )

    return candidates


# --- Mara (cobranzas) --------------------------------------------------


async def detect_collections_issues(company_id: str, session: AsyncSession) -> list[dict[str, Any]]:
    """Flag overdue credit sales that still have an outstanding balance, so
    Mara can nudge the owner to collect.

    Only sales still in status PENDIENTE are proposed — approving a Mara
    alert flips the sale to VENCIDO (its executable action), after which it
    drops out of detection, so each overdue sale is escalated exactly once
    (no re-proposal loop). Prerequisite built with the cartera feature:
    due dates + abonos + real Customer.saldo.

    Pure arithmetic, no LLM — compose() turns each candidate into the
    human-readable reminder."""
    sale_repo = SaleRepository(session)
    customer_repo = CustomerRepository(session)
    now = datetime.now(timezone.utc)

    open_sales = await sale_repo.get_open_credit_sales(company_id)
    abonos_by_sale = await sale_repo.get_abonos_sum_by_sale([s.id for s in open_sales])
    customers = {c.id: c for c in (await customer_repo.get_all(company_id, limit=100_000))[0]} if open_sales else {}

    candidates: list[dict[str, Any]] = []
    for s in open_sales:
        if s.status != SaleStatus.PENDIENTE:
            continue  # already escalated to VENCIDO — don't re-flag
        if s.due_date is None or s.due_date >= now:
            continue  # not overdue yet
        abonado = round(abonos_by_sale.get(s.id, 0.0), 2)
        saldo = round(s.total - abonado, 2)
        if saldo <= 0.01:
            continue  # nothing left to collect
        customer = customers.get(s.customer_id) if s.customer_id else None
        candidates.append(
            {
                "type": "cobro_vencido",
                # Generic entity key for sweep de-dup (sales aren't products).
                "dedup_key": s.id,
                "sale_code": s.code,
                "customer_name": customer.name if customer else "Cliente ocasional",
                "total": s.total,
                "abonado": abonado,
                "saldo": saldo,
                "days_overdue": (now - s.due_date).days,
                "due_date": s.due_date.strftime("%Y-%m-%d"),
            }
        )

    return candidates


# --- Yaco (compras) ----------------------------------------------------

PURCHASE_LOOKBACK_DAYS = 30  # window used to measure sales velocity
LEAD_TIME_DAYS = 7  # reorder when stock won't cover at least this many days
REORDER_COVER_DAYS = 30  # order enough to cover ~1 month of sales


async def detect_reorder_needs(company_id: str, session: AsyncSession) -> list[dict[str, Any]]:
    """Anticipate stockouts *before* they happen and propose a purchase.

    This is Yaco's predictive complement to Inti's reactive quiebre: Inti
    fires once stock is already at/below the minimum; Yaco watches sales
    velocity and flags a product whose remaining stock won't last the
    supplier's lead time — while it's still *above* the minimum. Products
    already at/below minimum are skipped here on purpose (Inti owns those),
    so the same product never gets two competing reorder proposals.

    Pure arithmetic, no LLM — compose() writes the message from these facts."""
    product_repo = ProductRepository(session)
    supplier_repo = SupplierRepository(session)
    inventory_repo = InventoryRepository(session)
    purchase_repo = PurchaseRepository(session)
    now = datetime.now(timezone.utc)

    # Products already on an in-flight order — don't propose reordering
    # something that's on its way (avoids re-proposing every sweep while the
    # PO sits in borrador before being received).
    on_order = await purchase_repo.products_with_open_orders(company_id)

    candidates: list[dict[str, Any]] = []
    all_products, _ = await product_repo.get_all(company_id, category_id=None, search=None, offset=0, limit=500)
    for product in all_products:
        if product.is_bundle or not product.supplier_id:
            continue  # kits aren't purchasable; no supplier means nobody to order from
        if product.id in on_order:
            continue  # already ordered, waiting to land

        level = await inventory_repo.get_level(company_id, product.id)
        if not level or level.stock_qty <= 0:
            continue  # already out — that's Inti's quiebre, not anticipation
        if level.min_stock and level.stock_qty <= level.min_stock:
            continue  # at/below minimum → Inti's domain, don't double-propose

        movements, _ = await inventory_repo.get_movements(
            company_id,
            product_id=product.id,
            type=MovementType.SALIDA,
            from_date=now - timedelta(days=PURCHASE_LOOKBACK_DAYS),
            limit=1000,
        )
        outflow = sum(-m.qty for m in movements)  # SALIDA stored negative
        daily_rate = outflow / PURCHASE_LOOKBACK_DAYS
        if daily_rate <= 0:
            continue  # no recent sales velocity — nothing to anticipate

        days_of_cover = level.stock_qty / daily_rate
        if days_of_cover > LEAD_TIME_DAYS:
            continue  # still plenty of runway

        # Order enough to cover ~a month of sales, netting out what's on hand.
        suggested_qty = max(round(daily_rate * REORDER_COVER_DAYS - level.stock_qty), 1)
        supplier = await supplier_repo.get_by_id(company_id, product.supplier_id)
        candidates.append(
            {
                "type": "reorden_predictivo",
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "stock_qty": level.stock_qty,
                "daily_rate": round(daily_rate, 2),
                "days_of_cover": round(days_of_cover, 1),
                "supplier_id": product.supplier_id,
                "supplier_name": supplier.name if supplier else "proveedor desconocido",
                "unit_cost": product.cost,
                "suggested_qty": suggested_qty,
                "total_cost": round(suggested_qty * product.cost, 2),
            }
        )

    return candidates


# --- Khipu (auditoría de datos) ------------------------------------------

CATEGORY_AUDIT_MIN_CONFIDENCE = 70  # below this, don't bother the owner
CATEGORY_AUDIT_MAX_PRODUCTS = 500  # one LLM call holds the whole catalog comfortably at this size
CATEGORY_AUDIT_MAX_FINDINGS = 20  # safety cap on alerts created per sweep


async def detect_catalog_issues(company_id: str, session: AsyncSession) -> list[dict[str, Any]]:
    """Audit the catalog for products filed under a clearly wrong category.

    The one LLM-assisted detector (see module docstring for why): the model
    receives the company's real category list + the catalog (sku, name,
    current category) and returns suspected misassignments. Every suspicion
    is then validated here in plain Python before becoming a candidate:

    - the SKU must be a real product (no hallucinated items),
    - the suggested category must exist verbatim in the company's real list
      (the LLM can never invent a category),
    - it must differ from the current one,
    - confidence must clear CATEGORY_AUDIT_MIN_CONFIDENCE.

    A human still approves every recategorization downstream (the action is
    never auto-applied) — the LLM suspects, Python filters, the user decides.
    """
    product_repo = ProductRepository(session)
    categories = await product_repo.get_all_categories(company_id)
    products, _ = await product_repo.get_all(
        company_id, category_id=None, search=None, offset=0, limit=CATEGORY_AUDIT_MAX_PRODUCTS
    )
    if len(categories) < 2 or len(products) < 5:
        return []  # nothing meaningful to audit yet

    cat_by_id = {c.id: c for c in categories}
    catalog = [
        {"sku": p.sku, "name": p.name, "category": cat_by_id[p.category_id].name if p.category_id in cat_by_id else None}
        for p in products
    ]

    model = get_chat_model().with_structured_output(CategoryAuditResult)
    usage_callback = UsageMetadataCallbackHandler()
    result: CategoryAuditResult = await model.ainvoke(
        [
            ("system", CATEGORY_AUDIT_SYSTEM_PROMPT),
            (
                "human",
                f"Categorías válidas: {[c.name for c in categories]}\n\n"
                f"Catálogo (sku, nombre, categoría actual): {catalog}",
            ),
        ],
        config={"callbacks": [usage_callback]},
    )
    # Same usage logging as graph.compose() so Khipu's detection cost shows
    # up in ai_usage too, tagged separately from the agents' compose calls.
    for model_name, usage in usage_callback.usage_metadata.items():
        await AiUsageRepository(session).create(
            AiUsageEvent(
                company_id=company_id,
                source="agent:catalogo:detector",
                model=model_name,
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                cached_input_tokens=(usage.get("input_token_details") or {}).get("cache_read"),
            )
        )

    # --- Validation: the LLM suspects, Python filters ---------------------
    def _fold(s: str) -> str:
        return " ".join(s.casefold().split())

    cat_by_folded_name = {_fold(c.name): c for c in categories}
    products_by_sku = {p.sku: p for p in products}

    candidates: list[dict[str, Any]] = []
    for finding in result.findings[:CATEGORY_AUDIT_MAX_FINDINGS]:
        product = products_by_sku.get(finding.sku)
        if not product:
            continue  # hallucinated SKU
        suggested = cat_by_folded_name.get(_fold(finding.suggested_category))
        if not suggested:
            continue  # category not in the company's real list — invented
        current = cat_by_id.get(product.category_id)
        if current and suggested.id == current.id:
            continue  # no-op suggestion
        if finding.confidence < CATEGORY_AUDIT_MIN_CONFIDENCE:
            continue  # not sure enough to bother the owner
        candidates.append(
            {
                "type": "categoria_incorrecta",
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "current_category": current.name if current else "Sin categoría",
                "suggested_category": suggested.name,
                "new_category_id": suggested.id,
                "confidence": finding.confidence,
                "reason": finding.reason,
            }
        )

    return candidates
