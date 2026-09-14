import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from dotenv import load_dotenv

# Importamos todos los modelos (Actualizado con Proveedor y OrdenCompra)
from app.models.articulo import Articulo
from app.models.movimiento import Movimiento
from app.models.lote import Lote
from app.models.proveedor import Proveedor
from app.models.orden_compra import OrdenCompra
from app.models.almacen import Almacen
from app.models.usuario import Usuario
from app.models.flujo import FlujoGobernanza, InstanciaTracking
from app.models.cliente import Cliente
from app.models.venta import Venta
from app.models.cuenta_corriente import CuentaCorriente
from app.models.sucursal import Sucursal
from app.models.caja import Caja
from app.models.sesion_caja import SesionCaja

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME")

async def init_db():
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]
    
    # Registramos NUESTROS 12 MODELOS en Beanie
    await init_beanie(
        database=db,
        document_models=[
            Articulo, 
            Movimiento, 
            Lote, 
            Proveedor,       # <-- Agregado
            OrdenCompra,     # <-- Agregado
            Almacen,
            Usuario,
            FlujoGobernanza,
            InstanciaTracking,
            Cliente,
            Venta,
            CuentaCorriente,
            Sucursal,
            Caja,
            SesionCaja
        ] 
    )
    print(f"Conexión exitosa a la base de datos: {DATABASE_NAME}")