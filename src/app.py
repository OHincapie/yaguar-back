from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.domains.accounts.router import router as auth_router
from src.domains.agents.router import router as agents_router
from src.domains.ai_usage.router import router as ai_usage_router
from src.domains.customers.router import router as customers_router
from src.domains.dashboard.router import router as dashboard_router
from src.domains.inventory.router import router as inventory_router
from src.domains.ledger.router import router as ledger_router
from src.domains.pos.router import router as pos_router
from src.domains.products.router import categories_router, router as products_router
from src.domains.purchases.router import router as purchases_router
from src.domains.sales.router import payment_methods_router, router as sales_router
from src.domains.suppliers.router import router as suppliers_router
from src.shared.middleware.errors import register_error_handlers
from src.shared.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Yaguar ERP API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.cors_allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

API_PREFIX = "/api"
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(products_router, prefix=API_PREFIX)
app.include_router(categories_router, prefix=API_PREFIX)
app.include_router(inventory_router, prefix=API_PREFIX)
app.include_router(suppliers_router, prefix=API_PREFIX)
app.include_router(purchases_router, prefix=API_PREFIX)
app.include_router(customers_router, prefix=API_PREFIX)
app.include_router(sales_router, prefix=API_PREFIX)
app.include_router(payment_methods_router, prefix=API_PREFIX)
app.include_router(ledger_router, prefix=API_PREFIX)
app.include_router(pos_router, prefix=API_PREFIX)
app.include_router(dashboard_router, prefix=API_PREFIX)
app.include_router(agents_router, prefix=API_PREFIX)
app.include_router(ai_usage_router, prefix=API_PREFIX)
