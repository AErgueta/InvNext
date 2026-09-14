from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import init_db

# Importamos todos nuestros enrutadores (¡Agregamos 'vistas' al final!)
from app.routers import articulos, movimientos, lotes, reportes, proveedores, ordenes_compra, almacenes, auth, gobernanza, clientes, ventas, vistas, cajas

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield 

app = FastAPI(
    title="InvNext API by NUMB",
    description="API agnóstica para la gestión unificada de inventarios",
    version="0.1.0",
    lifespan=lifespan
)

# 1. Exponer la carpeta static (para que lea el CSS y JS del frontend)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def root():
    return {
        "status": "ok", 
        "sistema": "InvNext by NUMB",
        "mensaje": "La API está en línea y conectada a MongoDB Atlas"
    }

# 2. Conectamos las rutas de los módulos del Backend
app.include_router(articulos.router)
app.include_router(movimientos.router)
app.include_router(lotes.router)
app.include_router(reportes.router)
app.include_router(proveedores.router)
app.include_router(ordenes_compra.router)
app.include_router(almacenes.router)
app.include_router(auth.router)
app.include_router(gobernanza.router)
app.include_router(clientes.router)
app.include_router(ventas.router)

# 3. Conectamos las rutas del Frontend
app.include_router(vistas.router)
app.include_router(cajas.router)