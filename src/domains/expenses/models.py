import uuid

from sqlmodel import Field, SQLModel, UniqueConstraint


class ExpenseAccount(SQLModel, table=True):
    """A company-configurable operational-expense account (Gastos module).

    Deliberately a flat, editable list per company — same pattern as
    payment_methods and product categories — not a hierarchical chart of
    accounts. `puc_code` is the optional hook to the Colombian Plan Único de
    Cuentas (e.g. 5120 Arrendamientos, 5135 Servicios): it keeps expenses
    exportable/compatible with what an accountant expects, without building
    a full double-entry PUC engine (that's the future-vision item in the
    backlog). Seeded with the common grupo-51 expense accounts on company
    registration.
    """

    __tablename__ = "expense_accounts"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_expense_accounts_company_name"),)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    company_id: str = Field(foreign_key="companies.id", max_length=36, index=True)
    name: str = Field(max_length=100)
    # Optional PUC code — free text so a company can use its own coding too.
    puc_code: str | None = Field(default=None, max_length=20)
    color: str = Field(max_length=30)
    is_active: bool = Field(default=True)
