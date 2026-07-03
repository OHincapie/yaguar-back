from src.domains.inventory.service import InventoryService
from src.domains.ledger.models import LedgerCategory, LedgerEntry, LedgerType
from src.domains.ledger.repository import LedgerRepository
from src.domains.purchases.models import Purchase, PurchaseLine, PurchaseStatus
from src.domains.purchases.repository import PurchaseRepository
from src.domains.purchases.schemas import PurchaseCreate, PurchaseStatusUpdate
from src.shared.middleware.errors import BusinessError, ConflictError, NotFoundError


class PurchaseService:
    def __init__(
        self,
        repo: PurchaseRepository,
        inventory_service: InventoryService,
        ledger_repo: LedgerRepository,
    ):
        self.repo = repo
        self.inventory_service = inventory_service
        self.ledger_repo = ledger_repo

    async def list_purchases(self, status, supplier_id: str | None, page: int, page_size: int):
        offset = (page - 1) * page_size
        return await self.repo.get_all(status=status, supplier_id=supplier_id, offset=offset, limit=page_size)

    async def get_purchase(self, id: str) -> Purchase:
        purchase = await self.repo.get_by_id(id)
        if not purchase:
            raise NotFoundError("Purchase", id)
        return purchase

    async def get_lines(self, id: str) -> list[PurchaseLine]:
        await self.get_purchase(id)
        return await self.repo.get_lines(id)

    async def create_purchase(self, data: PurchaseCreate) -> Purchase:
        existing = await self.repo.get_by_id(data.id)
        if existing:
            raise ConflictError(f"Purchase '{data.id}' already exists")

        lines = [PurchaseLine(purchase_id=data.id, **line.model_dump()) for line in data.lines]
        total = sum(line.qty * line.unit_cost for line in data.lines)

        purchase = Purchase(
            id=data.id,
            supplier_id=data.supplier_id,
            total=total,
            eta=data.eta,
            notes=data.notes,
        )
        return await self.repo.create(purchase, lines)

    async def update_status(self, id: str, data: PurchaseStatusUpdate) -> Purchase:
        purchase = await self.get_purchase(id)
        purchase.status = data.status
        return await self.repo.update(purchase)

    async def receive(self, id: str) -> Purchase:
        purchase = await self.get_purchase(id)
        if purchase.status == PurchaseStatus.RECIBIDO:
            raise BusinessError("Purchase already received")
        if purchase.status == PurchaseStatus.CANCELADO:
            raise BusinessError("Cannot receive a cancelled purchase")

        lines = await self.repo.get_lines(id)
        for line in lines:
            await self.inventory_service.apply_purchase_receipt(
                product_sku=line.product_sku,
                qty=line.qty,
                purchase_id=id,
            )

        await self.ledger_repo.create(
            LedgerEntry(
                concept=f"Recepción orden de compra {id}",
                category=LedgerCategory.COMPRAS,
                debit=purchase.total,
                type=LedgerType.OUT,
                reference_id=id,
                reference_type="purchase",
            )
        )

        purchase.status = PurchaseStatus.RECIBIDO
        return await self.repo.update(purchase)
