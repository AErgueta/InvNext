# 1. Asegúrate de tener estas importaciones al inicio del archivo:
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

# 2. Asegúrate de importar tus modelos (incluyendo TipoMovimiento):
from app.models.movimiento import Movimiento, TipoMovimiento
from app.models.articulo import Articulo
from app.models.lote import Lote

# 3. Y JUSTO DEBAJO de las importaciones, colocas la clase:
class PeticionSalidaFIFO(BaseModel):
    sku_articulo: str
    usuario: str
    tipo_movimiento: TipoMovimiento
    concepto: str
    cantidad: float
    id_referencia: Optional[str] = None

router = APIRouter(
    prefix="/movimientos",
    tags=["Movimientos"]
)

@router.post("/", response_model=Movimiento, status_code=status.HTTP_201_CREATED)
async def registrar_movimiento(movimiento: Movimiento):
    # 1. Verificamos que el artículo global exista
    articulo = await Articulo.find_one(Articulo.sku == movimiento.sku_articulo)
    
    if not articulo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El artículo con SKU '{movimiento.sku_articulo}' no existe."
        )

    # --- INTERCEPTOR: Lógica de Lote Perpetuo ---
    if not articulo.controla_lotes:
        movimiento.numero_lote = "SIN-LOTE"
        movimiento.fecha_vencimiento = None

    # 2. Lógica matemática y gestión de Lotes
    if movimiento.tipo_movimiento in [TipoMovimiento.ENTRADA, TipoMovimiento.ENTRADA_PRODUCCION]:
        # Buscamos si el lote ya existe en el sistema
        lote = await Lote.find_one(
            Lote.numero_lote == movimiento.numero_lote,
            Lote.sku_articulo == movimiento.sku_articulo
        )
        
        if lote:
            # Si el artículo NO controla lotes (Lote Perpetuo), aplicamos Costo Promedio Ponderado
            if not articulo.controla_lotes:
                valor_actual = lote.cantidad_actual * lote.costo_unitario
                valor_nuevo = movimiento.cantidad * movimiento.costo_unitario
                nueva_cantidad = lote.cantidad_actual + movimiento.cantidad
                nuevo_costo = (valor_actual + valor_nuevo) / nueva_cantidad
                lote.costo_unitario = round(nuevo_costo, 4)
            else:
                # Si ya existía y es lote normal, actualizamos al costo más reciente
                lote.costo_unitario = movimiento.costo_unitario
                
            # Simplemente le sumamos la nueva cantidad
            lote.cantidad_actual += movimiento.cantidad
            await lote.save()
        else:
            # Si es un lote nuevo, lo creamos desde cero
            nuevo_lote = Lote(
                sku_articulo=movimiento.sku_articulo,
                numero_lote=movimiento.numero_lote,
                cantidad_inicial=movimiento.cantidad,
                cantidad_actual=movimiento.cantidad,
                costo_unitario=movimiento.costo_unitario,
                fecha_vencimiento=movimiento.fecha_vencimiento
            )
            await nuevo_lote.insert()
            
        # Sumamos al stock global del almacén
        articulo.stock_actual += movimiento.cantidad

    elif movimiento.tipo_movimiento in [TipoMovimiento.SALIDA_VENTA, TipoMovimiento.SALIDA_PRODUCCION]:
        # Para sacar inventario, el lote DEBE existir
        lote = await Lote.find_one(
            Lote.numero_lote == movimiento.numero_lote,
            Lote.sku_articulo == movimiento.sku_articulo
        )
        
        if not lote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El lote '{movimiento.numero_lote}' no está registrado."
            )
            
        if lote.cantidad_actual < movimiento.cantidad:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock insuficiente en el lote {movimiento.numero_lote}. Actual: {lote.cantidad_actual}"
            )
            
        # IMPORTANTE: Congelamos el costo unitario real del lote en el historial del movimiento
        movimiento.costo_unitario = lote.costo_unitario
        
        # Lógica diferenciada para precios de venta según el tipo de salida
        if movimiento.tipo_movimiento == TipoMovimiento.SALIDA_VENTA:
            # Si es venta comercial, respetamos precio manual (descuento) o asignamos el oficial
            if movimiento.precio_venta is None:
                movimiento.precio_venta = articulo.precio_venta
        else:
            # Si es salida a producción, no hay venta al público ni ingresos comerciales
            movimiento.precio_venta = None

        # Restamos del lote específico y del stock global
        lote.cantidad_actual -= movimiento.cantidad
        await lote.save()
        
        articulo.stock_actual -= movimiento.cantidad

    elif movimiento.tipo_movimiento == TipoMovimiento.AJUSTE:
        # El ajuste reemplaza la cantidad física exacta de un lote específico
        lote = await Lote.find_one(
            Lote.numero_lote == movimiento.numero_lote,
            Lote.sku_articulo == movimiento.sku_articulo
        )
        
        if not lote:
            raise HTTPException(status_code=404, detail="Lote no encontrado para el ajuste.")
            
        # Calculamos la diferencia para ajustar el stock global correctamente
        diferencia = movimiento.cantidad - lote.cantidad_actual
        
        lote.cantidad_actual = movimiento.cantidad
        await lote.save()
        
        articulo.stock_actual += diferencia

    # 3. Guardamos el Artículo y el registro histórico inmutable del Movimiento
    await articulo.save()
    await movimiento.insert()
    
    return movimiento

