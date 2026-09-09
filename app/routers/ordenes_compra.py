from fastapi import APIRouter, status, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from zoneinfo import ZoneInfo

# 1. Importamos el guardia de seguridad
from app.routers.auth import obtener_usuario_actual

# Importamos nuestros modelos
from app.models.orden_compra import OrdenCompra, EstadoOrden, EstadoPago, ItemOrden
from app.models.articulo import Articulo, StockAlmacen
from app.models.movimiento import Movimiento, TipoMovimiento
from app.models.lote import Lote, StockLoteAlmacen

router = APIRouter(
    prefix="/ordenes-compra",
    tags=["Órdenes de Compra"]
)

# --- CLASES DE PETICIÓN (Limpias de usuarios "en duro") ---

class PeticionNuevaOrden(BaseModel):
    numero_orden: str
    proveedor_id: str
    items: List[ItemOrden]
    notas: Optional[str] = None

class ItemRecepcion(BaseModel):
    sku_articulo: str
    cantidad_a_recibir: float
    costo_unitario: float        # <--- AÑADIDO: El costo real de ingreso
    fecha_vencimiento: Optional[datetime] = None  # <--- Opcional con valor por defecto None

class PeticionRecepcion(BaseModel):
    codigo_almacen: str  # <--- Agregado para saber en qué sucursal ingresa la mercancía
    id_referencia: str 
    flujo_trabajo_seleccionado: str = Field(..., description="Flujo de trabajo de seguimiento obligatorio") 
    items_recibidos: List[ItemRecepcion]

class PeticionPago(BaseModel):
    monto: float = Field(..., gt=0, description="El pago debe ser estrictamente mayor a 0")
    metodo_pago: str  
    referencia: str   


# --- ENDPOINTS BLINDADOS CON DEPENDS ---

@router.post("/", response_model=OrdenCompra, status_code=status.HTTP_201_CREATED)
async def crear_orden_compra(
    peticion: PeticionNuevaOrden,
    usuario_actual = Depends(obtener_usuario_actual)
):
    """Crea una nueva Orden de Compra y calcula su total."""
    if not peticion.items:
        raise HTTPException(status_code=400, detail="La orden debe tener al menos un artículo.")

    # Cálculo automático del total financiero
    monto_calculado = sum(item.cantidad_solicitada * item.costo_unitario_estimado for item in peticion.items)
    
    # Instanciamos el modelo de Base de Datos inyectando al usuario real
    orden = OrdenCompra(
        numero_orden=peticion.numero_orden,
        proveedor_id=peticion.proveedor_id,
        items=peticion.items,
        notas=peticion.notas,
        monto_total=monto_calculado,
        usuario_creador=usuario_actual.username
    )
    
    try:
        await orden.insert()
    except Exception:
        raise HTTPException(status_code=400, detail="Error al crear la orden. Verifica duplicados.")
    
    return orden

@router.get("/", response_model=List[OrdenCompra])
async def listar_ordenes():
    """Devuelve todas las órdenes de compra registradas."""
    return await OrdenCompra.find_all().sort("-fecha_emision").to_list()


