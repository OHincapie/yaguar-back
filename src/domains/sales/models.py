import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from sqlalchemy import DateTime
from sqlmodel import AutoString, Field, SQLModel, UniqueConstraint


class SaleStatus(StrEnum):
    PAGADO = "pagado"
    PENDIENTE = "pendiente"
    VENCIDO = "vencido"
    CANCELADO = "cancelado"


class PaymentMethodConfig(SQLModel, table=True):
    """Company-configurable payment methods — replaced the old hardcoded
    PaymentMethod enum so a company can add its own (e.g. "Nequi",
    "Daviplata") instead of being stuck with Efectivo/Tarjeta/Transferencia/
    Crédito. Every company gets those four seeded on registration."""

    __tablename__ = "payment_methods"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_payment_methods_company_name"),)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    company_id: str = Field(foreign_key="companies.id", max_length=36, index=True)
    name: str = Field(max_length=50)
    # A credit method means "no money changed hands yet" — mutually
    # exclusive with every other method on the same sale (see
    # SaleService._validate_payments) and always leaves the sale
    # "pendiente" regardless of amount. Exactly one seeded method (the
    # default "Crédito") has this set; a company could mark another one
    # this way too (e.g. "Fiado"), but two credit methods split across one
    # sale would still be rejected — deliberately all-or-nothing, not a
    # partial-payment/receivables feature (that's a bigger, separate thing —
    # Customer.saldo isn't wired to anything yet).
    is_credit: bool = Field(default=False)
    is_active: bool = Field(default=True)


class Sale(SQLModel, table=True):
    __tablename__ = "sales"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_sales_company_code"),)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    company_id: str = Field(foreign_key="companies.id", max_length=36, index=True)
    code: str = Field(max_length=50)
    # Nullable: a walk-in/casual sale with no identified buyer. A credit
    # sale always requires a customer (you can't extend credit to someone
    # you didn't register) — enforced in SaleService, not at the DB level.
    customer_id: Optional[str] = Field(default=None, foreign_key="customers.id", max_length=36)
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))
    # subtotal = sum(qty * unit_price); total = subtotal - discount_amount + tax_amount.
    # Stored (not recomputed later) so a sale's numbers stay accurate even if
    # the company's discount_pct/tax_pct or enabled flags change afterwards.
    subtotal: float = Field(default=0.0)
    discount_amount: float = Field(default=0.0)
    tax_amount: float = Field(default=0.0)
    total: float = Field(default=0.0)
    # Denormalized display summary derived from this sale's SalePayment rows
    # (e.g. "Efectivo", "Efectivo + Transferencia") — kept so listing sales
    # doesn't need a join every time. The real source of truth for amounts
    # per method is the sale_payments table; this is read-only from the
    # caller's perspective, SaleService recomputes it whenever payments change.
    payment_method: str = Field(default="", sa_type=AutoString)
    status: SaleStatus = Field(default=SaleStatus.PENDIENTE, sa_type=AutoString)
    notes: Optional[str] = Field(default=None, max_length=500)
    # Only meaningful for credit sales — Mara (collections agent) uses this
    # to flag a sale as overdue. Null for cash/card/transfer sales.
    due_date: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))


class SaleLine(SQLModel, table=True):
    __tablename__ = "sale_lines"

    id: Optional[int] = Field(default=None, primary_key=True)
    sale_id: str = Field(foreign_key="sales.id", max_length=36)
    product_id: str = Field(foreign_key="products.id", max_length=36)
    qty: float
    unit_price: float
    unit_cost: float


class SalePayment(SQLModel, table=True):
    """One line per payment method used on a sale. A sale has 1+ of these;
    their amounts must sum exactly to Sale.total (validated in
    SaleService), which is how a split payment (part cash, part transfer)
    is represented — there's no separate "split" flag, just multiple rows."""

    __tablename__ = "sale_payments"

    id: Optional[int] = Field(default=None, primary_key=True)
    sale_id: str = Field(foreign_key="sales.id", max_length=36)
    payment_method_id: str = Field(foreign_key="payment_methods.id", max_length=36)
    amount: float
