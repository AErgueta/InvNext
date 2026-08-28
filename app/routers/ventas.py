import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from beanie import PydanticObjectId

from app.models.venta import Venta, DetalleVenta, EstadoVenta, CondicionPago
from app.models.movimiento import Movimiento, TipoMovimiento

from app.routers.auth import obtener_usuario_actual
from app.models.usuario import Usuario

from app.models.lote import Lote
from app.models.articulo import Articulo
from app.models.cuenta_corriente import CuentaCorriente, TipoTransaccionCxC

router = APIRouter(
    prefix="/ventas",
    tags=["Ventas y Facturación"]
)

# ==========================================
# ESQUEMAS DE ENTRADA (PAYLOAD DEL FRONTEND)
# ==========================================
class NuevaVentaRequest(BaseModel):
    cliente: str
    documento_cliente: Optional[str] = None
    almacen_origen: str  
    flujo_trabajo_seleccionado: str 
    articulos: List[DetalleVenta]
    descuento_global: float = 0.0
    condicion_pago: CondicionPago = CondicionPago.CONTADO

class AnularVentaRequest(BaseModel):
    flujo_trabajo_seleccionado: str 

class PagoRequest(BaseModel):
    monto: float
    concepto: str = "Pago en caja"    

# ==========================================
# ENDPOINT 1: CREAR VENTA (Logística Pendiente, Deuda Inicial)
# ==========================================
@router.post("/", status_code=status.HTTP_201_CREATED)
async def registrar_venta(
    request: NuevaVentaRequest,
    usuario_actual: Usuario = Depends(obtener_usuario_actual)
):
    """
    Recibe un carrito de compras, valida las matemáticas, genera el documento de Venta
    y dispara los movimientos de salida en estado PENDIENTE.
    """
    # 1. Auditoría Matemática
    subtotal_calculado = 0.0
    for art in request.articulos:
        calc_esperado = (art.cantidad * art.precio_unitario) - art.descuento_linea
        if round(calc_esperado, 2) != round(art.subtotal_linea, 2):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Inconsistencia matemática en el SKU {art.sku_articulo}. Se esperaba {calc_esperado}, pero enviaron {art.subtotal_linea}."
            )
        subtotal_calculado += calc_esperado
        
    total_calculado = subtotal_calculado - request.descuento_global
    
    # 2. Generar Folio
    folio_generado = f"VEN-{uuid.uuid4().hex[:6].upper()}"
    
    # 3. PREPARAR LA VENTA EN MEMORIA 
    nueva_venta = Venta(
        folio=folio_generado,
        cliente=request.cliente,
        documento_cliente=request.documento_cliente,
        condicion_pago=request.condicion_pago,          
        articulos=request.articulos,
        subtotal_venta=subtotal_calculado,
        descuento_global=request.descuento_global,
        total_venta=total_calculado,
        saldo_pendiente=total_calculado,                
        estado=EstadoVenta.PENDIENTE
    )
    
    # 4. PREPARAR LOS MOVIMIENTOS EN MEMORIA 
    movimientos_a_guardar = []
    for art in request.articulos:
        nuevo_movimiento = Movimiento(
            sku_articulo=art.sku_articulo,
            codigo_almacen=request.almacen_origen,
            numero_lote="LOTE-POR-ASIGNAR", 
            usuario=usuario_actual.username, 
            tipo_movimiento=TipoMovimiento.SALIDA_VENTA,
            cantidad=art.cantidad,
            costo_unitario=0.0,  
            concepto=f"Despacho por venta folio {folio_generado}",
            flujo_trabajo_seleccionado=request.flujo_trabajo_seleccionado,
            estado="PENDIENTE" # Candado inicial asegurado
        )
        movimientos_a_guardar.append(nuevo_movimiento)
        
    # 5. ZONA SEGURA: ESCRITURA
    await nueva_venta.insert()
    
    ids_movimientos = []
    for mov in movimientos_a_guardar:
        await mov.insert()
        ids_movimientos.append(str(mov.id))
        
    if ids_movimientos:
        #await nueva_venta.update({"$set": {"referencia_movimiento_id": ",".join(ids_movimientos)}})
        await nueva_venta.update({"$set": {"referencia_movimiento_id": ids_movimientos}})
        
    return {
        "mensaje": "Orden de venta registrada exitosamente.",
        "folio": nueva_venta.folio,
        "venta_id": str(nueva_venta.id),
        "condicion_pago": nueva_venta.condicion_pago,   
        "total_a_cobrar": total_calculado,
        "movimientos_generados": ids_movimientos
    }    

