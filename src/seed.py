"""Seed inicial basado en el mock data del frontend.

Crea una empresa demo + usuario admin@yaguar.demo / admin123 y siembra su
catálogo. Pensado para una base de datos nueva (branch de Neon o local).
"""
import asyncio

import bcrypt
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.accounts.models import Company, CompanyRole, User, UserCompany
from src.domains.customers.models import Customer, CustomerStatus, CustomerType
from src.domains.inventory.models import InventoryLevel
from src.domains.products.models import Category, Product
from src.domains.suppliers.models import Supplier, SupplierStatus
from src.shared.database import engine, init_db


async def seed(session: AsyncSession) -> None:
    company = Company(name="Yaguar Demo", slug="yaguar-demo")
    session.add(company)
    await session.flush()

    user = User(
        email="admin@yaguar.demo",
        password_hash=bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode(),
        name="Admin Demo",
    )
    session.add(user)
    await session.flush()

    session.add(UserCompany(user_id=user.id, company_id=company.id, role=CompanyRole.OWNER))

    categories = {
        code: Category(company_id=company.id, code=code, name=name, color=color)
        for code, name, color in [
            ("TEC", "Tecnología", "#3B82F6"),
            ("HOG", "Hogar", "#10B981"),
            ("HER", "Herramientas", "#F59E0B"),
            ("LIM", "Limpieza", "#8B5CF6"),
            ("BEB", "Bebé", "#EC4899"),
            ("ALI", "Alimentos", "#EF4444"),
        ]
    }
    for cat in categories.values():
        session.add(cat)

    suppliers = {
        code: Supplier(
            company_id=company.id, code=code, name=name, contact=contact, categories=cats,
            rating=rating, lead_days=lead_days, saldo=saldo, status=status, on_time_pct=on_time, orders_count=orders,
        )
        for code, name, contact, cats, rating, lead_days, saldo, status, on_time, orders in [
            ("SUP-001", "Andina Import", "Carlos Ríos", ["TEC", "HOG"], 4.8, 6, 12400.0, SupplierStatus.AL_DIA, 96, 34),
            ("SUP-002", "TechDistrib", "Ana Gómez", ["TEC"], 4.5, 8, 8200.0, SupplierStatus.PENDIENTE, 88, 21),
            ("SUP-003", "HogarPlus", "Luis Vera", ["HOG", "LIM"], 4.2, 4, 3100.0, SupplierStatus.AL_DIA, 92, 18),
            ("SUP-004", "Herramax", "Sofía Paredes", ["HER"], 3.9, 10, 15600.0, SupplierStatus.VENCIDO, 74, 12),
            ("SUP-005", "BabyCare", "Pedro Lara", ["BEB"], 4.6, 7, 4400.0, SupplierStatus.AL_DIA, 94, 9),
            ("SUP-006", "FreshDist", "María Torres", ["ALI"], 4.3, 2, 2100.0, SupplierStatus.AL_DIA, 98, 45),
        ]
    }
    for sup in suppliers.values():
        session.add(sup)
    await session.flush()

    products_data = [
        ("TEC-1180", "Audífonos BT Pulse X2", "TEC", 89.90, 52.00, "SUP-001", "und", 42, 15),
        ("TEC-2240", "Cable USB-C 2m Braided", "TEC", 18.50, 8.20, "SUP-002", "und", 8, 20),
        ("TEC-3310", "Cargador Inalámbrico 15W", "TEC", 45.00, 24.00, "SUP-001", "und", 31, 10),
        ("HOG-1050", "Set Ollas Antiadherente x5", "HOG", 129.90, 72.00, "SUP-003", "set", 5, 8),
        ("HOG-2130", "Licuadora Pro 1000W", "HOG", 95.00, 54.00, "SUP-003", "und", 19, 10),
        ("HER-1070", "Taladro Inalámbrico 18V", "HER", 185.00, 108.00, "SUP-004", "und", 12, 5),
        ("HER-2020", "Set Llaves Allen 9pz", "HER", 22.00, 11.00, "SUP-004", "set", 60, 20),
        ("LIM-1090", "Detergente Industrial 5L", "LIM", 28.50, 14.00, "SUP-003", "und", 3, 10),
        ("LIM-2060", "Desinfectante Multi 3L", "LIM", 19.90, 9.50, "SUP-003", "und", 25, 15),
        ("BEB-1030", "Silla de Auto Grupo 1/2/3", "BEB", 245.00, 148.00, "SUP-005", "und", 7, 3),
        ("BEB-2010", "Monitor Bebé Video HD", "BEB", 180.00, 105.00, "SUP-005", "und", 9, 4),
        ("ALI-1020", "Aceite Vegetal x12 botl", "ALI", 85.00, 58.00, "SUP-006", "pack", 48, 12),
        ("ALI-2080", "Arroz Premium 50kg", "ALI", 145.00, 98.00, "SUP-006", "und", 22, 10),
        ("TEC-4100", "Hub USB 7 puertos 3.0", "TEC", 35.00, 18.00, "SUP-002", "und", 35, 12),
        ("HOG-3040", "Cafetera Espresso 1200W", "HOG", 210.00, 128.00, "SUP-003", "und", 4, 5),
        ("HER-3015", "Nivel Digital 40cm", "HER", 48.00, 27.00, "SUP-004", "und", 18, 8),
    ]
    for sku, name, cat_code, price, cost, sup_code, unit, stock, min_stock in products_data:
        product = Product(
            company_id=company.id,
            sku=sku,
            name=name,
            category_id=categories[cat_code].id,
            price=price,
            cost=cost,
            supplier_id=suppliers[sup_code].id,
            unit=unit,
        )
        session.add(product)
        await session.flush()
        session.add(InventoryLevel(company_id=company.id, product_id=product.id, stock_qty=stock, min_stock=min_stock))

    customers = [
        ("CLI-001", "Comercial Andrade", CustomerType.MAYORISTA, "Lima", 48200.0, 34, CustomerStatus.VIP, 4280.0),
        ("CLI-002", "Distribuidora Norte", CustomerType.MAYORISTA, "Trujillo", 31500.0, 22, CustomerStatus.ACTIVO, 0.0),
        ("CLI-003", "Minimarket Sol", CustomerType.MINORISTA, "Lima", 8400.0, 41, CustomerStatus.ACTIVO, 620.0),
        ("CLI-004", "Ferretería El Maestro", CustomerType.MINORISTA, "Arequipa", 15200.0, 18, CustomerStatus.RIESGO, 2100.0),
        ("CLI-005", "Supermercado Familia", CustomerType.MAYORISTA, "Cusco", 62000.0, 58, CustomerStatus.VIP, 0.0),
        ("CLI-006", "Bodega Central", CustomerType.MINORISTA, "Iquitos", 5100.0, 12, CustomerStatus.ACTIVO, 480.0),
    ]
    for code, name, ctype, city, ltv, orders, status, saldo in customers:
        session.add(Customer(company_id=company.id, code=code, name=name, type=ctype, city=city, ltv=ltv, orders=orders, status=status, saldo=saldo))

    await session.commit()
    print(f"✓ Seed completado — empresa '{company.name}' ({company.id}), login admin@yaguar.demo / admin123")


async def main() -> None:
    await init_db()
    async with AsyncSession(engine) as session:
        await seed(session)


if __name__ == "__main__":
    asyncio.run(main())
