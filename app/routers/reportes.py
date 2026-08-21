from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, status, Query
from beanie.operators import In
from app.models.movimiento import Movimiento, TipoMovimiento
from app.models.articulo import Articulo
from app.models.lote import Lote

router = APIRouter(
    prefix="/reportes",
    tags=["Reportes Financieros y Alertas"]
)

@router.get("/utilidad", status_code=status.HTTP_200_OK)
async def calcular_reporte_utilidad():
    """
    Calcula el reporte financiero separando Ventas (OUT_SALE) y Consumos de Producción (OUT_PROD).
    """
    movimientos_salida = await Movimiento.find(
        In(Movimiento.tipo_movimiento, [TipoMovimiento.SALIDA_VENTA, TipoMovimiento.SALIDA_PRODUCCION])
    ).to_list()
    
    detalle_ventas = []
    detalle_produccion = []
    
    total_ingresos_ventas = 0.0
    total_costos_ventas = 0.0
    total_utilidad_ventas = 0.0
    total_costos_produccion = 0.0

    for mov in movimientos_salida:
        cantidad = mov.cantidad
        costo_u = mov.costo_unitario
        costo_linea = costo_u * cantidad

        if mov.tipo_movimiento == TipoMovimiento.SALIDA_VENTA:
            precio_v = mov.precio_venta if mov.precio_venta is not None else 0.0
            ingreso_linea = precio_v * cantidad
            utilidad_linea = ingreso_linea - costo_linea
            margen_porcentaje = ((precio_v - costo_u) / precio_v * 100) if precio_v > 0 else 0.0

            total_ingresos_ventas += ingreso_linea
            total_costos_ventas += costo_linea
            total_utilidad_ventas += utilidad_linea

            detalle_ventas.append({
                "sku": mov.sku_articulo,
                "lote": mov.numero_lote,
                "cantidad_vendida": cantidad,
                "precio_unitario_venta": precio_v,
                "costo_unitario_lote": costo_u,
                "ingreso_total": round(ingreso_linea, 2),
                "costo_total": round(costo_linea, 2),
                "utilidad_neta": round(utilidad_linea, 2),
                "margen_porcentaje": round(margen_porcentaje, 2),
                "fecha_venta": mov.fecha_registro
            })

        elif mov.tipo_movimiento == TipoMovimiento.SALIDA_PRODUCCION:
            total_costos_produccion += costo_linea

            detalle_produccion.append({
                "sku": mov.sku_articulo,
                "lote": mov.numero_lote,
                "cantidad_consumida": cantidad,
                "costo_unitario_lote": costo_u,
                "costo_total_produccion": round(costo_linea, 2),
                "concepto": mov.concepto,
                "fecha_consumo": mov.fecha_registro
            })

    return {
        "resumen_financiero": {
            "ventas": {
                "ingresos_totales": round(total_ingresos_ventas, 2),
                "costos_de_lo_vendido": round(total_costos_ventas, 2),
                "utilidad_neta_total": round(total_utilidad_ventas, 2)
            },
            "produccion": {
                "costo_total_materia_prima_consumida": round(total_costos_produccion, 2)
            }
        },
        "detalles": {
            "transacciones_ventas": detalle_ventas,
            "transacciones_produccion": detalle_produccion
        }
    }


# ==========================================
# NUEVOS ENDPOINTS: ALERTAS DE INVENTARIO
# ==========================================


@router.get("/lotes-por-vencer", status_code=status.HTTP_200_OK)
async def reporte_lotes_por_vencer(dias_limite: int = Query(default=30, description="Días de anticipación para la alerta")):
    """
    Devuelve los lotes activos (con stock > 0) cuya fecha de vencimiento esté dentro de los próximos N días.
    """
    # Buscamos lotes con stock > 0. 
    lotes = await Lote.find(Lote.cantidad_actual > 0).to_list()

    # Usamos zona horaria nula para evitar errores de resta con los ISODate de Mongo
    fecha_actual = datetime.now().replace(tzinfo=None)
    lotes_en_riesgo = []

    for lote in lotes:
        # Extraemos la fecha de forma segura por si el campo no existe en todos los lotes
        fecha_vencimiento_raw = getattr(lote, "fecha_vencimiento", None)
        
        if not fecha_vencimiento_raw:
            continue
            
        try:
            # Validamos si Mongo lo trajo como datetime (ISODate) o como texto
            if isinstance(fecha_vencimiento_raw, datetime):
                fecha_venc = fecha_vencimiento_raw.replace(tzinfo=None)
            else:
                # Cortamos a 10 caracteres por si trae horas en formato string
                fecha_venc = datetime.strptime(str(fecha_vencimiento_raw)[:10], "%Y-%m-%d")

            dias_restantes = (fecha_venc - fecha_actual).days

            if dias_restantes <= dias_limite:
                lotes_en_riesgo.append({
                    "sku_articulo": lote.sku_articulo,
                    "numero_lote": lote.numero_lote,
                    "cantidad_actual": lote.cantidad_actual,
                    "costo_unitario": lote.costo_unitario,
                    "fecha_vencimiento": fecha_venc.strftime("%Y-%m-%d"), # Estandarizamos texto limpio para el frontend
                    "dias_restantes": dias_restantes,
                    "estado": "VENCIDO" if dias_restantes < 0 else "POR_VENCER"
                })
        except Exception as e:
            # Si un lote tiene la fecha corrupta, lo saltamos en lugar de tumbar el servidor
            print(f"Error procesando fecha del lote {lote.numero_lote}: {e}")
            continue

    # Ordenamos del más próximo a vencer al más lejano
    lotes_en_riesgo.sort(key=lambda x: x["dias_restantes"])

    return {
        "dias_anticipacion_evaluados": dias_limite,
        "total_lotes_en_riesgo": len(lotes_en_riesgo),
        "lotes": lotes_en_riesgo
    }