# ==========================================
# ENDPOINT 2: DESPACHAR MERCADERÍA (Logística Pura + Cargo CxC)
# ==========================================
@router.put("/{venta_id}/despachar", status_code=status.HTTP_200_OK)
async def despachar_venta(
    venta_id: str,
    usuario_actual = Depends(obtener_usuario_actual)
):
    """
    Despacha la mercadería usando lógica FIFO.
    Búsqueda quirúrgica por IDs y protección de estados financieros.
    """
    try:
        id_obj = PydanticObjectId(venta_id)
    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Formato de ID inválido.")
        
    venta = await Venta.get(id_obj)
    if not venta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada.")
        
    if not venta.referencia_movimiento_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Esta venta no tiene movimientos logísticos asociados."
        )

    # 0. BÚSQUEDA INFALIBLE DE MOVIMIENTOS POR ID (Nativo de MongoDB)
    #----------------------
    if isinstance(venta.referencia_movimiento_id, list):
        ids_strings = venta.referencia_movimiento_id
    else:
        ids_strings = [id_str.strip() for id_str in venta.referencia_movimiento_id.split(",") if id_str.strip()]
        
    ids_objetos = [PydanticObjectId(id_str) for id_str in ids_strings]
    #----------------------

    movimientos_venta = await Movimiento.find({"_id": {"$in": ids_objetos}}).to_list()
    
    if not movimientos_venta:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Error interno: No se encontraron movimientos físicos en la base de datos para los IDs."
        )
    
    # Filtramos para asegurarnos de no despachar dos veces lo mismo
    movimientos_pendientes = [mov for mov in movimientos_venta if getattr(mov, "estado", "PENDIENTE") != "EJECUTADO"]
    
    if not movimientos_pendientes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="¡La mercadería de esta venta YA FUE DESPACHADA anteriormente! (Sus movimientos están en estado EJECUTADO)."
        )

    # 1. PREPARACIÓN EN MEMORIA (Lógica FIFO Logística)
    lotes_a_guardar = []
    articulos_a_guardar = []
    
    for mov in movimientos_pendientes:
        articulo = await Articulo.find_one(Articulo.sku == mov.sku_articulo)
        if not articulo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Artículo {mov.sku_articulo} no encontrado.")
            
        lotes_disponibles = await Lote.find(
            Lote.sku_articulo == mov.sku_articulo,
            Lote.cantidad_actual > 0
        ).sort("+fecha_vencimiento").to_list()
        
        cantidad_restante = mov.cantidad
        lotes_utilizados = []
        costo_total_lotes = 0.0  # <--- 1. NUEVO: Variable para acumular el valor financiero
        
        for lote in lotes_disponibles:
            if cantidad_restante <= 0:
                break
                
            stock_lote_alm = next((sl for sl in lote.stock_por_almacen if sl.codigo_almacen == mov.codigo_almacen), None)
            
            if stock_lote_alm and stock_lote_alm.cantidad > 0:
                cantidad_a_tomar = min(stock_lote_alm.cantidad, cantidad_restante)
                
                # <--- 2. NUEVO: Acumulamos el costo de las piezas que estamos sacando de este lote específico
                costo_total_lotes += cantidad_a_tomar * lote.costo_unitario 
                
                lote.cantidad_actual -= cantidad_a_tomar
                stock_lote_alm.cantidad -= cantidad_a_tomar
                lotes_a_guardar.append(lote)
                
                lotes_utilizados.append(lote.numero_lote)
                cantidad_restante -= cantidad_a_tomar
                
        if cantidad_restante > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Inventario insuficiente para el SKU {mov.sku_articulo}. Faltan {cantidad_restante} unidades en el almacén {mov.codigo_almacen}."
            )
                
        stock_almacen = next((alm for alm in articulo.stock_por_almacen if alm.codigo_almacen == mov.codigo_almacen), None)
        if stock_almacen:
            stock_almacen.cantidad -= mov.cantidad
            
        articulo.stock_actual -= mov.cantidad
        articulos_a_guardar.append(articulo)
        
        mov.numero_lote = ", ".join(lotes_utilizados) if lotes_utilizados else "SIN-LOTE"
        mov.estado = "EJECUTADO"
        
        # <--- 3. NUEVO: Asignamos el costo unitario real calculado al movimiento
        mov.costo_unitario = costo_total_lotes / mov.cantidad

    # 2. PREPARACIÓN FINANCIERA (Cuentas por Cobrar)
    cargo_cxc = None
    
    if venta.condicion_pago != CondicionPago.CONTADO:
        cargo_cxc = CuentaCorriente(
            documento_cliente=venta.documento_cliente or "CF",
            cliente=venta.cliente,
            venta_id=str(venta.id),
            folio_venta=venta.folio,
            tipo=TipoTransaccionCxC.CARGO,
            monto=venta.total_venta,
            concepto=f"Despacho a crédito ({venta.condicion_pago.value})",
            usuario=usuario_actual.username
        )
        
        if venta.estado == EstadoVenta.PENDIENTE:
            venta.estado = EstadoVenta.POR_COBRAR
    else:
    # --- NUEVO: Si es AL CONTADO, la venta pasa a pagada ---
        if venta.estado == EstadoVenta.PENDIENTE:
            venta.estado = EstadoVenta.PAGADA
        
    # 3. ZONA SEGURA: ESCRITURA EN BASE DE DATOS
    await venta.save()
    
    for articulo in articulos_a_guardar:
        await articulo.save()
        for lote in lotes_a_guardar:
            await lote.save()
    for mov in movimientos_pendientes:
        await mov.save()
        
    if cargo_cxc:
        await cargo_cxc.insert()
        
    return {
        "mensaje": f"Mercadería despachada correctamente.",
        "folio": venta.folio,
        "estado_actual": venta.estado,
        "cargo_generado_cxc": True if cargo_cxc else False
    }

