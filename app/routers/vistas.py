from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates

from app.models.usuario import Usuario
from .auth import obtener_usuario_admin

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

@router.get("/recepcion-oc")
async def vista_recepcion_oc(
    request: Request,
    # Mantenemos el guardia aquí solo como ejemplo de protección estricta a nivel API, 
    # pero recuerda que para vistas HTML con localStorage, la validación JS es la ideal.
    admin: Usuario = Depends(obtener_usuario_admin)
):
    return templates.TemplateResponse(
        request=request, 
        name="recepcion_oc.hbs",
        context={"mostrar_menu": True}
    )

@router.get("/crear-oc")
async def vista_crear_oc(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="crear_oc.hbs",
        context={"mostrar_menu": True}
    )

@router.get("/pagar-oc")
async def vista_pagar_oc(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="pagar_oc.hbs",
        context={"mostrar_menu": True}
    )

@router.get("/pos")
async def mostrar_pos(request: Request):
    """Renderiza la vista del Punto de Venta (POS)."""
    return templates.TemplateResponse(
        request=request, 
        name="pos.hbs",
        context={"mostrar_menu": True}
    )

@router.get("/ajuste-fisico")
async def vista_ajuste_fisico(request: Request):
    """Renderiza la pantalla de conteo físico y ajustes de inventario."""
    # Guardia retirado. La seguridad ahora recae en ajuste_fisico.js
    return templates.TemplateResponse(
        request=request, 
        name="ajuste_fisico.hbs",
        context={"mostrar_menu": True}
    )

@router.get("/articulos")
async def vista_articulos(request: Request):
    """Renderiza el gestor del catálogo de artículos."""
    return templates.TemplateResponse(
        request=request, 
        name="articulos.hbs",
        context={"mostrar_menu": True}
    )

@router.get("/traspasos")
async def vista_traspasos(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="traspasos.hbs", 
        context={"mostrar_menu": True}
    )

# ==========================================
# NUEVA RUTA: REPORTES DE VENTAS Y ANALÍTICA
# ==========================================
@router.get("/reportes")
async def vista_reportes(request: Request):
    """Renderiza el panel de reportes analíticos."""
    # La validación de seguridad (RBAC) se hará vía JS en el frontend
    return templates.TemplateResponse(
        request=request, 
        name="reportes.hbs",
        context={"mostrar_menu": True}
    )