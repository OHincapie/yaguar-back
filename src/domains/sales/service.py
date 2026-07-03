from src.domains.inventory.service import InventoryService
from src.domains.ledger.models import LedgerCategory, LedgerEntry, LedgerType
from src.domains.ledger.repository import LedgerRepository
from src.domains.sales.models import Sale, SaleLine
from src.domains.sales.repository import SaleRepository
from src.domains.sales.schemas import SaleCreate, SaleStatusUpdate
from src.shared.middleware.errors import ConflictError, NotFoundError


class SaleService:
    def __init__(
        self,
        repo: SaleRepository,
        inventory_service: InventoryService,
        ledger_repo: LedgerRepository,
    ):
        self.repo = repo
        self.inventory_service = inventory_service
        self.ledger_repo = ledger_repo

    async def list_sales(self, status, customer_id: str | None, from_date, to_date, page: int, page_size: int):
        offset = (page - 1) * page_size
        return await self.repo.get_all(
            status=status, customer_id=customer_id, from_date=from_date, to_date=to_date,
            offset=offset, limit=page_size,
        )

    async def get_sale(self, id: str) -> Sale:
        sale = await self.repo.get_by_id(id)
        if not sale:
            raise NotFoundError("Sale", id)
        return sale

    async def get_lines(self, id: str) -> list[SaleLine]:
        await self.get_sale(id)
        return await self.repo.get_lines(id)

    async def create_sale(self, data: SaleCreate) -> Sale:
        existing = await self.repo.get_by_id(data.id)
        if existing:
            raise ConflictError(f"Sale '{data.id}' already exists")

        for line_data in data.lines:
            await self.inventory_service.apply_sale(
                product_sku=line_data.product_sku,
                qty=line_data.qty,
                sale_id=data.id,
            )

        lines = [SaleLine(sale_id=data.id, **line.model_dump()) for line in data.lines]
        total = sum(line.qty * line.unit_price for line in data.lines)

        sale = Sale(
            id=data.id,
            customer_id=data.customer_id,
            total=total,
            payment_method=data.payment_method,
            status=data.status,
            notes=data.notes,
        )
        sale = await self.repo.create(sale, lines)

        await self.ledger_repo.create(
            LedgerEntry(
                concept=f"Venta {data.id} - cliente {data.customer_id}",
                category=LedgerCategory.VENTAS,
                credit=total,
                type=LedgerType.IN,
                reference_id=data.id,
                reference_type="sale",
            )
        )
        return sale

    async def update_status(self, id: str, data: SaleStatusUpdate) -> Sale:
        sale = await self.get_sale(id)
        sale.status = data.status
        return await self.repo.update(sale)
