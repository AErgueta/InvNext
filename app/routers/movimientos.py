# 1. Importaciones
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, Depends, Response
from pydantic import BaseModel, Field
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import io
import uuid


from bson import ObjectId

from app.routers.auth import obtener_usuario_actual

# 2. Modelos
from app.models.movimiento import Movimiento, TipoMovimiento
from app.models.articulo import Articulo, StockAlmacen
from app.models.lote import Lote, StockLoteAlmacen
from app.models.usuario import Usuario, RolUsuario
from app.models.flujo import InstanciaTracking

# 3. Clases de Petición y Respuesta (Esquemas Pydantic)
class PeticionMovimiento(BaseModel):
    sku_articulo: str
    codigo_almacen: str
    numero_lote: str
    tipo_movimiento: TipoMovimiento
    cantidad: float = Field(..., gt=0, description="Cantidad del movimiento")
    costo_unitario: float = 0.0
    concepto: str
    flujo_trabajo_seleccionado: str = Field(..., description="Flujo de trabajo/aprobación seleccionado manualmente por el usuario")
    id_referencia: Optional[str] = None
    precio_venta: Optional[float] = None
    fecha_vencimiento: Optional[datetime] = None

class PeticionSalidaFIFO(BaseModel):
    sku_articulo: str
    codigo_almacen: str
    tipo_movimiento: TipoMovimiento
    concepto: str
    cantidad: float = Field(..., gt=0)
    id_referencia: Optional[str] = None

class PeticionSalida(BaseModel):
    sku_articulo: str
    codigo_almacen: str
    cantidad: float = Field(..., gt=0, description="Cantidad a retirar del almacén")
    concepto: str = Field(..., description="Ej: Consumo interno, Venta, Merma")
    id_referencia: str | None = None

class PeticionTraspaso(BaseModel):
    sku_articulo: str
    codigo_almacen_origen: str
    codigo_almacen_destino: str
    numero_lote: str
    cantidad: float = Field(..., gt=0, description="Cantidad a traspasar")
    concepto: str = "Traspaso interno"
    id_referencia: str

class RespuestaKardex(BaseModel):
    sku: str
    almacen: Optional[str] = None
    unidad_medida: str = "UNIDADES"
    saldo_inicial: float
    movimientos: list[Movimiento]

class PeticionAjusteCosto(BaseModel):
    sku_articulo: str
    numero_lote: str
    nuevo_costo: float = Field(..., gt=0, description="El nuevo costo unitario corregido")
    concepto: str = Field(..., description="Motivo de la revalorización")
    id_referencia: str | None = None

class PeticionIngresoManual(BaseModel):
    sku_articulo: str
    codigo_almacen: str
    cantidad: float = Field(..., gt=0, description="Cantidad a ingresar")
    costo_unitario: float = Field(..., gt=0, description="Costo unitario mayor a cero")
    numero_lote: Optional[str] = None
    flujo_trabajo_seleccionado: str = Field(..., description="Flujo de trabajo de seguimiento obligatorio")
    concepto: str = "Ingreso manual"

class PeticionEgresoManual(BaseModel):
    sku_articulo: str
    codigo_almacen: str
    tipo_movimiento: TipoMovimiento
    cantidad: float = Field(..., gt=0, description="Cantidad total a retirar")
    concepto: str = Field(..., description="Motivo de la salida")
    flujo_trabajo_seleccionado: str = Field(..., description="El usuario debe elegir obligatoriamente su propio flujo de seguimiento")
    id_referencia: Optional[str] = None

# 4. Enrutador
router = APIRouter(
    prefix="/movimientos",
    tags=["Movimientos"]
)