@router.get("/stock-bajo", status_code=status.HTTP_200_OK)
async def reporte_stock_bajo():
    """
    Escanea el inventario y devuelve los artículos que alcanzaron su punto de reorden 
    o stock mínimo, evaluando de forma independiente cada almacén.
    """
    articulos = await Articulo.find_all().to_list()
    
    alertas = []
    for art in articulos:
        # Iteramos sobre cada almacén del artículo
        for stock_alm in art.stock_por_almacen:
            
            # Verificamos que tenga configurado un punto de reorden
            if stock_alm.punto_reorden is not None and stock_alm.punto_reorden > 0:
                
                # Evaluamos el stock local de ese almacén
                if stock_alm.cantidad <= stock_alm.punto_reorden:
                    if stock_alm.cantidad <= stock_alm.stock_minimo:
                        estado = "CRÍTICO" 
                    else:
                        estado = "REORDEN" 
                        
                    alertas.append({
                        "sku": art.sku,
                        "nombre": art.nombre,
                        "almacen": stock_alm.codigo_almacen,     # <--- AHORA ENVIAMOS EL ALMACÉN
                        "stock_actual": stock_alm.cantidad,      # <--- STOCK LOCAL
                        "punto_reorden": stock_alm.punto_reorden,
                        "stock_minimo": stock_alm.stock_minimo,
                        "estado_alerta": estado,
                        "diferencia_reorden": stock_alm.punto_reorden - stock_alm.cantidad
                    })
        
    # Ordenamos para mostrar primero las alertas con mayor falta de inventario
    alertas.sort(key=lambda x: x["diferencia_reorden"], reverse=True)
    
    return alertas

# ==========================================
# NUEVO ENDPOINT: RESUMEN DASHBOARD
# ==========================================

@router.get("/resumen-dashboard", status_code=status.HTTP_200_OK)
async def obtener_resumen_dashboard():
    """
    Agrega la información clave para mostrar en la pantalla principal (Dashboard).
    Devuelve los KPIs consolidados y la lista de los últimos movimientos.
    """
    # 1. Total de Artículos en el catálogo
    total_articulos = await Articulo.count()

    # 2. Valor del Inventario (Sumando: cantidad * costo de cada lote activo)
    lotes_activos = await Lote.find(Lote.cantidad_actual > 0).to_list()
    valor_inventario = sum((lote.cantidad_actual * lote.costo_unitario) for lote in lotes_activos)

    # 3. Alertas de Stock Bajo (Reutilizamos la lógica rápida de validación)
    articulos = await Articulo.find_all().to_list()
    alertas_stock = 0
    for art in articulos:
        for stock_alm in art.stock_por_almacen:
            if stock_alm.punto_reorden is not None and stock_alm.cantidad <= stock_alm.punto_reorden:
                alertas_stock += 1

    # 4. Movimientos Hoy
    hoy_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    movimientos_hoy = await Movimiento.find(Movimiento.fecha_registro >= hoy_inicio).count()

    # 5. Últimos 5 Movimientos para la tabla (Ordenados por fecha descendente)
    ultimos_docs = await Movimiento.find_all().sort(-Movimiento.fecha_registro).limit(5).to_list()
    
    lista_movimientos = []
    for mov in ultimos_docs:
        lista_movimientos.append({
            "tipo": mov.tipo_movimiento.value,
            "articulo": mov.sku_articulo,
            "cantidad": mov.cantidad,
            "fecha": mov.fecha_registro.strftime("%Y-%m-%d %H:%M")
        })

    return {
        "kpis": {
            "total_articulos": total_articulos,
            "valor_inventario": round(valor_inventario, 2),
            "alertas_stock": alertas_stock,
            "movimientos_hoy": movimientos_hoy
        },
        "ultimos_movimientos": lista_movimientos
    }