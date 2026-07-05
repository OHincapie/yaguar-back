"""What actually happens when a proposal is approved (by a human or by
autonomy rules). Deliberately plain Python calling the existing services
— the LLM never invokes these directly, it only requests one by name
via the `action` dict built in graph.py."""

from typing import Any, Awaitable, Callable

from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.ledger.repository import LedgerRepository
from src.domains.inventory.repository import InventoryRepository
from src.domains.products.repository import ProductRepository
from src.domains.products.schemas import ProductUpdate
from src.domains.products.service import ProductService
from src.domains.inventory.service import InventoryService
from src.domains.purchases.repository import PurchaseRepository
from src.domains.purchases.schemas import PurchaseCreate, PurchaseLineCreate
from src.domains.purchases.service import PurchaseService

ActionHandler = Callable[[str, dict[str, Any], AsyncSession], Awaitable[dict[str, Any]]]


async def _create_purchase(company_id: str, args: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    product_repo = ProductRepository(session)
    purchase_service = PurchaseService(
        PurchaseRepository(session),
        InventoryService(InventoryRepository(session), product_repo),
        LedgerRepository(session),
        product_repo,
    )
    purchase = await purchase_service.create_purchase(
        company_id,
        PurchaseCreate(
            supplier_id=args["supplier_id"],
            notes="Generada automáticamente por Inti (agente de inventario)",
            lines=[PurchaseLineCreate(product_id=args["product_id"], qty=args["qty"], unit_cost=args["unit_cost"])],
        ),
    )
    return {"purchase_id": purchase.id, "purchase_code": purchase.code, "total": purchase.total}


async def _update_product_price(company_id: str, args: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    product_service = ProductService(ProductRepository(session))
    product = await product_service.update_product(
        company_id, args["sku"], ProductUpdate(price=args["new_price"])
    )
    return {"product_id": product.id, "sku": product.sku, "new_price": product.price}


ACTION_HANDLERS: dict[str, ActionHandler] = {
    "create_purchase": _create_purchase,
    "update_product_price": _update_product_price,
}


async def execute_action(company_id: str, action: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    handler = ACTION_HANDLERS.get(action["name"])
    if not handler:
        raise ValueError(f"Unknown agent action: {action['name']!r}")
    return await handler(company_id, action["args"], session)