@router.post("/", response_model=Movimiento, status_code=status.HTTP_201_CREATED)
async def registrar_movimiento(
    peticion: PeticionMovimiento,
    usuario_actual = Depends(obtener_usuario_actual)
):
    # --- 1. VALIDACIONES DE SEGURIDAD BÁSICAS ---
    if usuario_actual.rol == RolUsuario.OPERADOR:
        if peticion.codigo_almacen != usuario_actual.codigo_almacen:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado: Como operador solo puedes registrar movimientos en el almacén '{usuario_actual.codigo_almacen}'."
            )
        if peticion.tipo_movimiento == TipoMovimiento.AJUSTE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: Solo los administradores pueden realizar ajustes manuales de inventario."
            )

    articulo = await Articulo.find_one(Articulo.sku == peticion.sku_articulo)
    if not articulo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El artículo con SKU '{peticion.sku_articulo}' no existe."
        )

    # --- 2. CREACIÓN DEL DOCUMENTO (Solo intención, no afecta stock físico) ---
    movimiento = Movimiento(
        sku_articulo=peticion.sku_articulo,
        codigo_almacen=peticion.codigo_almacen,
        numero_lote=peticion.numero_lote,
        usuario=usuario_actual.username, 
        tipo_movimiento=peticion.tipo_movimiento,
        cantidad=peticion.cantidad,
        costo_unitario=peticion.costo_unitario,
        concepto=peticion.concepto,
        id_referencia=peticion.id_referencia,
        precio_venta=peticion.precio_venta,
        fecha_vencimiento=peticion.fecha_vencimiento,
        
        # ---> LÍNEA AGREGADA: Pasamos el flujo seleccionado por el usuario <---
        flujo_trabajo_seleccionado=peticion.flujo_trabajo_seleccionado,
        
        estado="PENDIENTE" # <--- El candado inicial
    )
    
    await movimiento.insert()
    return movimiento

@router.post("/ingreso", status_code=status.HTTP_201_CREATED)
async def registrar_ingreso_manual(
    peticion: PeticionIngresoManual,
    usuario_actual: Usuario = Depends(obtener_usuario_actual)
):
    # 1. Validaciones de Seguridad
    if usuario_actual.rol == RolUsuario.OPERADOR:
        if peticion.codigo_almacen != usuario_actual.codigo_almacen:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado: Solo puedes registrar ingresos en '{usuario_actual.codigo_almacen}'."
            )

    articulo = await Articulo.find_one(Articulo.sku == peticion.sku_articulo)
    if not articulo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El artículo con SKU '{peticion.sku_articulo}' no existe."
        )

    # 2. Autogeneración de Lote Inteligente
    lote_final = peticion.numero_lote
    if not lote_final or lote_final.strip() == "":
        fecha_str = datetime.now().strftime("%Y%m%d")
        hash_corto = uuid.uuid4().hex[:4].upper()
        lote_final = f"LOT-{fecha_str}-{hash_corto}"

    # 3. Creación del Documento (Con candado de PENDIENTE)
    nuevo_movimiento = Movimiento(
        sku_articulo=peticion.sku_articulo,
        codigo_almacen=peticion.codigo_almacen,
        numero_lote=lote_final,
        usuario=usuario_actual.username,
        tipo_movimiento=TipoMovimiento.ENTRADA, 
        cantidad=peticion.cantidad,
        costo_unitario=peticion.costo_unitario,
        concepto=peticion.concepto,
        flujo_trabajo_seleccionado=peticion.flujo_trabajo_seleccionado, 
        estado="PENDIENTE" 
    )
    
    await nuevo_movimiento.insert()

    return {
        "mensaje": "Ingreso manual registrado correctamente.",
        "movimiento_id": str(nuevo_movimiento.id),
        "lote": lote_final,
        "estado": "PENDIENTE"
    }

