from fastapi import APIRouter, status, HTTPException
from typing import List
from pydantic import BaseModel, Field
from datetime import datetime
from zoneinfo import ZoneInfo

# Importamos nuestros modelos
from app.models.orden_compra import OrdenCompra, EstadoOrden, EstadoPago
from app.models.articulo import Articulo
from app.models.movimiento import Movimiento, TipoMovimiento
from app.models.lote import Lote

router = APIRouter(
    prefix="/ordenes-compra",
    tags=["Órdenes de Compra"]
)

# --- CLASES PARA LA RECEPCIÓN ---
class ItemRecepcion(BaseModel):
    sku_articulo: str
    cantidad_a_recibir: float

class PeticionRecepcion(BaseModel):
    usuario: str
    id_referencia: str  # Número de factura o remito
    items_recibidos: List[ItemRecepcion]

class PeticionPago(BaseModel):
    # gt=0 significa "Greater Than" (Mayor que) 0
    monto: float = Field(..., gt=0, description="El pago debe ser estrictamente mayor a 0")
    metodo_pago: str  # Ej: "Transferencia", "Efectivo", "Cheque"
    referencia: str   # Ej: Número de comprobante o voucher


# --- ENDPOINTS BÁSICOS ---
@router.post("/", response_model=OrdenCompra, status_code=status.HTTP_201_CREATED)
async def crear_orden_compra(orden: OrdenCompra):
    """Crea una nueva Orden de Compra y calcula su total."""
    if not orden.items:
        raise HTTPException(status_code=400, detail="La orden debe tener al menos un artículo.")

    # Cálculo automático del total financiero
    monto_calculado = sum(item.cantidad_solicitada * item.costo_unitario_estimado for item in orden.items)
    orden.monto_total = monto_calculado
    
    try:
        await orden.insert()
    except Exception:
        raise HTTPException(status_code=400, detail="Error al crear la orden. Verifica duplicados.")
    
    return orden

@router.get("/", response_model=List[OrdenCompra])
async def listar_ordenes():
    """Devuelve todas las órdenes de compra registradas."""
    return await OrdenCompra.find_all().sort("-fecha_emision").to_list()