@router.get("/", response_model=list[Movimiento], status_code=status.HTTP_200_OK)
async def obtener_todos_los_movimientos():
    """
    Devuelve el historial completo de todos los movimientos registrados.
    (Ideal para auditorías globales).
    """
    # .sort(+Movimiento.fecha_registro) ordena del más antiguo al más reciente
    movimientos = await Movimiento.find_all().sort(+Movimiento.fecha_registro).to_list()
    return movimientos

@router.get("/{sku}", response_model=list[Movimiento], status_code=status.HTTP_200_OK)
async def obtener_movimientos_por_articulo(sku: str):
    """
    Devuelve el Kardex (historial de movimientos) de un artículo específico.
    """
    movimientos = await Movimiento.find(
        Movimiento.sku_articulo == sku
    ).sort(+Movimiento.fecha_registro).to_list()
    
    return movimientos

@router.post("/salida-automatica", status_code=status.HTTP_201_CREATED)
async def registrar_salida_fifo(peticion: PeticionSalidaFIFO):
    """
    Endpoint para salidas automatizadas (FIFO).
    Descuenta automáticamente del lote más antiguo disponible.
    Puede generar múltiples movimientos si la cantidad requiere tomar de varios lotes.
    """
    # 1. Validar que el tipo de movimiento sea correcto para una salida
    if peticion.tipo_movimiento not in [TipoMovimiento.SALIDA_VENTA, TipoMovimiento.SALIDA_PRODUCCION]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El tipo de movimiento debe ser una salida (OUT_SALE o OUT_PROD)."
        )
        
    if peticion.cantidad <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La cantidad debe ser mayor a cero."
        )

    # 2. Verificar Artículo y Stock Global
    articulo = await Articulo.find_one(Articulo.sku == peticion.sku_articulo)
    if not articulo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El artículo con SKU '{peticion.sku_articulo}' no existe."
        )
        
    if articulo.stock_actual < peticion.cantidad:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stock insuficiente. Solicitado: {peticion.cantidad}, Disponible: {articulo.stock_actual}"
        )
        
    # 3. Obtener lotes con stock, ordenados del más antiguo al más nuevo (+_id)
    lotes_disponibles = await Lote.find(
        Lote.sku_articulo == peticion.sku_articulo,
        Lote.cantidad_actual > 0
    ).sort("+_id").to_list()
    
    cantidad_restante = peticion.cantidad
    movimientos_generados = []
    
    # 4. Bucle FIFO: Consumir lotes en cascada
    for lote in lotes_disponibles:
        if cantidad_restante <= 0:
            break  # Ya cubrimos la cantidad solicitada
            
        # Determinamos cuánto podemos tomar de este lote específico
        cantidad_a_tomar = min(lote.cantidad_actual, cantidad_restante)
        
        # Descontamos del lote y guardamos
        lote.cantidad_actual -= cantidad_a_tomar
        await lote.save()
        
        # Definimos el precio de venta (solo aplica si es OUT_SALE)
        precio_v = articulo.precio_venta if peticion.tipo_movimiento == TipoMovimiento.SALIDA_VENTA else None
        
        # Creamos el registro del movimiento para este lote en particular
        nuevo_movimiento = Movimiento(
            sku_articulo=articulo.sku,
            numero_lote=lote.numero_lote,
            usuario=peticion.usuario,
            tipo_movimiento=peticion.tipo_movimiento,
            concepto=peticion.concepto,
            cantidad=cantidad_a_tomar,
            costo_unitario=lote.costo_unitario, # El costo se respeta según el lote
            precio_venta=precio_v,
            id_referencia=peticion.id_referencia
        )
        
        await nuevo_movimiento.insert()
        movimientos_generados.append(nuevo_movimiento)
        
        # Restamos lo que acabamos de tomar a nuestra meta
        cantidad_restante -= cantidad_a_tomar
        
    # 5. Actualizar el stock global del artículo
    articulo.stock_actual -= peticion.cantidad
    await articulo.save()
    
    return {
        "mensaje": f"Salida automática completada. Se solicitó {peticion.cantidad} y se descontó correctamente.",
        "lotes_afectados": len(movimientos_generados),
        "movimientos_generados": movimientos_generados
    }