@router.post("/egreso", status_code=status.HTTP_201_CREATED)
async def registrar_egreso_manual(
    peticion: PeticionEgresoManual,
    usuario_actual: Usuario = Depends(obtener_usuario_actual)
):
    # --- 1. VALIDACIONES DE SEGURIDAD ---
    if usuario_actual.rol == RolUsuario.OPERADOR:
        if peticion.codigo_almacen != usuario_actual.codigo_almacen:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado: Solo puedes retirar mercancía de tu almacén asignado '{usuario_actual.codigo_almacen}'."
            )

    if peticion.tipo_movimiento not in [TipoMovimiento.SALIDA_VENTA, TipoMovimiento.SALIDA_PRODUCCION, TipoMovimiento.SALIDA_TRASPASO]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El tipo de movimiento debe corresponder a una salida."
        )

    articulo = await Articulo.find_one(Articulo.sku == peticion.sku_articulo)
    if not articulo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artículo no encontrado.")
        
    stock_almacen = next((alm for alm in articulo.stock_por_almacen if alm.codigo_almacen == peticion.codigo_almacen), None)
    if not stock_almacen or stock_almacen.cantidad < peticion.cantidad:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stock físico insuficiente en el almacén {peticion.codigo_almacen}. Se solicitaron {peticion.cantidad} pero solo hay {stock_almacen.cantidad if stock_almacen else 0}."
        )

    # --- 2. EXTRACCIÓN Y ORDENAMIENTO FEFO ---
    lotes_activos = await Lote.find(
        Lote.sku_articulo == peticion.sku_articulo,
        Lote.cantidad_actual > 0
    ).to_list()
    
    lotes_validos_en_sucursal = []
    for l in lotes_activos:
        s_alm = next((sl for sl in l.stock_por_almacen if sl.codigo_almacen == peticion.codigo_almacen), None)
        if s_alm and s_alm.cantidad > 0:
            lotes_validos_en_sucursal.append((l, s_alm))

    # Función segura para ordenar fechas (FEFO)
    def obtener_fecha_orden(lote):
        if not lote.fecha_vencimiento:
            return datetime.max # Si no tiene vencimiento, va al final de la cola
        if isinstance(lote.fecha_vencimiento, datetime):
            return lote.fecha_vencimiento.replace(tzinfo=None)
        try:
            return datetime.strptime(str(lote.fecha_vencimiento)[:10], "%Y-%m-%d")
        except:
            return datetime.max

    # Ordenamos: primero los que vencen más pronto
    lotes_validos_en_sucursal.sort(key=lambda x: obtener_fecha_orden(x[0]))

    # --- 3. DESCUENTO EN CASCADA ---
    cantidad_restante = peticion.cantidad
    movimientos_a_guardar = []
    lotes_a_guardar = []
    
    for lote, stock_lote_alm in lotes_validos_en_sucursal:
        if cantidad_restante <= 0:
            break
            
        cantidad_a_tomar = min(stock_lote_alm.cantidad, cantidad_restante)
        
        # Descuento del lote
        lote.cantidad_actual -= cantidad_a_tomar
        stock_lote_alm.cantidad -= cantidad_a_tomar
        lotes_a_guardar.append(lote) 
        
        precio_v = articulo.precio_venta if peticion.tipo_movimiento == TipoMovimiento.SALIDA_VENTA else None
        
        # Generación del movimiento individual asegurando el flujo elegido
        nuevo_movimiento = Movimiento(
            sku_articulo=articulo.sku,
            codigo_almacen=peticion.codigo_almacen,
            numero_lote=lote.numero_lote,
            usuario=usuario_actual.username, 
            tipo_movimiento=peticion.tipo_movimiento,
            concepto=peticion.concepto,
            cantidad=cantidad_a_tomar,
            costo_unitario=lote.costo_unitario, 
            precio_venta=precio_v,
            flujo_trabajo_seleccionado=peticion.flujo_trabajo_seleccionado, # Control de destino manual
            id_referencia=peticion.id_referencia,
            estado="EJECUTADO"
        )
        
        movimientos_a_guardar.append(nuevo_movimiento) 
        cantidad_restante -= cantidad_a_tomar
        
    # Descuento global del artículo
    articulo.stock_actual -= peticion.cantidad
    stock_almacen.cantidad -= peticion.cantidad
    
    # --- 4. PERSISTENCIA EN BASE DE DATOS ---
    for lote in lotes_a_guardar:
        await lote.save()
        
    for mov in movimientos_a_guardar:
        await mov.insert()
        
    await articulo.save()
    
    return {
        "mensaje": "Salida manual completada bajo estrategia FEFO.",
        "cantidad_total": peticion.cantidad,
        "lotes_afectados": len(movimientos_a_guardar),
        "detalle_movimientos": movimientos_a_guardar
    }