@router.post("/{numero_orden}/recibir", status_code=status.HTTP_200_OK)
async def recibir_orden(
    numero_orden: str, 
    peticion: PeticionRecepcion,
    usuario_actual = Depends(obtener_usuario_actual)
):
    """Recibe mercancía de una orden, soportando entregas parciales y asignación física a almacenes."""
    orden = await OrdenCompra.find_one(OrdenCompra.numero_orden == numero_orden)
    if not orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada.")
    
    if orden.estado == EstadoOrden.COMPLETADA:
        raise HTTPException(status_code=400, detail="Esta orden ya está completamente recibida.")

    movimientos_generados = []

    for item_recibido in peticion.items_recibidos:
        item_orden = next((i for i in orden.items if i.sku_articulo == item_recibido.sku_articulo), None)
        
        if not item_orden:
            raise HTTPException(status_code=400, detail=f"El artículo {item_recibido.sku_articulo} no pertenece a esta orden.")

        if item_orden.cantidad_recibida + item_recibido.cantidad_a_recibir > item_orden.cantidad_solicitada:
            raise HTTPException(status_code=400, detail=f"Intentas recibir más de lo solicitado para {item_recibido.sku_articulo}.")

        articulo = await Articulo.find_one(Articulo.sku == item_recibido.sku_articulo)
        if not articulo:
            continue

        numero_lote = None
        
        # 1. Gestión de Lotes y Asignación de Stock Físico
        if articulo.controla_lotes:
            timestamp = datetime.now(ZoneInfo("America/La_Paz")).strftime("%d%H%M")
            numero_lote = f"L-OC-{numero_orden}-{item_recibido.sku_articulo}-{timestamp}"
            
            nuevo_lote = Lote(
                sku_articulo=item_recibido.sku_articulo,
                numero_lote=numero_lote,
                cantidad_inicial=item_recibido.cantidad_a_recibir,
                cantidad_actual=item_recibido.cantidad_a_recibir,
                costo_unitario=item_recibido.costo_unitario,       # <--- ACTUALIZADO
                fecha_vencimiento=item_recibido.fecha_vencimiento, # <--- NUEVO
                stock_por_almacen=[StockLoteAlmacen(codigo_almacen=peticion.codigo_almacen, cantidad=item_recibido.cantidad_a_recibir)]
            )
            await nuevo_lote.insert()
        else:
            numero_lote = f"PERPETUO-{item_recibido.sku_articulo}"
            lote_existente = await Lote.find_one(Lote.numero_lote == numero_lote)
            
            if lote_existente:
                lote_existente.cantidad_inicial += item_recibido.cantidad_a_recibir
                lote_existente.cantidad_actual += item_recibido.cantidad_a_recibir
                
                stock_lote_alm = next((sl for sl in lote_existente.stock_por_almacen if sl.codigo_almacen == peticion.codigo_almacen), None)
                if stock_lote_alm:
                    stock_lote_alm.cantidad += item_recibido.cantidad_a_recibir
                else:
                    lote_existente.stock_por_almacen.append(StockLoteAlmacen(codigo_almacen=peticion.codigo_almacen, cantidad=item_recibido.cantidad_a_recibir))
                    
                await lote_existente.save()
            else:
                nuevo_lote_perpetuo = Lote(
                    sku_articulo=item_recibido.sku_articulo,
                    numero_lote=numero_lote,
                    cantidad_inicial=item_recibido.cantidad_a_recibir,
                    cantidad_actual=item_recibido.cantidad_a_recibir,
                    costo_unitario=item_recibido.costo_unitario,       # <--- ACTUALIZADO
                    fecha_vencimiento=item_recibido.fecha_vencimiento, # <--- NUEVO
                    stock_por_almacen=[StockLoteAlmacen(codigo_almacen=peticion.codigo_almacen, cantidad=item_recibido.cantidad_a_recibir)]
                )
                await nuevo_lote_perpetuo.insert()
        # 2. Actualizamos stock global y físico del artículo
        articulo.stock_actual += item_recibido.cantidad_a_recibir
        
        almacen_art = next((a for a in articulo.stock_por_almacen if a.codigo_almacen == peticion.codigo_almacen), None)
        if almacen_art:
            almacen_art.cantidad += item_recibido.cantidad_a_recibir
        else:
            articulo.stock_por_almacen.append(StockAlmacen(codigo_almacen=peticion.codigo_almacen, cantidad=item_recibido.cantidad_a_recibir))
            
        await articulo.save()

        # 3. Registramos el movimiento (IN) en el Kardex
        nuevo_movimiento = Movimiento(
            sku_articulo=item_recibido.sku_articulo,
            codigo_almacen=peticion.codigo_almacen, # <--- Se asigna el almacén de la petición
            numero_lote=numero_lote,
            usuario=usuario_actual.username,
            tipo_movimiento=TipoMovimiento.ENTRADA,
            concepto=f"Recepción de OC {numero_orden}",
            cantidad=item_recibido.cantidad_a_recibir,
            costo_unitario=item_recibido.costo_unitario, # <--- ACTUALIZADO
            id_referencia=peticion.id_referencia,
            flujo_trabajo_seleccionado=peticion.flujo_trabajo_seleccionado
        )
        await nuevo_movimiento.insert()
        movimientos_generados.append(nuevo_movimiento)

        item_orden.cantidad_recibida += item_recibido.cantidad_a_recibir

    todas_completadas = all(i.cantidad_recibida >= i.cantidad_solicitada for i in orden.items)
    
    if todas_completadas:
        orden.estado = EstadoOrden.COMPLETADA
    else:
        orden.estado = EstadoOrden.RECEPCION_PARCIAL

    # Sellamos la orden con el usuario que la recibió
    orden.usuario_ultimo_receptor = usuario_actual.username
    orden.fecha_actualizacion = datetime.now(ZoneInfo("America/La_Paz"))

    await orden.save()

    return {
        "mensaje": "Recepción procesada correctamente",
        "estado_actual_orden": orden.estado,
        "usuario_recepcion": orden.usuario_ultimo_receptor,
        "movimientos_creados": len(movimientos_generados)
    }


@router.post("/{numero_orden}/pagar", status_code=status.HTTP_200_OK)
async def registrar_pago(
    numero_orden: str, 
    peticion: PeticionPago,
    usuario_actual = Depends(obtener_usuario_actual)
):
    """
    Registra un pago a cuenta para una Orden de Compra.
    """
    orden = await OrdenCompra.find_one(OrdenCompra.numero_orden == numero_orden)
    if not orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada.")
    
    if orden.estado_pago == EstadoPago.PAGADO:
        raise HTTPException(status_code=400, detail="Esta orden ya se encuentra totalmente pagada.")

    saldo_pendiente = orden.monto_total - orden.monto_pagado
    if peticion.monto > saldo_pendiente:
        raise HTTPException(
            status_code=400, 
            detail=f"El pago excede la deuda. Saldo pendiente actual: {saldo_pendiente}"
        )

    orden.monto_pagado += peticion.monto

    if orden.monto_pagado >= orden.monto_total:
        orden.estado_pago = EstadoPago.PAGADO
    else:
        orden.estado_pago = EstadoPago.PAGO_PARCIAL

    # Sellamos la orden con el usuario que ejecutó el pago
    orden.usuario_ultimo_pagador = usuario_actual.username
    orden.fecha_actualizacion = datetime.now(ZoneInfo("America/La_Paz"))

    await orden.save()

    return {
        "mensaje": "Pago registrado con éxito",
        "estado_pago_actual": orden.estado_pago,
        "usuario_pago": orden.usuario_ultimo_pagador,
        "resumen_financiero": {
            "monto_total": orden.monto_total,
            "total_pagado": orden.monto_pagado,
            "saldo_pendiente": orden.monto_total - orden.monto_pagado
        },
        "detalles_ultimo_pago": {
            "monto": peticion.monto,
            "metodo": peticion.metodo_pago,
            "referencia": peticion.referencia
        }
    }