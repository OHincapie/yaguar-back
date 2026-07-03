"""Seed inicial basado en el mock data del frontend."""
import asyncio

from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.customers.models import Customer, CustomerStatus, CustomerType
from src.domains.inventory.models import InventoryLevel
from src.domains.products.models import Category, Product
from src.domains.suppliers.models import Supplier, SupplierStatus
from src.shared.database import engine, init_db


async def seed(session: AsyncSession) -> None:
    categories = [
        Category(id="TEC", name="Tecnología", color="#3B82F6"),
        Category(id="HOG", name="Hogar", color="#10B981"),
        Category(id="HER", name="Herramientas", color="#F59E0B"),
        Category(id="LIM", name="Limpieza", color="#8B5CF6"),
        Category(id="BEB", name="Bebé", color="#EC4899"),
        Category(id="ALI", name="Alimentos", color="#EF4444"),
    ]
    for cat in categories:
        session.add(cat)

    suppliers = [
        Supplier(id="SUP-001", name="Andina Import", contact="Carlos Ríos", categories=["TEC", "HOG"], rating=4.8, lead_days=6, saldo=12400.0, status=SupplierStatus.AL_DIA, on_time_pct=96, orders_count=34),
        Supplier(id="SUP-002", name="TechDistrib", contact="Ana Gómez", categories=["TEC"], rating=4.5, lead_days=8, saldo=8200.0, status=SupplierStatus.PENDIENTE, on_time_pct=88, orders_count=21),
        Supplier(id="SUP-003", name="HogarPlus", contact="Luis Vera", categories=["HOG", "LIM"], rating=4.2, lead_days=4, saldo=3100.0, status=SupplierStatus.AL_DIA, on_time_pct=92, orders_count=18),
        Supplier(id="SUP-004", name="Herramax", contact="Sofía Paredes", categories=["HER"], rating=3.9, lead_days=10, saldo=15600.0, status=SupplierStatus.VENCIDO, on_time_pct=74, orders_count=12),
        Supplier(id="SUP-005", name="BabyCare", contact="Pedro Lara", categories=["BEB"], rating=4.6, lead_days=7, saldo=4400.0, status=SupplierStatus.AL_DIA, on_time_pct=94, orders_count=9),
        Supplier(id="SUP-006", name="FreshDist", contact="María Torres", categories=["ALI"], rating=4.3, lead_days=2, saldo=2100.0, status=SupplierStatus.AL_DIA, on_time_pct=98, orders_count=45),
    ]
    for sup in suppliers:
        session.add(sup)

    products = [
        Product(sku="TEC-1180", name="Audífonos BT Pulse X2", category_id="TEC", price=89.90, cost=52.00, supplier_id="SUP-001", unit="und"),
        Product(sku="TEC-2240", name="Cable USB-C 2m Braided", category_id="TEC", price=18.50, cost=8.20, supplier_id="SUP-002", unit="und"),
        Product(sku="TEC-3310", name="Cargador Inalámbrico 15W", category_id="TEC", price=45.00, cost=24.00, supplier_id="SUP-001", unit="und"),
        Product(sku="HOG-1050", name="Set Ollas Antiadherente x5", category_id="HOG", price=129.90, cost=72.00, supplier_id="SUP-003", unit="set"),
        Product(sku="HOG-2130", name="Licuadora Pro 1000W", category_id="HOG", price=95.00, cost=54.00, supplier_id="SUP-003", unit="und"),
        Product(sku="HER-1070", name="Taladro Inalámbrico 18V", category_id="HER", price=185.00, cost=108.00, supplier_id="SUP-004", unit="und"),
        Product(sku="HER-2020", name="Set Llaves Allen 9pz", category_id="HER", price=22.00, cost=11.00, supplier_id="SUP-004", unit="set"),
        Product(sku="LIM-1090", name="Detergente Industrial 5L", category_id="LIM", price=28.50, cost=14.00, supplier_id="SUP-003", unit="und"),
        Product(sku="LIM-2060", name="Desinfectante Multi 3L", category_id="LIM", price=19.90, cost=9.50, supplier_id="SUP-003", unit="und"),
        Product(sku="BEB-1030", name="Silla de Auto Grupo 1/2/3", category_id="BEB", price=245.00, cost=148.00, supplier_id="SUP-005", unit="und"),
        Product(sku="BEB-2010", name="Monitor Bebé Video HD", category_id="BEB", price=180.00, cost=105.00, supplier_id="SUP-005", unit="und"),
        Product(sku="ALI-1020", name="Aceite Vegetal x12 botl", category_id="ALI", price=85.00, cost=58.00, supplier_id="SUP-006", unit="pack"),
        Product(sku="ALI-2080", name="Arroz Premium 50kg", category_id="ALI", price=145.00, cost=98.00, supplier_id="SUP-006", unit="und"),
        Product(sku="TEC-4100", name="Hub USB 7 puertos 3.0", category_id="TEC", price=35.00, cost=18.00, supplier_id="SUP-002", unit="und"),
        Product(sku="HOG-3040", name="Cafetera Espresso 1200W", category_id="HOG", price=210.00, cost=128.00, supplier_id="SUP-003", unit="und"),
        Product(sku="HER-3015", name="Nivel Digital 40cm", category_id="HER", price=48.00, cost=27.00, supplier_id="SUP-004", unit="und"),
    ]
    for prod in products:
        session.add(prod)

    inventory_levels = [
        InventoryLevel(product_sku="TEC-1180", stock_qty=42, min_stock=15),
        InventoryLevel(product_sku="TEC-2240", stock_qty=8, min_stock=20),
        InventoryLevel(product_sku="TEC-3310", stock_qty=31, min_stock=10),
        InventoryLevel(product_sku="HOG-1050", stock_qty=5, min_stock=8),
        InventoryLevel(product_sku="HOG-2130", stock_qty=19, min_stock=10),
        InventoryLevel(product_sku="HER-1070", stock_qty=12, min_stock=5),
        InventoryLevel(product_sku="HER-2020", stock_qty=60, min_stock=20),
        InventoryLevel(product_sku="LIM-1090", stock_qty=3, min_stock=10),
        InventoryLevel(product_sku="LIM-2060", stock_qty=25, min_stock=15),
        InventoryLevel(product_sku="BEB-1030", stock_qty=7, min_stock=3),
        InventoryLevel(product_sku="BEB-2010", stock_qty=9, min_stock=4),
        InventoryLevel(product_sku="ALI-1020", stock_qty=48, min_stock=12),
        InventoryLevel(product_sku="ALI-2080", stock_qty=22, min_stock=10),
        InventoryLevel(product_sku="TEC-4100", stock_qty=35, min_stock=12),
        InventoryLevel(product_sku="HOG-3040", stock_qty=4, min_stock=5),
        InventoryLevel(product_sku="HER-3015", stock_qty=18, min_stock=8),
    ]
    for level in inventory_levels:
        session.add(level)

    customers = [
        Customer(id="CLI-001", name="Comercial Andrade", type=CustomerType.MAYORISTA, city="Lima", ltv=48200.0, orders=34, status=CustomerStatus.VIP, saldo=4280.0),
        Customer(id="CLI-002", name="Distribuidora Norte", type=CustomerType.MAYORISTA, city="Trujillo", ltv=31500.0, orders=22, status=CustomerStatus.ACTIVO, saldo=0.0),
        Customer(id="CLI-003", name="Minimarket Sol", type=CustomerType.MINORISTA, city="Lima", ltv=8400.0, orders=41, status=CustomerStatus.ACTIVO, saldo=620.0),
        Customer(id="CLI-004", name="Ferretería El Maestro", type=CustomerType.MINORISTA, city="Arequipa", ltv=15200.0, orders=18, status=CustomerStatus.RIESGO, saldo=2100.0),
        Customer(id="CLI-005", name="Supermercado Familia", type=CustomerType.MAYORISTA, city="Cusco", ltv=62000.0, orders=58, status=CustomerStatus.VIP, saldo=0.0),
        Customer(id="CLI-006", name="Bodega Central", type=CustomerType.MINORISTA, city="Iquitos", ltv=5100.0, orders=12, status=CustomerStatus.ACTIVO, saldo=480.0),
    ]
    for cust in customers:
        session.add(cust)

    await session.commit()
    print("✓ Seed completado")


async def main() -> None:
    await init_db()
    async with AsyncSession(engine) as session:
        await seed(session)


if __name__ == "__main__":
    asyncio.run(main())
