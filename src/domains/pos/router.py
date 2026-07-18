from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.accounts.repository import AccountsRepository
from src.domains.agents.repository import AgentRepository
from src.domains.customers.repository import CustomerRepository
from src.domains.inventory.repository import InventoryRepository
from src.domains.inventory.service import InventoryService
from src.domains.ledger.repository import LedgerRepository
from src.domains.pos.schemas import CheckoutRequest, CheckoutResponse
from src.domains.products.repository import ProductRepository
from src.domains.sales.repository import PaymentMethodRepository, SaleRepository
from src.domains.sales.schemas import SaleCreate, SaleLineCreate
from src.domains.sales.service import SaleService
from src.shared.database import get_session
from src.shared.middleware.auth import CurrentUser, require_module

router = APIRouter(prefix="/pos", tags=["pos"], dependencies=[Depends(require_module("pos"))])


def get_sale_service(session: Annotated[AsyncSession, Depends(get_session)]) -> SaleService:
    return SaleService(
        SaleRepository(session),
        InventoryService(InventoryRepository(session), ProductRepository(session)),
        LedgerRepository(session),
        AccountsRepository(session),
        PaymentMethodRepository(session),
        CustomerRepository(session),
        AgentRepository(session),
    )


@router.post("/checkout", response_model=CheckoutResponse, status_code=201)
async def checkout(
    current_user: CurrentUser,
    data: CheckoutRequest,
    service: Annotated[SaleService, Depends(get_sale_service)],
):
    sale_data = SaleCreate(
        customer_id=data.customer_id,
        payments=data.payments,
        notes=data.notes,
        lines=[SaleLineCreate(**line.model_dump()) for line in data.lines],
    )
    sale = await service.create_sale(current_user.company_id, sale_data)
    return CheckoutResponse(sale=sale, total=sale.total, items_count=len(data.lines))
