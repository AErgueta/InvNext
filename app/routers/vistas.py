from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

# Creamos el enrutador específico para las pantallas
router = APIRouter(prefix="/vistas", tags=["Vistas Frontend"])

# Le indicamos dónde están los archivos .hbs
templates = Jinja2Templates(directory="app/templates")
templates.env.cache = None

@router.get("/login")
async def render_login(request: Request):
    """Renderiza la pantalla de inicio de sesión sin el menú superior."""
    return templates.TemplateResponse(
        request=request, 
        name="login.hbs", 
        context={"mostrar_menu": False}
    )

@router.get("/kardex")
async def render_kardex(request: Request):
    """Renderiza la interfaz del Kardex."""
    return templates.TemplateResponse(
        request=request,
        name="kardex.hbs", 
        context={"mostrar_menu": True}
    )

@router.get("/alertas")
async def render_alertas(request: Request):
    """Renderiza el panel de alertas."""
    return templates.TemplateResponse(
        request=request,
        name="alertas.hbs", 
        context={"mostrar_menu": True}
    )

@router.get("/vencimientos")
async def render_vencimientos(request: Request):
    """Renderiza la pantalla de vencimientos."""
    return templates.TemplateResponse(
        request=request, 
        name="vencimientos.hbs",
        context={"mostrar_menu": True}
    )

@router.get("/dashboard")
async def render_dashboard(request: Request):
    """Renderiza el panel principal de indicadores."""
    return templates.TemplateResponse(
        request=request,
        name="dashboard.hbs", 
        context={"mostrar_menu": True}
    )