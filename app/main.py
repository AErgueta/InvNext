from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.database import init_db

# Importamos nuestros enrutadores
from app.routers import articulos, movimientos, lotes, reportes, proveedores, ordenes_compra, almacenes

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

# 1. Exponer la carpeta static (para que lea el archivo kardex.js)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 2. Configurar el motor de plantillas (Jinja2 procesará los archivos .hbs)
templates = Jinja2Templates(directory="app/templates")
templates.env.cache = None

@app.get("/")
async def root():
    return {
        "status": "ok", 
        "sistema": "InvNext by NUMB",
        "mensaje": "La API está en línea y conectada a MongoDB Atlas"
    }

# 3. Ruta para renderizar la vista de la interfaz del Kardex
@app.get("/kardex-view", tags=["Vistas"])
async def ver_pantalla_kardex(request: Request):
    """
    Renderiza la interfaz de usuario del Kardex basada en Handlebars/Jinja2.
    """
    # Usamos argumentos por nombre (kwargs) para compatibilidad con las nuevas versiones
    return templates.TemplateResponse(
        request=request,
        name="kardex.hbs", 
        context={"request": request}
    )

# Conectamos las rutas de los módulos a la aplicación
app.include_router(articulos.router)
app.include_router(movimientos.router)
app.include_router(lotes.router)
app.include_router(reportes.router)
app.include_router(proveedores.router)
app.include_router(ordenes_compra.router)
app.include_router(almacenes.router)