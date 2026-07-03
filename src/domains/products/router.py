from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.domains.products.repository import ProductRepository
from src.domains.products.schemas import CategoryCreate, CategoryRead, ProductCreate, ProductRead, ProductUpdate
from src.domains.products.service import ProductService
from src.shared.database import get_session
from src.shared.middleware.auth import CurrentUser
from src.shared.types import MessageResponse, PaginatedResponse
from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/products", tags=["products"])


def get_service(session: Annotated[AsyncSession, Depends(get_session)]) -> ProductService:
    return ProductService(ProductRepository(session))


@router.get("", response_model=PaginatedResponse[ProductRead])
async def list_products(
    _: CurrentUser,
    service: Annotated[ProductService, Depends(get_service)],
    cat: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    products, total = await service.list_products(category_id=cat, search=search, page=page, page_size=page_size)
    pages = (total + page_size - 1) // page_size
    return PaginatedResponse(data=products, total=total, page=page, page_size=page_size, pages=pages)


@router.post("", response_model=ProductRead, status_code=201)
async def create_product(_: CurrentUser, data: ProductCreate, service: Annotated[ProductService, Depends(get_service)]):
    return await service.create_product(data)


@router.get("/{sku}", response_model=ProductRead)
async def get_product(_: CurrentUser, sku: str, service: Annotated[ProductService, Depends(get_service)]):
    return await service.get_product(sku)


@router.put("/{sku}", response_model=ProductRead)
async def update_product(_: CurrentUser, sku: str, data: ProductUpdate, service: Annotated[ProductService, Depends(get_service)]):
    return await service.update_product(sku, data)


@router.delete("/{sku}", response_model=MessageResponse)
async def delete_product(_: CurrentUser, sku: str, service: Annotated[ProductService, Depends(get_service)]):
    await service.delete_product(sku)
    return MessageResponse(message=f"Product '{sku}' deleted")


categories_router = APIRouter(prefix="/categories", tags=["products"])


def get_product_service(session: Annotated[AsyncSession, Depends(get_session)]) -> ProductService:
    return ProductService(ProductRepository(session))


@categories_router.get("", response_model=list[CategoryRead])
async def list_categories(_: CurrentUser, service: Annotated[ProductService, Depends(get_product_service)]):
    return await service.list_categories()


@categories_router.post("", response_model=CategoryRead, status_code=201)
async def create_category(_: CurrentUser, data: CategoryCreate, service: Annotated[ProductService, Depends(get_product_service)]):
    return await service.create_category(data)
