from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.accounts.repository import AccountsRepository
from src.domains.inventory.repository import InventoryRepository
from src.domains.inventory.service import InventoryService
from src.domains.ledger.repository import LedgerRepository
from src.domains.pos.schemas import CheckoutRequest, CheckoutResponse
from src.domains.products.repository import ProductRepository
from src.domains.sales.models import SaleStatus
from src.domains.sales.repository import SaleRepository
from src.domains.sales.schemas import SaleCreate, SaleLineCreate
from src.domains.sales.service import SaleService
from src.shared.database import get_session
from src.shared.middleware.auth import CurrentUser

router = APIRouter(prefix="/pos", tags=["pos"])


def get_sale_service(session: Annotated[AsyncSession, Depends(get_session)]) -> SaleService:
    return SaleService(
        SaleRepository(session),
        InventoryService(InventoryRepository(session), ProductRepository(session)),
        LedgerRepository(session),
        AccountsRepository(session),
    )


@router.post("/checkout", response_model=CheckoutResponse, status_code=201)
async def checkout(
    current_user: CurrentUser,
    data: CheckoutRequest,
    service: Annotated[SaleService, Depends(get_sale_service)],
):
    sale_data = SaleCreate(
        customer_id=data.customer_id,
        payment_method=data.payment_method,
        status=SaleStatus.PAGADO if data.payment_method.value != "Crédito" else SaleStatus.PENDIENTE,
        notes=data.notes,
        lines=[SaleLineCreate(**line.model_dump()) for line in data.lines],
    )
    sale = await service.create_sale(current_user.company_id, sale_data)
    return CheckoutResponse(sale=sale, total=sale.total, items_count=len(data.lines))
