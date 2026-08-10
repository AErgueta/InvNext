from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from datetime import datetime

from app.models.flujo import FlujoGobernanza, InstanciaTracking, PasoFlujo
from app.routers.auth import obtener_usuario_actual
from app.models.usuario import RolUsuario

router = APIRouter(
    prefix="/gobernanza",
    tags=["Flujos de Aprobación y Gobernanza"],
    dependencies=[Depends(obtener_usuario_actual)]
)

@router.post("/flujos", response_model=FlujoGobernanza, status_code=status.HTTP_201_CREATED)
async def crear_plantilla_flujo(
    flujo: FlujoGobernanza,
    usuario_actual = Depends(obtener_usuario_actual)
):
    """
    Crea una nueva plantilla de flujo de aprobación (Solo Administradores).
    """
    if usuario_actual.rol != RolUsuario.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Solo los administradores pueden crear plantillas de flujos."
        )
    
    existe = await FlujoGobernanza.find_one(FlujoGobernanza.codigo_flujo == flujo.codigo_flujo)
    if existe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El flujo con código '{flujo.codigo_flujo}' ya existe."
        )
    
    await flujo.insert()
    return flujo


@router.post("/instancias", response_model=InstanciaTracking, status_code=status.HTTP_201_CREATED)
async def iniciar_tracking(
    referencia_id: str,
    codigo_flujo: str,
    usuario_actual = Depends(obtener_usuario_actual)
):
    """
    Inicia dinámicamente una instancia de seguimiento para una operación (ej. movimiento u orden),
    copiando los pasos de la plantilla seleccionada por el usuario.
    """
    # 1. Buscamos la plantilla del flujo elegido
    plantilla = await FlujoGobernanza.find_one(FlujoGobernanza.codigo_flujo == codigo_flujo)
    if not plantilla or not plantilla.activo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El flujo '{codigo_flujo}' no existe o no está activo."
        )
    
    # 2. Verificamos que no exista ya un tracking activo para esta referencia
    existente = await InstanciaTracking.find_one(InstanciaTracking.referencia_id == referencia_id)
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta referencia ya cuenta con un proceso de tracking activo."
        )

    # 3. Creamos la instancia copiando los pasos de la plantilla
    nueva_instancia = InstanciaTracking(
        referencia_id=referencia_id,
        codigo_flujo=codigo_flujo,
        pasos_actuales=plantilla.pasos,
        indice_paso_actual=0,
        estado_general="EN_PROCESO"
    )
    
    await nueva_instancia.insert()
    return nueva_instancia


@router.patch("/instancias/{referencia_id}/avanzar", status_code=status.HTTP_200_OK)
async def aprobar_paso_tracking(
    referencia_id: str,
    usuario_actual = Depends(obtener_usuario_actual)
):
    """
    Aprueba el paso actual del flujo y avanza al siguiente, 
    validando que el usuario tenga el rol requerido para la etapa.
    """
    instancia = await InstanciaTracking.find_one(InstanciaTracking.referencia_id == referencia_id)
    if not instancia:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instancia de tracking no encontrada."
        )
    
    if instancia.estado_general != "EN_PROCESO":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La instancia ya se encuentra en estado: {instancia.estado_general}"
        )

    # Obtenemos el paso que está pendiente de aprobación
    indice = instancia.indice_paso_actual
    paso_actual = instancia.pasos_actuales[indice]

    # Validamos si el usuario actual cumple con el rol necesario para este paso
    if usuario_actual.rol != paso_actual.rol_requerido and usuario_actual.rol != RolUsuario.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Acceso denegado: Este paso requiere el rol '{paso_actual.rol_requerido}'."
        )

    # Marcamos el paso actual como completado
    paso_actual.completado = True
    paso_actual.fecha_aprobacion = datetime.now()
    paso_actual.aprobado_por = usuario_actual.username if hasattr(usuario_actual, 'username') else "Usuario Autorizado"

    # Verificamos si hay más pasos o si el flujo ha concluido
    if indice + 1 < len(instancia.pasos_actuales):
        instancia.indice_paso_actual += 1
    else:
        instancia.estado_general = "COMPLETADO"

    await instancia.save()
    return {
        "mensaje": f"Paso '{paso_actual.nombre_paso}' aprobado con éxito.",
        "estado_general": instancia.estado_general,
        "siguiente_paso_indice": instancia.indice_paso_actual
    }