@router.patch("/{movimiento_id}/ejecutar", status_code=status.HTTP_200_OK)
async def ejecutar_movimiento(
    movimiento_id: str,
    usuario_actual = Depends(obtener_usuario_actual)
):
    movimiento = await Movimiento.get(ObjectId(movimiento_id))
    if not movimiento:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado.")

    if getattr(movimiento, "estado", "EJECUTADO") == "EJECUTADO":
        raise HTTPException(status_code=400, detail="Este movimiento ya fue procesado y sumado al inventario.")

    # --- 1. VALIDACIÓN DE GOBERNANZA (EL CANDADO) ---
    instancia = await InstanciaTracking.find_one(InstanciaTracking.referencia_id == str(movimiento.id))
    if instancia and instancia.estado_general != "COMPLETADO":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede procesar el inventario. El flujo de aprobación aún no ha concluido."
        )

    # --- 2. LÓGICA MATEMÁTICA Y GESTIÓN DE LOTES (Tu código original intacto) ---
    articulo = await Articulo.find_one(Articulo.sku == movimiento.sku_articulo)
    
    if not articulo.controla_lotes:
        movimiento.fecha_vencimiento = None

    variacion_stock = 0.0

    if movimiento.tipo_movimiento in [TipoMovimiento.ENTRADA, TipoMovimiento.ENTRADA_PRODUCCION, TipoMovimiento.ENTRADA_TRASPASO]:
        lote = await Lote.find_one(Lote.numero_lote == movimiento.numero_lote, Lote.sku_articulo == movimiento.sku_articulo)
        if lote:
            if not articulo.controla_lotes:
                valor_actual = lote.cantidad_actual * lote.costo_unitario
                valor_nuevo = movimiento.cantidad * movimiento.costo_unitario
                nueva_cantidad = lote.cantidad_actual + movimiento.cantidad
                lote.costo_unitario = round((valor_actual + valor_nuevo) / nueva_cantidad, 4)
            else:
                lote.costo_unitario = movimiento.costo_unitario
                
            lote.cantidad_actual += movimiento.cantidad
            stock_lote_alm = next((sl for sl in lote.stock_por_almacen if sl.codigo_almacen == movimiento.codigo_almacen), None)
            
            if stock_lote_alm:
                stock_lote_alm.cantidad += movimiento.cantidad
            else:
                lote.stock_por_almacen.append(StockLoteAlmacen(codigo_almacen=movimiento.codigo_almacen, cantidad=movimiento.cantidad))
            await lote.save()
        else:
            nuevo_lote = Lote(
                sku_articulo=movimiento.sku_articulo, numero_lote=movimiento.numero_lote,
                cantidad_inicial=movimiento.cantidad, cantidad_actual=movimiento.cantidad,
                costo_unitario=movimiento.costo_unitario, fecha_vencimiento=movimiento.fecha_vencimiento,
                stock_por_almacen=[StockLoteAlmacen(codigo_almacen=movimiento.codigo_almacen, cantidad=movimiento.cantidad)]
            )
            await nuevo_lote.insert()
            
        articulo.stock_actual += movimiento.cantidad
        variacion_stock = movimiento.cantidad

    elif movimiento.tipo_movimiento in [TipoMovimiento.SALIDA_VENTA, TipoMovimiento.SALIDA_PRODUCCION, TipoMovimiento.SALIDA_TRASPASO]:
        lote = await Lote.find_one(Lote.numero_lote == movimiento.numero_lote, Lote.sku_articulo == movimiento.sku_articulo)
        if not lote:
            raise HTTPException(status_code=404, detail="El lote no está registrado.")
            
        stock_lote_alm = next((sl for sl in lote.stock_por_almacen if sl.codigo_almacen == movimiento.codigo_almacen), None)
        if not stock_lote_alm or stock_lote_alm.cantidad < movimiento.cantidad:
            raise HTTPException(status_code=400, detail="Stock insuficiente en el lote especificado.")
            
        movimiento.costo_unitario = lote.costo_unitario
        if movimiento.tipo_movimiento == TipoMovimiento.SALIDA_VENTA and movimiento.precio_venta is None:
            movimiento.precio_venta = articulo.precio_venta

        lote.cantidad_actual -= movimiento.cantidad
        stock_lote_alm.cantidad -= movimiento.cantidad
        await lote.save()
        
        articulo.stock_actual -= movimiento.cantidad
        variacion_stock = -movimiento.cantidad

    elif movimiento.tipo_movimiento == TipoMovimiento.AJUSTE:
            lote = await Lote.find_one(
                Lote.numero_lote == movimiento.numero_lote,
                Lote.sku_articulo == movimiento.sku_articulo
            )
            if not lote:
                raise HTTPException(status_code=404, detail="Lote no encontrado para el ajuste.")
                
            stock_lote_alm = next((sl for sl in lote.stock_por_almacen if sl.codigo_almacen == movimiento.codigo_almacen), None)
            
            if stock_lote_alm:
                diferencia = movimiento.cantidad - stock_lote_alm.cantidad
                stock_lote_alm.cantidad = movimiento.cantidad
            else:
                diferencia = movimiento.cantidad
                lote.stock_por_almacen.append(StockLoteAlmacen(codigo_almacen=movimiento.codigo_almacen, cantidad=movimiento.cantidad))
                
            lote.cantidad_actual += diferencia
            await lote.save()
            
            articulo.stock_actual += diferencia
            variacion_stock = diferencia

    # --- 3. IMPACTAR STOCK EN EL ARTÍCULO ---
    almacen_encontrado = False
    for stock_alm in articulo.stock_por_almacen:
        if stock_alm.codigo_almacen == movimiento.codigo_almacen:
            stock_alm.cantidad += variacion_stock
            almacen_encontrado = True
            break
            
    if not almacen_encontrado:
        articulo.stock_por_almacen.append(StockAlmacen(codigo_almacen=movimiento.codigo_almacen, cantidad=variacion_stock))

    # --- 4. GUARDADO FINAL ---
    movimiento.estado = "EJECUTADO"
    await articulo.save()
    await movimiento.save()
    
    return {"mensaje": "Movimiento ejecutado y stock actualizado correctamente.", "movimiento": movimiento}