# ==========================================
# ENDPOINT 3: PAGAR / ABONAR (Finanzas Puras)
# ==========================================
@router.put("/{venta_id}/pagar", status_code=status.HTTP_200_OK)
async def registrar_pago_venta(
    venta_id: str,
    pago: PagoRequest,
    usuario_actual = Depends(obtener_usuario_actual)
):
    """
    Registra un pago (Abono) a una venta.
    Actualiza el saldo pendiente y cambia el estado financiero.
    ¡No toca inventarios!
    """
    try:
        id_obj = PydanticObjectId(venta_id)
    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Formato de ID inválido.")
        
    venta = await Venta.get(id_obj)
    if not venta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada.")
        
    # Validaciones financieras
    if venta.estado in [EstadoVenta.PAGADA, EstadoVenta.CANCELADA]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"La venta ya está {venta.estado.value}.")
        
    if pago.monto <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El monto a pagar debe ser mayor a cero.")
        
    if pago.monto > venta.saldo_pendiente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"El abono ({pago.monto}) supera el saldo pendiente actual ({venta.saldo_pendiente})."
        )
        
    # Registrar el ABONO en la Cuenta Corriente
    nuevo_abono = CuentaCorriente(
        documento_cliente=venta.documento_cliente or "CF",
        cliente=venta.cliente,
        venta_id=str(venta.id),
        folio_venta=venta.folio,
        tipo=TipoTransaccionCxC.ABONO,
        monto=pago.monto,
        concepto=pago.concepto,
        usuario=usuario_actual.username
    )
    
    # Actualizar la Venta
    venta.saldo_pendiente -= pago.monto
    
    if venta.saldo_pendiente == 0:
        venta.estado = EstadoVenta.PAGADA
    else:
        venta.estado = EstadoVenta.PAGO_PARCIAL
        
    # Guardar en Base de Datos
    await nuevo_abono.insert()
    await venta.save()
    
    return {
        "mensaje": "Pago registrado exitosamente.",
        "folio": venta.folio,
        "monto_abonado": pago.monto,
        "saldo_restante": venta.saldo_pendiente,
        "nuevo_estado": venta.estado
    }

