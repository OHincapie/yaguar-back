from src.domains.inventory.service import InventoryService
from src.domains.ledger.models import LedgerCategory, LedgerEntry, LedgerType
from src.domains.ledger.repository import LedgerRepository
from src.domains.purchases.models import Purchase, PurchaseLine, PurchaseStatus
from src.domains.purchases.repository import PurchaseRepository
from src.domains.purchases.schemas import PurchaseCreate, PurchaseStatusUpdate
from src.shared.middleware.errors import BusinessError, NotFoundError


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

    async def list_purchases(self, company_id: str, status, supplier_id: str | None, page: int, page_size: int):
        offset = (page - 1) * page_size
        return await self.repo.get_all(company_id, status=status, supplier_id=supplier_id, offset=offset, limit=page_size)

    async def get_purchase(self, company_id: str, code: str) -> Purchase:
        purchase = await self.repo.get_by_code(company_id, code)
        if not purchase:
            raise NotFoundError("Purchase", code)
        return purchase

    async def get_lines(self, company_id: str, code: str) -> list[PurchaseLine]:
        purchase = await self.get_purchase(company_id, code)
        return await self.repo.get_lines(purchase.id)

    async def create_purchase(self, company_id: str, data: PurchaseCreate) -> Purchase:
        count = await self.repo.count_for_company(company_id)
        code = f"OC-{count + 1:05d}"

        total = sum(line.qty * line.unit_cost for line in data.lines)
        purchase = Purchase(
            company_id=company_id,
            code=code,
            supplier_id=data.supplier_id,
            total=total,
            eta=data.eta,
            notes=data.notes,
        )
        lines = [PurchaseLine(purchase_id=purchase.id, **line.model_dump()) for line in data.lines]
        return await self.repo.create(purchase, lines)

    async def update_status(self, company_id: str, code: str, data: PurchaseStatusUpdate) -> Purchase:
        purchase = await self.get_purchase(company_id, code)
        purchase.status = data.status
        return await self.repo.update(purchase)

    async def receive(self, company_id: str, code: str) -> Purchase:
        purchase = await self.get_purchase(company_id, code)
        if purchase.status == PurchaseStatus.RECIBIDO:
            raise BusinessError("Purchase already received")
        if purchase.status == PurchaseStatus.CANCELADO:
            raise BusinessError("Cannot receive a cancelled purchase")

        lines = await self.repo.get_lines(purchase.id)
        for line in lines:
            await self.inventory_service.apply_purchase_receipt(
                company_id=company_id,
                product_id=line.product_id,
                qty=line.qty,
                purchase_id=purchase.id,
            )

        await self.ledger_repo.create(
            LedgerEntry(
                company_id=company_id,
                concept=f"Recepción orden de compra {purchase.code}",
                category=LedgerCategory.COMPRAS,
                debit=purchase.total,
                type=LedgerType.OUT,
                reference_id=purchase.id,
                reference_type="purchase",
            )
        )

        purchase.status = PurchaseStatus.RECIBIDO
        return await self.repo.update(purchase)