@router.post("/traspaso", status_code=status.HTTP_201_CREATED)
async def registrar_traspaso(
    peticion: PeticionTraspaso,
    usuario_actual: Usuario = Depends(obtener_usuario_actual)
):
    if usuario_actual.rol == RolUsuario.OPERADOR:
        if peticion.codigo_almacen_origen != usuario_actual.codigo_almacen:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No tienes permisos para sacar mercancía de {peticion.codigo_almacen_origen}."
            )
    
    articulo = await Articulo.find_one(Articulo.sku == peticion.sku_articulo)
    if not articulo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artículo no encontrado.")

    lote = await Lote.find_one(Lote.numero_lote == peticion.numero_lote, Lote.sku_articulo == peticion.sku_articulo)
    if not lote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado.")

    stock_art_origen = next((alm for alm in articulo.stock_por_almacen if alm.codigo_almacen == peticion.codigo_almacen_origen), None)
    if not stock_art_origen or stock_art_origen.cantidad < peticion.cantidad:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stock de artículo insuficiente en el origen.")

    stock_lote_origen = next((sl for sl in lote.stock_por_almacen if sl.codigo_almacen == peticion.codigo_almacen_origen), None)
    if not stock_lote_origen or stock_lote_origen.cantidad < peticion.cantidad:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El lote no tiene stock físico suficiente en el almacén de origen.")

    stock_art_origen.cantidad -= peticion.cantidad
    stock_art_destino = next((alm for alm in articulo.stock_por_almacen if alm.codigo_almacen == peticion.codigo_almacen_destino), None)
    if stock_art_destino:
        stock_art_destino.cantidad += peticion.cantidad
    else:
        articulo.stock_por_almacen.append(StockAlmacen(codigo_almacen=peticion.codigo_almacen_destino, cantidad=peticion.cantidad))

    stock_lote_origen.cantidad -= peticion.cantidad
    stock_lote_destino = next((sl for sl in lote.stock_por_almacen if sl.codigo_almacen == peticion.codigo_almacen_destino), None)
    if stock_lote_destino:
        stock_lote_destino.cantidad += peticion.cantidad
    else:
        lote.stock_por_almacen.append(StockLoteAlmacen(codigo_almacen=peticion.codigo_almacen_destino, cantidad=peticion.cantidad))

    mov_salida = Movimiento(
        sku_articulo=articulo.sku,
        codigo_almacen=peticion.codigo_almacen_origen,
        almacen_contraparte=peticion.codigo_almacen_destino,
        numero_lote=peticion.numero_lote,
        usuario=usuario_actual.username, # <--- SEGURIDAD APLICADA
        tipo_movimiento=TipoMovimiento.SALIDA_TRASPASO,
        concepto=peticion.concepto,
        cantidad=peticion.cantidad,
        costo_unitario=lote.costo_unitario,
        id_referencia=peticion.id_referencia,
        estado="EJECUTADO"
    )

    mov_entrada = Movimiento(
        sku_articulo=articulo.sku,
        codigo_almacen=peticion.codigo_almacen_destino,
        almacen_contraparte=peticion.codigo_almacen_origen,
        numero_lote=peticion.numero_lote,
        usuario=usuario_actual.username, # <--- SEGURIDAD APLICADA
        tipo_movimiento=TipoMovimiento.ENTRADA_TRASPASO,
        concepto=peticion.concepto,
        cantidad=peticion.cantidad,
        costo_unitario=lote.costo_unitario,
        id_referencia=peticion.id_referencia,
        estado="EJECUTADO"
    )

    await lote.save()
    await articulo.save()
    await mov_salida.insert()
    await mov_entrada.insert()

    return {
        "mensaje": "Traspaso exitoso",
        "salida": mov_salida,
        "entrada": mov_entrada
    }