# ==========================================
# ENDPOINT 4: ANULAR VENTA
# ==========================================
@router.put("/{venta_id}/anular", status_code=status.HTTP_200_OK)
async def anular_venta(
    venta_id: str, 
    request: AnularVentaRequest,
    usuario_actual: Usuario = Depends(obtener_usuario_actual)
):
    """
    Anula una orden de venta.
    """
    try:
        id_obj = PydanticObjectId(venta_id)
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Formato de ID de venta inválido."
        )
        
    venta = await Venta.get(id_obj)
    
    if not venta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró la venta solicitada."
        )
        
    if venta.estado == EstadoVenta.CANCELADA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta venta ya se encuentra anulada."
        )
        
    venta.estado = EstadoVenta.CANCELADA
    await venta.save()
    
    # Buscar usando sintaxis nativa de MongoDB para evitar falsos positivos
    if isinstance(venta.referencia_movimiento_id, list):
        ids_strings = venta.referencia_movimiento_id
    else:
        ids_strings = [id_str.strip() for id_str in venta.referencia_movimiento_id.split(",") if id_str.strip()]
        
    ids_objetos = [PydanticObjectId(id_str) for id_str in ids_strings]
    
    movimientos_venta = await Movimiento.find({"_id": {"$in": ids_objetos}}).to_list()
    
    for mov in movimientos_venta:
        if mov.estado == "PENDIENTE":
            mov.estado = "CANCELADO"
            await mov.save()
        elif mov.estado == "EJECUTADO":
            mov_reverso = Movimiento(
                sku_articulo=mov.sku_articulo,
                codigo_almacen=mov.codigo_almacen,
                numero_lote=mov.numero_lote,
                usuario=usuario_actual.username, 
                tipo_movimiento=TipoMovimiento.ANULACION_SALIDA,
                concepto=f"Reintegro por anulación de venta {venta.folio}",
                cantidad=mov.cantidad,
                costo_unitario=mov.costo_unitario,
                flujo_trabajo_seleccionado=request.flujo_trabajo_seleccionado, 
                estado="PENDIENTE" 
            )
            await mov_reverso.insert()
            
    return {
        "mensaje": f"Venta {venta.folio} anulada correctamente.",
        "estado_actual": venta.estado,
        "anulada_por": usuario_actual.username
    }

# ==========================================
# ENDPOINT 5: LISTAR VENTAS
# ==========================================
@router.get("/", status_code=status.HTTP_200_OK)
async def listar_ventas(estado: Optional[EstadoVenta] = None):
    """
    Obtiene el historial de ventas. Permite filtrar por estado.
    """
    if estado:
        ventas = await Venta.find(Venta.estado == estado).sort(-Venta.fecha_registro).to_list()
    else:
        ventas = await Venta.find_all().sort(-Venta.fecha_registro).to_list()
        
    return ventas

# ==========================================
# ENDPOINT 6: OBTENER DETALLE
# ==========================================
@router.get("/{venta_id}", status_code=status.HTTP_200_OK)
async def obtener_detalle_venta(venta_id: str):
    """
    Busca una venta específica por su ID. Útil para imprimir el ticket o ver detalles.
    """
    try:
        id_obj = PydanticObjectId(venta_id)
    except:
        raise HTTPException(status_code=400, detail="Formato de ID inválido.")
        
    venta = await Venta.get(id_obj)
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada.")
        
    return venta