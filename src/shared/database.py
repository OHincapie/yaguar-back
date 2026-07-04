from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.shared.settings import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    connect_args={"ssl": "require"},
)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    # expire_on_commit=False: several request handlers (e.g. POS checkout)
    # commit more than once per request (inventory, sale, ledger). With the
    # default expire-on-commit behavior, an object read after a *later*
    # commit raises MissingGreenlet when FastAPI serializes the response,
    # since attribute access would need to lazily re-fetch outside of an
    # awaited context.
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