@router.post("/salida-automatica", status_code=status.HTTP_201_CREATED)
async def registrar_salida_fifo(
    peticion: PeticionSalidaFIFO,
    usuario_actual = Depends(obtener_usuario_actual)
):
    if usuario_actual.rol == RolUsuario.OPERADOR:
        if peticion.codigo_almacen != usuario_actual.codigo_almacen:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado: Solo puedes procesar salidas automáticas desde tu almacén asignado '{usuario_actual.codigo_almacen}'."
            )

    if peticion.tipo_movimiento not in [TipoMovimiento.SALIDA_VENTA, TipoMovimiento.SALIDA_PRODUCCION, TipoMovimiento.SALIDA_TRASPASO]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El tipo de movimiento debe ser una salida."
        )
        
    if peticion.cantidad <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La cantidad debe ser mayor a cero."
        )

    articulo = await Articulo.find_one(Articulo.sku == peticion.sku_articulo)
    if not articulo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El artículo con SKU '{peticion.sku_articulo}' no existe."
        )
        
    stock_almacen = next((alm for alm in articulo.stock_por_almacen if alm.codigo_almacen == peticion.codigo_almacen), None)
    if not stock_almacen or stock_almacen.cantidad < peticion.cantidad:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stock insuficiente en el almacén {peticion.codigo_almacen}."
        )
        
    lotes_activos = await Lote.find(
        Lote.sku_articulo == peticion.sku_articulo,
        Lote.cantidad_actual > 0
    ).sort("+_id").to_list()
    
    lotes_validos_en_sucursal = []
    for l in lotes_activos:
        s_alm = next((sl for sl in l.stock_por_almacen if sl.codigo_almacen == peticion.codigo_almacen), None)
        if s_alm and s_alm.cantidad > 0:
            lotes_validos_en_sucursal.append((l, s_alm))
            
    cantidad_restante = peticion.cantidad
    movimientos_a_guardar = []
    lotes_a_guardar = []
    
    for lote, stock_lote_alm in lotes_validos_en_sucursal:
        if cantidad_restante <= 0:
            break
            
        cantidad_a_tomar = min(stock_lote_alm.cantidad, cantidad_restante)
        
        lote.cantidad_actual -= cantidad_a_tomar
        stock_lote_alm.cantidad -= cantidad_a_tomar
        lotes_a_guardar.append(lote) 
        
        precio_v = articulo.precio_venta if peticion.tipo_movimiento == TipoMovimiento.SALIDA_VENTA else None
        
        nuevo_movimiento = Movimiento(
            sku_articulo=articulo.sku,
            codigo_almacen=peticion.codigo_almacen,
            numero_lote=lote.numero_lote,
            usuario=usuario_actual.username, # <--- SEGURIDAD APLICADA
            tipo_movimiento=peticion.tipo_movimiento,
            concepto=peticion.concepto,
            cantidad=cantidad_a_tomar,
            costo_unitario=lote.costo_unitario, 
            precio_venta=precio_v,
            id_referencia=peticion.id_referencia,
            estado="EJECUTADO"
        )
        
        movimientos_a_guardar.append(nuevo_movimiento) 
        cantidad_restante -= cantidad_a_tomar
        
    articulo.stock_actual -= peticion.cantidad
    stock_almacen.cantidad -= peticion.cantidad
    
    for lote in lotes_a_guardar:
        await lote.save()
        
    for mov in movimientos_a_guardar:
        await mov.insert()
        
    await articulo.save()
    
    return {
        "mensaje": f"Salida automática completada. Se descontó correctamente.",
        "lotes_afectados": len(movimientos_a_guardar),
        "movimientos_generados": movimientos_a_guardar
    }

@router.get("/", response_model=list[Movimiento], status_code=status.HTTP_200_OK)
async def obtener_todos_los_movimientos(codigo_almacen: Optional[str] = None):
    filtros = []
    if codigo_almacen:
        filtros.append(Movimiento.codigo_almacen == codigo_almacen)
        
    movimientos = await Movimiento.find(*filtros).sort(+Movimiento.fecha_registro).to_list()
    return movimientos

