from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException, status, Depends

from app.models.sesion_caja import SesionCaja, AperturaCajaRequest, CierreCajaRequest
from app.models.caja import Caja
from app.models.venta import Venta, EstadoVenta
from app.routers.auth import obtener_usuario_actual
from app.models.usuario import Usuario

router = APIRouter(
    prefix="/cajas",
    tags=["Gestión de Cajas"]
)

# ==========================================
# ENDPOINT 1: ABRIR CAJA
# ==========================================
@router.post("/abrir", status_code=status.HTTP_201_CREATED)
async def abrir_caja(
    request: AperturaCajaRequest, 
    usuario_actual: Usuario = Depends(obtener_usuario_actual)
):
    """
    Inicia el turno de un cajero, bloqueando la caja para otros usuarios.
    """
    # 1. Verificar que la caja física exista
    caja = await Caja.find_one(Caja.codigo == request.caja_id, Caja.codigo_sucursal == request.sucursal_id)
    if not caja:
        raise HTTPException(status_code=404, detail="La caja especificada no existe en esta sucursal.")
        
    if not caja.activa:
        raise HTTPException(status_code=400, detail="Esta caja está inhabilitada por administración.")

    # 2. Verificar que la caja no esté ya en uso
    sesion_activa = await SesionCaja.find_one(SesionCaja.caja_id == request.caja_id, SesionCaja.estado == "ABIERTA")
    if sesion_activa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"La caja ya está abierta por el usuario {sesion_activa.usuario}."
        )

    # 3. Crear la nueva sesión
    nueva_sesion = SesionCaja(
        caja_id=request.caja_id,
        sucursal_id=request.sucursal_id,
        usuario=usuario_actual.username,
        monto_inicial=request.monto_inicial,
        estado="ABIERTA"
    )
    
    await nueva_sesion.insert()
    
    # 4. Bloquear la caja física
    caja.en_uso = True
    await caja.save()
    
    return {
        "mensaje": "Caja abierta exitosamente.",
        "sesion_id": str(nueva_sesion.id),
        "cajero": nueva_sesion.usuario,
        "monto_inicial": nueva_sesion.monto_inicial
    }

# ==========================================
# ENDPOINT 2: CERRAR CAJA (ARQUEO)
# ==========================================
@router.post("/{caja_id}/cerrar", status_code=status.HTTP_200_OK)
async def cerrar_caja(
    caja_id: str, 
    request: CierreCajaRequest, 
    usuario_actual: Usuario = Depends(obtener_usuario_actual)
):
    sesion = await SesionCaja.find_one(SesionCaja.caja_id == caja_id, SesionCaja.estado == "ABIERTA")
    if not sesion:
        raise HTTPException(status_code=404, detail="No hay ninguna sesión abierta.")

    # 1. Obtener TODAS las ventas del turno para el resumen
    ventas_turno = await Venta.find(
        Venta.caja_id == caja_id,
        Venta.estado != EstadoVenta.CANCELADA,
        Venta.fecha_registro >= sesion.fecha_apertura
    ).to_list()

    # Agrupar totales y cantidades por método de pago
    resumen_pagos = {
        "EFECTIVO": {"total": 0.0, "cantidad": 0},
        "QR": {"total": 0.0, "cantidad": 0},
        "TARJETA": {"total": 0.0, "cantidad": 0}
    }

    for v in ventas_turno:
        metodo = v.metodo_pago
        if metodo in resumen_pagos:
            resumen_pagos[metodo]["total"] += v.total_venta
            resumen_pagos[metodo]["cantidad"] += 1

    # Extraemos solo el total en efectivo para hacer las matemáticas de la gaveta
    total_ingresos_efectivo = resumen_pagos["EFECTIVO"]["total"]

    # 2. Calcular diferencias
    monto_calculado = sesion.monto_inicial + total_ingresos_efectivo
    diferencia = request.monto_cierre_real - monto_calculado
    
    # --- LÓGICA DE RECTIFICACIÓN ---
    # Si hay diferencia y el cajero aún no la ha confirmado explícitamente, detenemos el cierre.
    if diferencia != 0 and not request.confirmar_diferencia:
        return {
            "requiere_confirmacion": True,
            "mensaje": f"Descuadre detectado. Diferencia de Bs. {diferencia}. Por favor, vuelve a contar tu efectivo.",
            "diferencia": diferencia
        }

    # 3. Clausurar la sesión (Solo llega aquí si cuadra perfecto o si forzó el cierre)
    sesion.monto_cierre_calculado = monto_calculado
    sesion.monto_cierre_real = request.monto_cierre_real
    sesion.diferencia = diferencia
    sesion.estado = "CERRADA"
    sesion.fecha_cierre = datetime.now(ZoneInfo("America/La_Paz"))
    await sesion.save()
    
    # 4. Liberar la caja física
    caja = await Caja.find_one(Caja.codigo == caja_id)
    if caja:
        caja.en_uso = False
        await caja.save()
        
    return {
        "requiere_confirmacion": False,
        "mensaje": "Arqueo de caja realizado con éxito.",
        "monto_inicial": sesion.monto_inicial, # Nuevo: Necesario para el ticket
        "monto_calculado_sistema": sesion.monto_cierre_calculado,
        "monto_declarado_cajero": sesion.monto_cierre_real,
        "diferencia": sesion.diferencia,
        "cuadre": "PERFECTO" if sesion.diferencia == 0 else ("FALTANTE" if sesion.diferencia < 0 else "SOBRANTE"),
        "resumen_pagos": resumen_pagos # Nuevo: Enviamos el desglose al frontend
    }

# ==========================================
# ENDPOINT 3: VERIFICAR ESTADO (Útil para el Frontend)
# ==========================================
@router.get("/{caja_id}/estado", status_code=status.HTTP_200_OK)
async def verificar_estado_caja(caja_id: str):
    """
    Permite al frontend saber rápidamente si la caja está abierta o no.
    """
    sesion = await SesionCaja.find_one(SesionCaja.caja_id == caja_id, SesionCaja.estado == "ABIERTA")
    if sesion:
        return {"abierta": True, "usuario": sesion.usuario, "sucursal_id": sesion.sucursal_id}
    return {"abierta": False}