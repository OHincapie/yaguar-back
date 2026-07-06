from src.domains.accounts.repository import AccountsRepository
from src.domains.inventory.service import InventoryService
from src.domains.ledger.models import LedgerCategory, LedgerEntry, LedgerType
from src.domains.ledger.repository import LedgerRepository
from src.domains.sales.models import Sale, SaleLine
from src.domains.sales.repository import SaleRepository
from src.domains.sales.schemas import SaleCreate, SaleLineCreate, SaleStatusUpdate, SaleUpdate
from src.shared.middleware.errors import NotFoundError


class SaleService:
    def __init__(
        self,
        repo: SaleRepository,
        inventory_service: InventoryService,
        ledger_repo: LedgerRepository,
        accounts_repo: AccountsRepository,
    ):
        self.repo = repo
        self.inventory_service = inventory_service
        self.ledger_repo = ledger_repo
        self.accounts_repo = accounts_repo

    async def list_sales(self, company_id: str, status, customer_id: str | None, from_date, to_date, page: int, page_size: int):
        offset = (page - 1) * page_size
        return await self.repo.get_all(
            company_id, status=status, customer_id=customer_id, from_date=from_date, to_date=to_date,
            offset=offset, limit=page_size,
        )

    async def get_sale(self, company_id: str, code: str) -> Sale:
        sale = await self.repo.get_by_code(company_id, code)
        if not sale:
            raise NotFoundError("Sale", code)
        return sale

    async def get_lines(self, company_id: str, code: str) -> list[SaleLine]:
        sale = await self.get_sale(company_id, code)
        return await self.repo.get_lines(sale.id)

    async def _compute_amounts(self, company_id: str, lines: list[SaleLineCreate]) -> tuple[float, float, float, float]:
        """Returns (subtotal, discount_amount, tax_amount, total) using the
        company's current discount_pct/tax_pct — same rule for create and edit,
        so a sale never silently drifts from what checkout would compute today."""
        company = await self.accounts_repo.get_company(company_id)
        assert company is not None
        subtotal = sum(line.qty * line.unit_price for line in lines)
        discount_amount = subtotal * (company.discount_pct / 100) if company.discount_enabled else 0.0
        tax_amount = (subtotal - discount_amount) * (company.tax_pct / 100) if company.tax_enabled else 0.0
        total = subtotal - discount_amount + tax_amount
        return subtotal, discount_amount, tax_amount, total

    async def create_sale(self, company_id: str, data: SaleCreate) -> Sale:
        count = await self.repo.count_for_company(company_id)
        code = f"V-{count + 1:05d}"

        subtotal, discount_amount, tax_amount, total = await self._compute_amounts(company_id, data.lines)
        sale = Sale(
            company_id=company_id,
            code=code,
            customer_id=data.customer_id,
            subtotal=subtotal,
            discount_amount=discount_amount,
            tax_amount=tax_amount,
            total=total,
            payment_method=data.payment_method,
            status=data.status,
            notes=data.notes,
        )

        for line_data in data.lines:
            await self.inventory_service.apply_sale(
                company_id=company_id,
                product_id=line_data.product_id,
                qty=line_data.qty,
                sale_id=sale.id,
            )

        lines = [SaleLine(sale_id=sale.id, **line.model_dump()) for line in data.lines]
        sale = await self.repo.create(sale, lines)

        await self.ledger_repo.create(
            LedgerEntry(
                company_id=company_id,
                concept=f"Venta {sale.code}",
                category=LedgerCategory.VENTAS,
                credit=total,
                type=LedgerType.IN,
                reference_id=sale.id,
                reference_type="sale",
            )
        )
        return sale

    async def update_status(self, company_id: str, code: str, data: SaleStatusUpdate) -> Sale:
        sale = await self.get_sale(company_id, code)
        sale.status = data.status
        return await self.repo.update(sale)

    async def update_sale(self, company_id: str, code: str, data: SaleUpdate) -> Sale:
        sale = await self.get_sale(company_id, code)

        if data.notes is not None:
            sale.notes = data.notes

        if data.lines is not None:
            old_lines = await self.repo.get_lines(sale.id)
            for old_line in old_lines:
                await self.inventory_service.reverse_sale(
                    company_id=company_id, product_id=old_line.product_id, qty=old_line.qty, sale_id=sale.id
                )

            for line_data in data.lines:
                await self.inventory_service.apply_sale(
                    company_id=company_id, product_id=line_data.product_id, qty=line_data.qty, sale_id=sale.id
                )

            subtotal, discount_amount, tax_amount, total = await self._compute_amounts(company_id, data.lines)
            sale.subtotal = subtotal
            sale.discount_amount = discount_amount
            sale.tax_amount = tax_amount
            sale.total = total

            await self.repo.replace_lines(sale.id, [SaleLine(sale_id=sale.id, **line.model_dump()) for line in data.lines])

            ledger_entry = await self.ledger_repo.get_by_reference(company_id, sale.id, "sale")
            if ledger_entry:
                ledger_entry.credit = total
                await self.ledger_repo.update(ledger_entry)

        return await self.repo.update(sale)
