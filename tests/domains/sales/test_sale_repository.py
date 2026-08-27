import pytest

from src.domains.sales.repository import SaleRepository


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def one(self):
        return self.value


class _AllocationSession:
    """Small database boundary fake with different count/max answers.

    The incident is specifically caused by those two values diverging after a
    deletion. Returning both lets the test fail if the old count-based
    allocator is accidentally retained.
    """

    def __init__(self, *, max_number: int | None, row_count: int = 66):
        self.max_number = max_number
        self.row_count = row_count
        self.locked_company: str | None = None

    async def execute(self, statement, params):
        sql = str(statement)
        assert "pg_advisory_xact_lock" in sql
        self.locked_company = params["company_id"]

    async def exec(self, statement):
        sql = str(statement).lower()
        if "max(" in sql:
            return _ScalarResult(self.max_number)
        if "count(" in sql:
            return _ScalarResult(self.row_count)
        raise AssertionError(f"Unexpected query: {sql}")


@pytest.mark.asyncio
async def test_reserve_next_code_uses_highest_number_and_locks_company():
    session = _AllocationSession(max_number=67, row_count=66)

    code = await SaleRepository(session).reserve_next_code("company-1")

    assert code == "V-00068"
    assert session.locked_company == "company-1"


@pytest.mark.asyncio
async def test_reserve_next_code_starts_at_one_when_company_has_no_sales():
    session = _AllocationSession(max_number=None, row_count=0)

    code = await SaleRepository(session).reserve_next_code("company-1")

    assert code == "V-00001"
