from datetime import datetime

from pydantic import BaseModel, model_validator

from src.domains.sales.models import SaleStatus


class SaleLineCreate(BaseModel):
    product_id: str
    qty: float
    unit_price: float
    unit_cost: float


class SaleLineRead(BaseModel):
    id: int
    sale_id: str
    product_id: str
    qty: float
    unit_price: float
    unit_cost: float

    model_config = {"from_attributes": True}


class PaymentLine(BaseModel):
    payment_method_id: str
    amount: float


class SaleCreate(BaseModel):
    # None = walk-in/casual sale, no buyer registered — see SaleService for
    # the rule that this can't be combined with a credit payment method.
    customer_id: str | None = None
    payments: list[PaymentLine]
    notes: str | None = None
    lines: list[SaleLineCreate] = []
    # No `status` field on purpose — SaleService.create_sale derives it from
    # the payment methods used (any credit method → pendiente, otherwise
    # pagado) the same way regardless of caller (POS checkout, manual
    # "Nueva venta", the chat), so the paths can't drift out of sync again.

    @model_validator(mode="after")
    def _at_least_one_payment(self):
        if not self.payments:
            raise ValueError("A sale needs at least one payment line")
        return self


class SaleStatusUpdate(BaseModel):
    status: SaleStatus


class SaleUpdate(BaseModel):
    notes: str | None = None
    # When provided, replaces the sale's lines entirely and recalculates
    # subtotal/discount_amount/tax_amount/total from the company's current
    # discount_pct/tax_pct settings — same rule used at creation time.
    lines: list[SaleLineCreate] | None = None
    # When provided, replaces the sale's payment lines entirely — must sum
    # to the (possibly just-recalculated) total. Optional independently of
    # `lines`: you can correct how a sale was paid without touching items.
    payments: list[PaymentLine] | None = None


class SaleRead(BaseModel):
    id: str
    code: str
    customer_id: str | None
    date: datetime
    subtotal: float
    discount_amount: float
    tax_amount: float
    total: float
    payment_method: str
    status: SaleStatus
    notes: str | None

    model_config = {"from_attributes": True}


class SalePaymentRead(BaseModel):
    id: int
    sale_id: str
    payment_method_id: str
    payment_method_name: str
    amount: float


class PaymentMethodRead(BaseModel):
    id: str
    name: str
    is_credit: bool
    is_active: bool

    model_config = {"from_attributes": True}


class PaymentMethodCreate(BaseModel):
    name: str
    is_credit: bool = False


class PaymentMethodUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