# --- EL ENDPOINT INTELIGENTE DE RECEPCIÓN ---
@router.post("/{numero_orden}/recibir", status_code=status.HTTP_200_OK)
async def recibir_orden(numero_orden: str, peticion: PeticionRecepcion):
    """Recibe mercancía de una orden, soportando entregas parciales."""
    orden = await OrdenCompra.find_one(OrdenCompra.numero_orden == numero_orden)
    if not orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada.")
    
    if orden.estado == EstadoOrden.COMPLETADA:
        raise HTTPException(status_code=400, detail="Esta orden ya está completamente recibida.")

    movimientos_generados = []

    # 1. Procesamos lo que viene en el camión
    for item_recibido in peticion.items_recibidos:
        # Buscamos este artículo dentro de la orden original
        item_orden = next((i for i in orden.items if i.sku_articulo == item_recibido.sku_articulo), None)
        
        if not item_orden:
            raise HTTPException(status_code=400, detail=f"El artículo {item_recibido.sku_articulo} no pertenece a esta orden.")

        if item_orden.cantidad_recibida + item_recibido.cantidad_a_recibir > item_orden.cantidad_solicitada:
            raise HTTPException(status_code=400, detail=f"Intentas recibir más de lo solicitado para {item_recibido.sku_articulo}.")

        articulo = await Articulo.find_one(Articulo.sku == item_recibido.sku_articulo)
        if not articulo:
            continue

        # 2. Gestión de Lotes (Dinámicos vs Perpetuos)
        numero_lote = None
        
        if articulo.controla_lotes:
            # LOTE DINÁMICO: Uno nuevo por cada recepción
            timestamp = datetime.now(ZoneInfo("America/La_Paz")).strftime("%d%H%M")
            numero_lote = f"L-OC-{numero_orden}-{timestamp}"
            
            nuevo_lote = Lote(
                sku_articulo=item_recibido.sku_articulo,
                numero_lote=numero_lote,
                cantidad_inicial=item_recibido.cantidad_a_recibir,
                cantidad_actual=item_recibido.cantidad_a_recibir,
                costo_unitario=item_orden.costo_unitario_estimado
            )
            await nuevo_lote.insert()
        else:
            # LOTE PERPETUO: Acumulamos en un solo lote maestro
            numero_lote = f"PERPETUO-{item_recibido.sku_articulo}"
            lote_existente = await Lote.find_one(Lote.numero_lote == numero_lote)
            
            if lote_existente:
                # Si ya existe, le sumamos el nuevo ingreso al stock del lote
                lote_existente.cantidad_inicial += item_recibido.cantidad_a_recibir
                lote_existente.cantidad_actual += item_recibido.cantidad_a_recibir
                await lote_existente.save()
            else:
                # Si es el primer ingreso histórico de este artículo, lo creamos
                nuevo_lote_perpetuo = Lote(
                    sku_articulo=item_recibido.sku_articulo,
                    numero_lote=numero_lote,
                    cantidad_inicial=item_recibido.cantidad_a_recibir,
                    cantidad_actual=item_recibido.cantidad_a_recibir,
                    costo_unitario=item_orden.costo_unitario_estimado
                )
                await nuevo_lote_perpetuo.insert()

        # 3. Actualizamos stock global
        articulo.stock_actual += item_recibido.cantidad_a_recibir
        await articulo.save()

        # 4. Registramos el movimiento (IN) en el Kardex
        nuevo_movimiento = Movimiento(
            sku_articulo=item_recibido.sku_articulo,
            numero_lote=numero_lote,
            usuario=peticion.usuario,
            tipo_movimiento=TipoMovimiento.ENTRADA,
            concepto=f"Recepción de OC {numero_orden}",
            cantidad=item_recibido.cantidad_a_recibir,
            costo_unitario=item_orden.costo_unitario_estimado,
            id_referencia=peticion.id_referencia
        )
        await nuevo_movimiento.insert()
        movimientos_generados.append(nuevo_movimiento)

        # 5. "Memoria": Sumamos lo que acaba de llegar a la orden
        item_orden.cantidad_recibida += item_recibido.cantidad_a_recibir

    # 6. Lógica inteligente para cambiar el estado de la Orden
    todas_completadas = all(i.cantidad_recibida >= i.cantidad_solicitada for i in orden.items)
    
    if todas_completadas:
        orden.estado = EstadoOrden.COMPLETADA
    else:
        orden.estado = EstadoOrden.RECEPCION_PARCIAL

    await orden.save()

    return {
        "mensaje": "Recepción procesada correctamente",
        "estado_actual_orden": orden.estado,
        "movimientos_creados": len(movimientos_generados)
    }


@router.post("/{numero_orden}/pagar", status_code=status.HTTP_200_OK)
async def registrar_pago(numero_orden: str, peticion: PeticionPago):
    """
    Registra un pago a cuenta para una Orden de Compra:
    1. Suma el monto pagado.
    2. Valida que no se pague más del total.
    3. Cambia el estado financiero (PAGO_PARCIAL o PAGADO).
    """
    # 1. Buscamos la orden
    orden = await OrdenCompra.find_one(OrdenCompra.numero_orden == numero_orden)
    if not orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada.")
    
    if orden.estado_pago == EstadoPago.PAGADO:
        raise HTTPException(status_code=400, detail="Esta orden ya se encuentra totalmente pagada.")

    # 2. Protección contra errores de tipeo (sobrepago)
    saldo_pendiente = orden.monto_total - orden.monto_pagado
    if peticion.monto > saldo_pendiente:
        raise HTTPException(
            status_code=400, 
            detail=f"El pago excede la deuda. Saldo pendiente actual: {saldo_pendiente}"
        )

    # 3. Sumamos el dinero a la orden
    orden.monto_pagado += peticion.monto

    # 4. Lógica inteligente para el estado financiero
    if orden.monto_pagado >= orden.monto_total:
        orden.estado_pago = EstadoPago.PAGADO
    else:
        orden.estado_pago = EstadoPago.PAGO_PARCIAL

    await orden.save()

    # Devolvemos un resumen financiero súper claro
    return {
        "mensaje": "Pago registrado con éxito",
        "estado_pago_actual": orden.estado_pago,
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