@router.get("/{sku}", response_model=RespuestaKardex, status_code=status.HTTP_200_OK)
async def obtener_movimientos_por_articulo(
    sku: str, 
    codigo_almacen: Optional[str] = None, 
    fecha_inicio: Optional[datetime] = None, 
    fecha_fin: Optional[datetime] = None
):
    tz_local = ZoneInfo("America/La_Paz")
    
    if fecha_inicio and fecha_inicio.tzinfo is None:
        fecha_inicio = fecha_inicio.replace(tzinfo=tz_local)
    if fecha_fin and fecha_fin.tzinfo is None:
        fecha_fin = fecha_fin.replace(tzinfo=tz_local)

    saldo_inicial = 0.0
    
    filtros_hist = [Movimiento.sku_articulo == sku]
    if codigo_almacen:
        filtros_hist.append(Movimiento.codigo_almacen == codigo_almacen)
        
    if fecha_inicio:
        filtros_hist.append(Movimiento.fecha_registro < fecha_inicio)
        movimientos_previos = await Movimiento.find(*filtros_hist).to_list()
        
        for mov in movimientos_previos:
            if mov.tipo_movimiento in [TipoMovimiento.ENTRADA, TipoMovimiento.ENTRADA_PRODUCCION, TipoMovimiento.ENTRADA_TRASPASO]:
                saldo_inicial += mov.cantidad
            elif mov.tipo_movimiento in [TipoMovimiento.SALIDA_VENTA, TipoMovimiento.SALIDA_PRODUCCION, TipoMovimiento.SALIDA_TRASPASO]:
                saldo_inicial -= mov.cantidad

    filtros_periodo = [Movimiento.sku_articulo == sku]
    if codigo_almacen:
        filtros_periodo.append(Movimiento.codigo_almacen == codigo_almacen)
    if fecha_inicio:
        filtros_periodo.append(Movimiento.fecha_registro >= fecha_inicio)
    if fecha_fin:
        filtros_periodo.append(Movimiento.fecha_registro <= fecha_fin)
        
    movimientos_periodo = await Movimiento.find(*filtros_periodo).sort(+Movimiento.fecha_registro).to_list()
    
    # ---> NUEVO: Buscamos el artículo para leer sus metadatos <---
    articulo = await Articulo.find_one(Articulo.sku == sku)
    unidad = "UNIDADES" # Valor por defecto si no tiene metadatos
    if articulo and articulo.metadatos:
        unidad = articulo.metadatos.get("unidad_medida", "UNIDADES")

    return RespuestaKardex(
        sku=sku,
        almacen=codigo_almacen or "TODOS",
        unidad_medida=unidad, # <--- Se lo pasamos al esquema de respuesta
        saldo_inicial=saldo_inicial,
        movimientos=movimientos_periodo
    )


