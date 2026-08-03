from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import init_db

# Importamos nuestro nuevo enrutador
from app.routers import articulos, movimientos, lotes, reportes, proveedores, ordenes_compra

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

@app.get("/")
async def root():
    return {
        "status": "ok", 
        "sistema": "InvNext by NUMB",
        "mensaje": "La API está en línea y conectada a MongoDB Atlas"
    }

# Conectamos las rutas de artículos a la aplicación
app.include_router(articulos.router)
app.include_router(movimientos.router)
app.include_router(lotes.router)
app.include_router(reportes.router)
app.include_router(proveedores.router)
app.include_router(ordenes_compra.router)