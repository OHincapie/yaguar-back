from datetime import datetime

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.sales.models import PaymentMethodConfig, Sale, SaleLine, SalePayment, SaleStatus


class SaleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(
        self,
        company_id: str,
        status: SaleStatus | None = None,
        customer_id: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Sale], int]:
        query = select(Sale).where(Sale.company_id == company_id)
        if status:
            query = query.where(Sale.status == status)
        if customer_id:
            query = query.where(Sale.customer_id == customer_id)
        if from_date:
            query = query.where(Sale.date >= from_date)
        if to_date:
            query = query.where(Sale.date <= to_date)

        count_result = await self.session.exec(query)  # type: ignore
        total = len(count_result.all())

        result = await self.session.exec(query.order_by(Sale.date.desc()).offset(offset).limit(limit))  # type: ignore
        return result.all(), total

    async def get_by_id(self, company_id: str, id: str) -> Sale | None:
        result = await self.session.exec(  # type: ignore
            select(Sale).where(Sale.company_id == company_id, Sale.id == id)
        )
        return result.first()

    async def get_by_code(self, company_id: str, code: str) -> Sale | None:
        result = await self.session.exec(  # type: ignore
            select(Sale).where(Sale.company_id == company_id, Sale.code == code)
        )
        return result.first()

    async def count_for_company(self, company_id: str) -> int:
        result = await self.session.exec(  # type: ignore
            select(func.count()).select_from(Sale).where(Sale.company_id == company_id)
        )
        return int(result.one())

    async def get_lines(self, sale_id: str) -> list[SaleLine]:
        result = await self.session.exec(select(SaleLine).where(SaleLine.sale_id == sale_id))  # type: ignore
        return result.all()

    async def create(self, sale: Sale, lines: list[SaleLine], payments: list[SalePayment]) -> Sale:
        self.session.add(sale)
        for line in lines:
            self.session.add(line)
        for payment in payments:
            self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(sale)
        return sale

    async def update(self, sale: Sale) -> Sale:
        self.session.add(sale)
        await self.session.commit()
        await self.session.refresh(sale)
        return sale

    async def replace_lines(self, sale_id: str, lines: list[SaleLine]) -> list[SaleLine]:
        existing = await self.get_lines(sale_id)
        for line in existing:
            await self.session.delete(line)
        for line in lines:
            self.session.add(line)
        await self.session.commit()
        for line in lines:
            await self.session.refresh(line)
        return lines

    async def get_payments(self, sale_id: str) -> list[SalePayment]:
        result = await self.session.exec(select(SalePayment).where(SalePayment.sale_id == sale_id))  # type: ignore
        return result.all()

    async def replace_payments(self, sale_id: str, payments: list[SalePayment]) -> list[SalePayment]:
        existing = await self.get_payments(sale_id)
        for payment in existing:
            await self.session.delete(payment)
        for payment in payments:
            self.session.add(payment)
        await self.session.commit()
        for payment in payments:
            await self.session.refresh(payment)
        return payments

    async def delete(self, sale: Sale) -> None:
        await self.session.delete(sale)
        await self.session.commit()


class PaymentMethodRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self, company_id: str, active_only: bool = False) -> list[PaymentMethodConfig]:
        query = select(PaymentMethodConfig).where(PaymentMethodConfig.company_id == company_id)
        if active_only:
            query = query.where(PaymentMethodConfig.is_active == True)  # noqa: E712
        result = await self.session.exec(query.order_by(PaymentMethodConfig.name))  # type: ignore
        return result.all()

    async def get_by_id(self, company_id: str, id: str) -> PaymentMethodConfig | None:
        result = await self.session.exec(  # type: ignore
            select(PaymentMethodConfig).where(
                PaymentMethodConfig.company_id == company_id, PaymentMethodConfig.id == id
            )
        )
        return result.first()

    async def get_by_ids(self, company_id: str, ids: list[str]) -> list[PaymentMethodConfig]:
        if not ids:
            return []
        result = await self.session.exec(  # type: ignore
            select(PaymentMethodConfig).where(
                PaymentMethodConfig.company_id == company_id, PaymentMethodConfig.id.in_(ids)
            )
        )
        return result.all()

    async def create(self, method: PaymentMethodConfig) -> PaymentMethodConfig:
        self.session.add(method)
        await self.session.commit()
        await self.session.refresh(method)
        return method

    async def update(self, method: PaymentMethodConfig) -> PaymentMethodConfig:
        self.session.add(method)
        await self.session.commit()
        await self.session.refresh(method)
        return method

    async def seed_defaults(self, company_id: str) -> list[PaymentMethodConfig]:
        """Called once when a company is created. Matches the four values
        the old hardcoded PaymentMethod enum used to have — existing
        behavior, just no longer hardcoded."""
        defaults = [
            PaymentMethodConfig(company_id=company_id, name="Efectivo", is_credit=False),
            PaymentMethodConfig(company_id=company_id, name="Tarjeta", is_credit=False),
            PaymentMethodConfig(company_id=company_id, name="Transferencia", is_credit=False),
            PaymentMethodConfig(company_id=company_id, name="Crédito", is_credit=True),
        ]
        for m in defaults:
            self.session.add(m)
        await self.session.commit()
        for m in defaults:
            await self.session.refresh(m)
        return defaults