@router.get("/{sku}/exportar", status_code=status.HTTP_200_OK)
async def exportar_kardex_csv(
    sku: str, 
    codigo_almacen: Optional[str] = None,
    fecha_inicio: Optional[datetime] = None, 
    fecha_fin: Optional[datetime] = None
):
    tz_local = ZoneInfo("America/La_Paz")
    
    if fecha_inicio and fecha_inicio.tzinfo is None:
        fecha_inicio = fecha_inicio.replace(tzinfo=tz_local)
    if fecha_fin and fecha_fin.tzinfo is None:
        fecha_fin = fecha_fin.replace(tzinfo=tz_local)

    # ---> NUEVO: Buscamos el artículo para extraer su unidad de medida <---
    articulo = await Articulo.find_one(Articulo.sku == sku)
    unidad = "UNIDADES" 
    if articulo and articulo.metadatos:
        unidad = articulo.metadatos.get("unidad_medida", "UNIDADES")

    saldo_inicial = 0.0
    
    filtros_hist = [Movimiento.sku_articulo == sku]
    if codigo_almacen:
        filtros_hist.append(Movimiento.codigo_almacen == codigo_almacen)
        
    if fecha_inicio:
        filtros_hist.append(Movimiento.fecha_registro < fecha_inicio)
        movimientos_previos = await Movimiento.find(*filtros_hist).to_list()
        
        for mov in movimientos_previos:
            if mov.tipo_movimiento in [TipoMovimiento.ENTRADA, TipoMovimiento.ENTRADA_PRODUCCION, TipoMovimiento.ENTRADA_TRASPASO]:
                saldo_inicial += mov.cantidad
            elif mov.tipo_movimiento in [TipoMovimiento.SALIDA_VENTA, TipoMovimiento.SALIDA_PRODUCCION, TipoMovimiento.SALIDA_TRASPASO]:
                saldo_inicial -= mov.cantidad

    filtros_periodo = [Movimiento.sku_articulo == sku]
    if codigo_almacen:
        filtros_periodo.append(Movimiento.codigo_almacen == codigo_almacen)
    if fecha_inicio:
        filtros_periodo.append(Movimiento.fecha_registro >= fecha_inicio)
    if fecha_fin:
        filtros_periodo.append(Movimiento.fecha_registro <= fecha_fin)
        
    movimientos_periodo = await Movimiento.find(*filtros_periodo).sort(+Movimiento.fecha_registro).to_list()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=",")
    
    # ---> NUEVO: Inyectamos la unidad dinámica en las cabeceras del CSV <---
    writer.writerow([
        "Fecha", "Almacén", "Concepto", "Lote", "Tipo Movimiento", 
        "Costo Unitario", f"Ingreso ({unidad})", f"Egreso ({unidad})", f"Saldo Físico ({unidad})", "Saldo Valor"
    ])
    
    valor_inicial_dinero = "$0.00" if saldo_inicial == 0 else "-"
    writer.writerow([
        fecha_inicio.strftime("%Y-%m-%d %H:%M") if fecha_inicio else "-", 
        codigo_almacen or "TODOS", "SALDO INICIAL", "-", "-", "-", "-", "-", saldo_inicial, valor_inicial_dinero
    ])
    
    saldo_actual = saldo_inicial
    for mov in movimientos_periodo:
        ingreso = 0
        egreso = 0
        
        if mov.tipo_movimiento in [TipoMovimiento.ENTRADA, TipoMovimiento.ENTRADA_PRODUCCION, TipoMovimiento.ENTRADA_TRASPASO]:
            ingreso = mov.cantidad
            saldo_actual += mov.cantidad
        elif mov.tipo_movimiento in [TipoMovimiento.SALIDA_VENTA, TipoMovimiento.SALIDA_PRODUCCION, TipoMovimiento.SALIDA_TRASPASO]:
            egreso = mov.cantidad
            saldo_actual -= mov.cantidad
            
        saldo_valor = saldo_actual * mov.costo_unitario
            
        fecha_str = mov.fecha_registro.astimezone(tz_local).strftime("%Y-%m-%d %H:%M")
        
        writer.writerow([
            fecha_str,
            mov.codigo_almacen,
            mov.concepto,
            mov.numero_lote,
            mov.tipo_movimiento.value, 
            mov.costo_unitario,
            ingreso if ingreso > 0 else "-", # Limpieza visual
            egreso if egreso > 0 else "-",   # Limpieza visual
            saldo_actual,
            round(saldo_valor, 2) 
        ])
        
    csv_content = output.getvalue()
    
    sufijo_archivo = f"_{codigo_almacen}" if codigo_almacen else "_global"
    return Response(
        content=csv_content.encode('utf-8-sig'),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=kardex_{sku}{sufijo_archivo}.csv"}
    )

@router.post("/ajuste-costo", response_model=Movimiento, status_code=status.HTTP_201_CREATED)
async def registrar_ajuste_costo(
    peticion: PeticionAjusteCosto,
    usuario_actual = Depends(obtener_usuario_actual)
):
    if usuario_actual.rol != RolUsuario.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Solo los administradores pueden revalorizar costos."
        )

    articulo = await Articulo.find_one(Articulo.sku == peticion.sku_articulo)
    if not articulo:
        raise HTTPException(status_code=404, detail=f"El artículo '{peticion.sku_articulo}' no existe.")

    lote = await Lote.find_one(
            Lote.numero_lote == peticion.numero_lote,
            Lote.sku_articulo == peticion.sku_articulo
        )
        
    if not lote:
        raise HTTPException(status_code=404, detail=f"El lote '{peticion.numero_lote}' no existe.")

    costo_anterior = lote.costo_unitario

    lote.costo_unitario = peticion.nuevo_costo
    await lote.save()

    concepto_extendido = f"{peticion.concepto} (Cambiado de ${costo_anterior} a ${peticion.nuevo_costo})"
    
    movimiento = Movimiento(
        sku_articulo=articulo.sku,
        codigo_almacen="GLOBAL", 
        numero_lote=lote.numero_lote,
        usuario=usuario_actual.username,
        tipo_movimiento=TipoMovimiento.REVALORIZACION,
        concepto=concepto_extendido,
        cantidad=0.0,            
        costo_unitario=peticion.nuevo_costo,
        id_referencia=peticion.id_referencia,
        estado="EJECUTADO"
    )
    await movimiento.insert()

    return movimiento