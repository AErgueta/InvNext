from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import uuid
from zoneinfo import ZoneInfo

from app.models.movimiento import Movimiento, TipoMovimiento
from app.models.traspaso import TraspasoInventario, EstadoTraspaso, DetalleTraspaso, RecepcionTraspasoReq
from app.routers.auth import obtener_usuario_actual

router = APIRouter(prefix="/traspasos", tags=["Traspasos de Inventario"])

# 1. Esquema que recibe los datos desde el frontend para CREAR (La pantalla)
class TraspasoCreate(BaseModel):
    almacen_origen_id: str
    almacen_destino_id: str
    articulos: List[dict]  
    recepcion_automatica: bool = False  
    notas: Optional[str] = None
    flujo_trabajo_seleccionado: str = "TRASPASO-INTERNO"  

@router.post("/", status_code=201)
async def crear_traspaso(
    payload: TraspasoCreate,
    usuario_actual = Depends(obtener_usuario_actual)
):
    if payload.almacen_origen_id == payload.almacen_destino_id:
        raise HTTPException(status_code=400, detail="El origen y destino no pueden ser el mismo.")

    # Generar un folio único y corto para la boleta
    folio_generado = f"TR-{uuid.uuid4().hex[:6].upper()}"

    # ==========================================
    # PASO A: DESCONTAR DEL ALMACÉN ORIGEN
    # ==========================================
    for art in payload.articulos:
        mov_salida = Movimiento(
            sku_articulo=art["sku_articulo"],
            codigo_almacen=payload.almacen_origen_id,
            numero_lote="N/A",  
            usuario=usuario_actual.username,
            tipo_movimiento=TipoMovimiento.SALIDA_TRASPASO,
            concepto=f"Envío a {payload.almacen_destino_id} (Boleta {folio_generado})",
            cantidad=art["cantidad"], 
            flujo_trabajo_seleccionado=payload.flujo_trabajo_seleccionado,
            almacen_contraparte=payload.almacen_destino_id,
            id_referencia=folio_generado,
            estado="APROBADO"
        )
        await mov_salida.insert()

    # Variables por defecto para el estado "En Tránsito"
    estado_actual = EstadoTraspaso.EN_TRANSITO
    fecha_recepcion = None
    usuario_recibe = None

    # ==========================================
    # PASO B: LÓGICA DE RECEPCIÓN AUTOMÁTICA
    # ==========================================
    if payload.recepcion_automatica:
        estado_actual = EstadoTraspaso.COMPLETADO
        fecha_recepcion = datetime.now(ZoneInfo("America/La_Paz"))
        usuario_recibe = usuario_actual.username 
        
        for art in payload.articulos:
            mov_entrada = Movimiento(
                sku_articulo=art["sku_articulo"],
                codigo_almacen=payload.almacen_destino_id,
                numero_lote="N/A",
                usuario=usuario_actual.username,
                tipo_movimiento=TipoMovimiento.ENTRADA_TRASPASO,
                concepto=f"Recepción automática desde {payload.almacen_origen_id} (Boleta {folio_generado})",
                cantidad=art["cantidad"],
                flujo_trabajo_seleccionado=payload.flujo_trabajo_seleccionado,
                almacen_contraparte=payload.almacen_origen_id,
                id_referencia=folio_generado,
                estado="APROBADO"
            )
            await mov_entrada.insert()

    # ==========================================
    # PASO C: GUARDAR LA BOLETA GLOBAL
    # ==========================================
    nuevo_traspaso = TraspasoInventario(
        folio=folio_generado,
        estado=estado_actual,
        almacen_origen_id=payload.almacen_origen_id,
        almacen_destino_id=payload.almacen_destino_id,
        usuario_envia=usuario_actual.username,
        usuario_recibe=usuario_recibe,
        fecha_recepcion=fecha_recepcion,
        articulos=payload.articulos,
        notas=payload.notas
    )
    
    await nuevo_traspaso.insert()
    
    return {
        "mensaje": "Traspaso registrado exitosamente",
        "folio": folio_generado,
        "estado": estado_actual,
        "recepcion_inmediata": payload.recepcion_automatica
    }


# ==========================================
# RUTAS DE CONSULTA Y RECEPCIÓN
# ==========================================

@router.get("/pendientes/{almacen_id}")
async def obtener_pendientes(almacen_id: str, usuario_actual = Depends(obtener_usuario_actual)):
    """
    Devuelve la lista de camiones/boletas que están en camino hacia este almacén.
    """
    pendientes = await TraspasoInventario.find(
        TraspasoInventario.almacen_destino_id == almacen_id,
        TraspasoInventario.estado == EstadoTraspaso.EN_TRANSITO
    ).to_list()
    
    return pendientes


@router.put("/{folio}/recibir")
async def recibir_traspaso(
    folio: str, 
    payload: RecepcionTraspasoReq, 
    usuario_actual = Depends(obtener_usuario_actual)
):
    # 1. Buscamos el traspaso en la base de datos
    traspaso = await TraspasoInventario.find_one(TraspasoInventario.folio == folio)
    if not traspaso:
        raise HTTPException(status_code=404, detail="Traspaso no encontrado")
        
    if traspaso.estado != EstadoTraspaso.EN_TRANSITO:
        raise HTTPException(status_code=400, detail="El traspaso no está en tránsito")

    # 2. Procesamos los artículos y detectamos discrepancias
    hubo_discrepancia = False
    historial_recepcion = []

    for item in payload.articulos_recibidos:
        if item.cantidad_recibida != item.cantidad_esperada:
            hubo_discrepancia = True
        
        historial_recepcion.append({
            "sku_articulo": item.sku_articulo,
            "cantidad_esperada": item.cantidad_esperada,
            "cantidad_recibida": item.cantidad_recibida,
            "observaciones": item.observaciones
        })

        # 3. ACTUALIZAR KARDEX (Destino)
        # Solo ingresamos stock si realmente llegó mercadería (cantidad_recibida > 0)
        if item.cantidad_recibida > 0:
            mov_entrada = Movimiento(
                sku_articulo=item.sku_articulo,
                codigo_almacen=traspaso.almacen_destino_id,
                numero_lote="N/A",
                usuario=usuario_actual.username,
                tipo_movimiento=TipoMovimiento.ENTRADA_TRASPASO,
                concepto=f"Recepción física desde {traspaso.almacen_origen_id} (Boleta {traspaso.folio})",
                cantidad=item.cantidad_recibida,  # Se registra solo lo que el usuario reportó que llegó
                flujo_trabajo_seleccionado=payload.flujo_trabajo_seleccionado,
                almacen_contraparte=traspaso.almacen_origen_id,
                id_referencia=folio,
                estado="APROBADO"
            )
            await mov_entrada.insert()

    # 4. Actualizamos el estado de la boleta
    nuevo_estado = EstadoTraspaso.COMPLETADO_CON_DISCREPANCIA if hubo_discrepancia else EstadoTraspaso.COMPLETADO
    
    traspaso.estado = nuevo_estado
    traspaso.usuario_recibe = usuario_actual.username
    traspaso.fecha_recepcion = datetime.now(ZoneInfo("America/La_Paz"))
    traspaso.detalle_recepcion = historial_recepcion

    await traspaso.save()

    return {
        "mensaje": "Recepción procesada exitosamente",
        "folio": traspaso.folio,
        "estado": traspaso.estado
    }