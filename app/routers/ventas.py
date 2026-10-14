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
from app.models.cliente import Cliente
from app.models.caja import Caja  

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
    flujo_trabajo_seleccionado: str 
    articulos: List[DetalleVenta]
    descuento_global: float = 0.0
    condicion_pago: CondicionPago = CondicionPago.CONTADO
    metodo_pago: str
    efectivo_recibido: float
    referencia_pago: str
    sucursal_id: str
    caja_id: str

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
    # 0. VALIDACIÓN DE CAJA Y ALMACÉN
    caja_origen = await Caja.find_one(Caja.codigo == request.caja_id, Caja.codigo_sucursal == request.sucursal_id)
    if not caja_origen:
        raise HTTPException(status_code=404, detail="La caja especificada no existe en esta sucursal.")
    
    if not caja_origen.codigo_almacen:
        raise HTTPException(
            status_code=400, 
            detail="La caja actual no tiene un almacén de despacho configurado. Contacte a administración."
        )
        
    almacen_despacho = caja_origen.codigo_almacen

    # ==========================================
    # ALTA RÁPIDA DE CLIENTE AUTOMÁTICA
    # ==========================================
    if request.documento_cliente and request.documento_cliente.strip().upper() != "S/N":
        cliente_existente = await Cliente.find_one(Cliente.documento_identidad == request.documento_cliente.strip().upper())
        if not cliente_existente:
            nuevo_cliente = Cliente(
                nombre_razon_social=request.cliente.strip(),
                documento_identidad=request.documento_cliente.strip().upper(),
                activo=True
            )
            await nuevo_cliente.insert()
    
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
        sucursal_id=request.sucursal_id,
        caja_id=request.caja_id,
        condicion_pago=request.condicion_pago,
        metodo_pago=request.metodo_pago,
        efectivo_recibido=request.efectivo_recibido,
        referencia_pago=request.referencia_pago,
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
            codigo_almacen=almacen_despacho, 
            numero_lote="LOTE-POR-ASIGNAR", 
            usuario=usuario_actual.username, 
            tipo_movimiento=TipoMovimiento.SALIDA_VENTA,
            cantidad=art.cantidad,
            costo_unitario=0.0,  
            concepto=f"Despacho por venta folio {folio_generado}",
            flujo_trabajo_seleccionado=request.flujo_trabajo_seleccionado,
            estado="PENDIENTE" 
        )
        movimientos_a_guardar.append(nuevo_movimiento)
        
    # 5. ZONA SEGURA: ESCRITURA
    await nueva_venta.insert()
    
    ids_movimientos = []
    for mov in movimientos_a_guardar:
        await mov.insert()
        ids_movimientos.append(str(mov.id))
        
    if ids_movimientos:
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
    try:
        print(f"\n--- INICIANDO DESPACHO DE VENTA: {venta_id} ---")
        
        # --- FUNCIONES ESCUDO (Para manejar tanto Diccionarios como Objetos) ---
        def get_codigo(item):
            if isinstance(item, dict): return str(item.get("codigo_almacen", "")).strip()
            return str(getattr(item, "codigo_almacen", "")).strip()
            
        def get_cantidad(item):
            if isinstance(item, dict): return float(item.get("cantidad", 0.0))
            return float(getattr(item, "cantidad", 0.0))

        def set_cantidad(item, valor):
            if isinstance(item, dict): item["cantidad"] = float(valor)
            else: item.cantidad = float(valor)
        # ------------------------------------------------------------------------

        try:
            id_obj = PydanticObjectId(venta_id)
        except Exception as e:
            print(f"Error en ID: {e}")
            raise HTTPException(status_code=400, detail="Formato de ID inválido.")
            
        venta = await Venta.get(id_obj)
        if not venta:
            raise HTTPException(status_code=404, detail="Venta no encontrada.")
            
        if not venta.referencia_movimiento_id:
            raise HTTPException(status_code=400, detail="Venta sin movimientos logísticos.")

        # 0. BÚSQUEDA SEGURA DE MOVIMIENTOS
        if isinstance(venta.referencia_movimiento_id, list):
            ids_strings = venta.referencia_movimiento_id
        else:
            ids_strings = [str(i).strip() for i in str(venta.referencia_movimiento_id).split(",") if str(i).strip()]
            
        ids_objetos = [PydanticObjectId(i) for i in ids_strings]

        from beanie.operators import In
        movimientos_venta = await Movimiento.find(In(Movimiento.id, ids_objetos)).to_list()
        
        if not movimientos_venta:
            print(f"No se encontraron movimientos para los IDs: {ids_objetos}")
            raise HTTPException(status_code=400, detail="Error interno: Movimientos no encontrados.")
        
        movimientos_pendientes = [mov for mov in movimientos_venta if getattr(mov, "estado", "PENDIENTE") != "EJECUTADO"]
        if not movimientos_pendientes:
            raise HTTPException(status_code=400, detail="¡Mercadería ya despachada anteriormente!")

        lotes_a_guardar = []
        articulos_a_guardar = []
        
        # 1. PREPARACIÓN LOGÍSTICA
        for mov in movimientos_pendientes:
            print(f"-> Procesando {mov.sku_articulo} | Cantidad: {mov.cantidad} | Almacén: {mov.codigo_almacen}")
            
            articulo = await Articulo.find_one(Articulo.sku == mov.sku_articulo)
            if not articulo:
                raise HTTPException(status_code=404, detail=f"Artículo {mov.sku_articulo} no encontrado.")
                
            cantidad_restante = float(mov.cantidad)
            costo_total = 0.0
            almacen_buscado = str(mov.codigo_almacen).strip()
            
            if getattr(articulo, 'controla_lotes', True):
                print(f"   Buscando lotes FEFO para {mov.sku_articulo}...")
                
                from zoneinfo import ZoneInfo
                from datetime import datetime
                
                todos_lotes = await Lote.find(Lote.sku_articulo == mov.sku_articulo).to_list()
                lotes_disponibles = [l for l in todos_lotes if float(getattr(l, "cantidad_actual", 0)) > 0]
                lotes_disponibles.sort(key=lambda x: x.fecha_vencimiento if getattr(x, "fecha_vencimiento", None) else datetime.max.replace(tzinfo=ZoneInfo("America/La_Paz")))
                
                print(f"   Lotes vigentes encontrados: {len(lotes_disponibles)}")
                lotes_utilizados = []
                
                for lote in lotes_disponibles:
                    if round(cantidad_restante, 4) <= 0: break
                        
                    # <-- APLICAMOS LA FUNCIÓN ESCUDO AQUÍ -->
                    stock_lote_alm = next((sl for sl in lote.stock_por_almacen if get_codigo(sl) == almacen_buscado), None)
                    
                    if stock_lote_alm and get_cantidad(stock_lote_alm) > 0:
                        cantidad_a_tomar = min(get_cantidad(stock_lote_alm), cantidad_restante)
                        print(f"   [+] Tomando {cantidad_a_tomar} del lote {lote.numero_lote}")
                        
                        costo_total += cantidad_a_tomar * float(getattr(lote, 'costo_unitario', 0.0))
                        
                        # Actualizamos valores
                        lote.cantidad_actual = float(lote.cantidad_actual) - cantidad_a_tomar
                        set_cantidad(stock_lote_alm, get_cantidad(stock_lote_alm) - cantidad_a_tomar)
                        
                        if lote not in lotes_a_guardar: lotes_a_guardar.append(lote)
                        lotes_utilizados.append(lote.numero_lote)
                        cantidad_restante -= cantidad_a_tomar
                        
                mov.numero_lote = ", ".join(lotes_utilizados) if lotes_utilizados else "SIN-LOTE"
            else:
                print(f"   Artículo sin lotes. Buscando stock directo...")
                
                # <-- APLICAMOS LA FUNCIÓN ESCUDO AQUÍ -->
                stock_almacen = next((alm for alm in articulo.stock_por_almacen if get_codigo(alm) == almacen_buscado), None)
                
                if stock_almacen and get_cantidad(stock_almacen) > 0:
                    cantidad_a_tomar = min(get_cantidad(stock_almacen), cantidad_restante)
                    print(f"   [+] Tomando {cantidad_a_tomar} de inventario general.")
                    costo_total += cantidad_a_tomar * float(getattr(articulo, 'costo_promedio', getattr(articulo, 'costo', 0.0)))
                    cantidad_restante -= cantidad_a_tomar
                mov.numero_lote = "N/A"
                
            if round(cantidad_restante, 4) > 0:
                print(f"   [ERROR] Stock insuficiente. Faltan {cantidad_restante} en {mov.codigo_almacen}")
                raise HTTPException(
                    status_code=400, 
                    detail=f"Falta stock físico real. No se encontraron {cantidad_restante} unidades de {mov.sku_articulo} en {mov.codigo_almacen}."
                )
                
            # <-- APLICAMOS LA FUNCIÓN ESCUDO PARA RESTAR AL MAESTRO -->
            stock_almacen = next((alm for alm in articulo.stock_por_almacen if get_codigo(alm) == almacen_buscado), None)
            if stock_almacen: 
                set_cantidad(stock_almacen, get_cantidad(stock_almacen) - float(mov.cantidad))
                
            articulo.stock_actual = float(getattr(articulo, "stock_actual", 0.0)) - float(mov.cantidad)
            if articulo not in articulos_a_guardar: articulos_a_guardar.append(articulo)
            
            mov.estado = "EJECUTADO"
            mov.costo_unitario = costo_total / float(mov.cantidad) if float(mov.cantidad) > 0 else 0.0

        # 2. FINANZAS
        print("-> Registrando finanzas...")
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
            if venta.estado == EstadoVenta.PENDIENTE: venta.estado = EstadoVenta.POR_COBRAR
        else:
            if venta.estado == EstadoVenta.PENDIENTE: venta.estado = EstadoVenta.PAGADA
            
        await venta.save()
        for articulo in articulos_a_guardar: await articulo.save()
        for lote in lotes_a_guardar: await lote.save()
        for mov in movimientos_pendientes: await mov.save()
        if cargo_cxc: await cargo_cxc.insert()
            
        print("✅ --- VENTA DESPACHADA CON ÉXITO ---")
        return {
            "mensaje": f"Mercadería despachada correctamente.",
            "folio": venta.folio,
            "estado_actual": venta.estado
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ ERROR INESPERADO (PYTHON): {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error inesperado en código: {str(e)}")
    

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