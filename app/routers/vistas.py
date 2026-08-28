from fastapi import APIRouter, Request, Depends
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

from fastapi import Request

@router.get("/recepcion-oc")
async def vista_recepcion_oc(request: Request):
    # Nombramos explícitamente request y name para evitar confusiones de versión
    return templates.TemplateResponse(
        request=request, 
        name="recepcion_oc.hbs"
    )

@router.get("/crear-oc")
async def vista_crear_oc(request: Request):
    # Nombramos explícitamente request y name para evitar confusiones de versión
    return templates.TemplateResponse(
        request=request, 
        name="crear_oc.hbs"
    )

@router.get("/pagar-oc")
async def vista_pagar_oc(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="pagar_oc.hbs"
    )

@router.get("/pos")
async def mostrar_pos(request: Request):
    """
    Renderiza la vista del Punto de Venta (POS).
    """
    return templates.TemplateResponse(
        request=request, 
        name="pos.hbs"
    )