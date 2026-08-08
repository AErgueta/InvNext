# 1. Importaciones
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, Depends, Response
from pydantic import BaseModel, Field
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import io

from app.routers.auth import obtener_usuario_actual

# 2. Modelos
from app.models.movimiento import Movimiento, TipoMovimiento
from app.models.articulo import Articulo, StockAlmacen
from app.models.lote import Lote, StockLoteAlmacen
from app.models.usuario import Usuario, RolUsuario

# 3. Clases de Petición y Respuesta (Esquemas Pydantic)
class PeticionMovimiento(BaseModel):
    sku_articulo: str
    codigo_almacen: str
    numero_lote: str
    tipo_movimiento: TipoMovimiento
    cantidad: float = Field(..., gt=0, description="Cantidad del movimiento")
    costo_unitario: float = 0.0
    concepto: str
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
    saldo_inicial: float
    movimientos: list[Movimiento]

class PeticionAjusteCosto(BaseModel):
    sku_articulo: str
    numero_lote: str
    nuevo_costo: float = Field(..., gt=0, description="El nuevo costo unitario corregido")
    concepto: str = Field(..., description="Motivo de la revalorización")
    id_referencia: str | None = None

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
    # --- 0. CONVERSIÓN E INYECCIÓN DE SEGURIDAD ---
    movimiento = Movimiento(
        sku_articulo=peticion.sku_articulo,
        codigo_almacen=peticion.codigo_almacen,
        numero_lote=peticion.numero_lote,
        usuario=usuario_actual.username, # <--- FIRMA INMUTABLE
        tipo_movimiento=peticion.tipo_movimiento,
        cantidad=peticion.cantidad,
        costo_unitario=peticion.costo_unitario,
        concepto=peticion.concepto,
        id_referencia=peticion.id_referencia,
        precio_venta=peticion.precio_venta,
        fecha_vencimiento=peticion.fecha_vencimiento
    )

    # --- 1. VALIDACIONES DE SEGURIDAD Y AUDITORÍA ---
    if usuario_actual.rol == RolUsuario.OPERADOR:
        if movimiento.codigo_almacen != usuario_actual.codigo_almacen:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado: Como operador solo puedes registrar movimientos en el almacén '{usuario_actual.codigo_almacen}'."
            )
        if movimiento.tipo_movimiento == TipoMovimiento.AJUSTE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: Solo los administradores pueden realizar ajustes manuales de inventario."
            )

    # --- 2. VERIFICACIÓN DEL ARTÍCULO ---
    articulo = await Articulo.find_one(Articulo.sku == movimiento.sku_articulo)
    
    if not articulo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El artículo con SKU '{movimiento.sku_articulo}' no existe."
        )

    # --- INTERCEPTOR: Lógica de Lote Perpetuo ---
    if not articulo.controla_lotes:
        movimiento.fecha_vencimiento = None

    variacion_stock = 0.0

    # --- 3. LÓGICA MATEMÁTICA Y GESTIÓN DE LOTES CON ALMACENES ---
    if movimiento.tipo_movimiento in [TipoMovimiento.ENTRADA, TipoMovimiento.ENTRADA_PRODUCCION, TipoMovimiento.ENTRADA_TRASPASO]:
        lote = await Lote.find_one(
            Lote.numero_lote == movimiento.numero_lote,
            Lote.sku_articulo == movimiento.sku_articulo
        )
        
        if lote:
            if not articulo.controla_lotes:
                valor_actual = lote.cantidad_actual * lote.costo_unitario
                valor_nuevo = movimiento.cantidad * movimiento.costo_unitario
                nueva_cantidad = lote.cantidad_actual + movimiento.cantidad
                nuevo_costo = (valor_actual + valor_nuevo) / nueva_cantidad
                lote.costo_unitario = round(nuevo_costo, 4)
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
                sku_articulo=movimiento.sku_articulo,
                numero_lote=movimiento.numero_lote,
                cantidad_inicial=movimiento.cantidad,
                cantidad_actual=movimiento.cantidad,
                costo_unitario=movimiento.costo_unitario,
                fecha_vencimiento=movimiento.fecha_vencimiento,
                stock_por_almacen=[StockLoteAlmacen(codigo_almacen=movimiento.codigo_almacen, cantidad=movimiento.cantidad)]
            )
            await nuevo_lote.insert()
            
        articulo.stock_actual += movimiento.cantidad
        variacion_stock = movimiento.cantidad

    elif movimiento.tipo_movimiento in [TipoMovimiento.SALIDA_VENTA, TipoMovimiento.SALIDA_PRODUCCION, TipoMovimiento.SALIDA_TRASPASO]:
        lote = await Lote.find_one(
            Lote.numero_lote == movimiento.numero_lote,
            Lote.sku_articulo == movimiento.sku_articulo
        )
        
        if not lote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El lote '{movimiento.numero_lote}' no está registrado."
            )
            
        stock_lote_alm = next((sl for sl in lote.stock_por_almacen if sl.codigo_almacen == movimiento.codigo_almacen), None)
        
        if not stock_lote_alm or stock_lote_alm.cantidad < movimiento.cantidad:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock insuficiente en el lote {movimiento.numero_lote} para el almacén {movimiento.codigo_almacen}. Actual: {stock_lote_alm.cantidad if stock_lote_alm else 0}"
            )
            
        movimiento.costo_unitario = lote.costo_unitario
        
        if movimiento.tipo_movimiento == TipoMovimiento.SALIDA_VENTA:
            if movimiento.precio_venta is None:
                movimiento.precio_venta = articulo.precio_venta
        else:
            movimiento.precio_venta = None

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

    # --- 4. IMPACTAR STOCK EN EL ARTÍCULO (POR ALMACÉN) ---
    almacen_encontrado = False
    for stock_alm in articulo.stock_por_almacen:
        if stock_alm.codigo_almacen == movimiento.codigo_almacen:
            stock_alm.cantidad += variacion_stock
            almacen_encontrado = True
            break
            
    if not almacen_encontrado:
        articulo.stock_por_almacen.append(
            StockAlmacen(
                codigo_almacen=movimiento.codigo_almacen, 
                cantidad=variacion_stock
            )
        )

    # --- 5. GUARDADO FINAL ---
    await articulo.save()
    await movimiento.insert()
    
    return movimiento


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
        id_referencia=peticion.id_referencia
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
        id_referencia=peticion.id_referencia
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
            id_referencia=peticion.id_referencia
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
    
    return RespuestaKardex(
        sku=sku,
        almacen=codigo_almacen or "TODOS",
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

    saldo_inicial = 0.0
    
    filtros_hist = [Movimiento.sku_articulo == sku]
    if codigo_almacen:
        filtros_hist.append(Movimiento.codigo_almacen == codigo_almacen)
        
    if fecha_inicio:
        filtros_hist.append(Movimiento.fecha_registro < fecha_inicio)
        movimientos_previos = await Movimiento.find(*filtros_hist).to_list()
        
        for mov in movimientos_previos:
            # Incluimos IN_TRANS en el cálculo histórico previo
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
    
    # 1. Agregamos la columna "Saldo Valor" en las cabeceras del CSV
    writer.writerow([
        "Fecha", "Almacén", "Concepto", "Lote", "Tipo Movimiento", 
        "Costo Unitario", "Ingreso", "Egreso", "Saldo Físico", "Saldo Valor"
    ])
    
    # Fila de Saldo Inicial (con su valor inicial en dinero si aplica)
    valor_inicial_dinero = "$0.00" if saldo_inicial == 0 else "-"
    writer.writerow([
        fecha_inicio.strftime("%Y-%m-%d %H:%M") if fecha_inicio else "-", 
        codigo_almacen or "TODOS", "SALDO INICIAL", "-", "-", "-", "-", "-", saldo_inicial, valor_inicial_dinero
    ])
    
    saldo_actual = saldo_inicial
    for mov in movimientos_periodo:
        ingreso = 0
        egreso = 0
        
        # Alineado con los tipos que maneja tu frontend
        if mov.tipo_movimiento in [TipoMovimiento.ENTRADA, TipoMovimiento.ENTRADA_PRODUCCION, TipoMovimiento.ENTRADA_TRASPASO]:
            ingreso = mov.cantidad
            saldo_actual += mov.cantidad
        elif mov.tipo_movimiento in [TipoMovimiento.SALIDA_VENTA, TipoMovimiento.SALIDA_PRODUCCION, TipoMovimiento.SALIDA_TRASPASO]:
            egreso = mov.cantidad
            saldo_actual -= mov.cantidad
            
        # 2. Calculamos el saldo en dinero multiplicando el saldo físico actual por el costo unitario del movimiento
        saldo_valor = saldo_actual * mov.costo_unitario
            
        fecha_str = mov.fecha_registro.astimezone(tz_local).strftime("%Y-%m-%d %H:%M")
        
        writer.writerow([
            fecha_str,
            mov.codigo_almacen,
            mov.concepto,
            mov.numero_lote,
            mov.tipo_movimiento.value, 
            mov.costo_unitario,
            ingreso,
            egreso,
            saldo_actual,
            round(saldo_valor, 2) # Formateado a 2 decimales para orden contable
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
        id_referencia=peticion.id_referencia
    )
    await movimiento.insert()

    return movimiento