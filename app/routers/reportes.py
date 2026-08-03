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

@router.get("/stock-bajo", status_code=status.HTTP_200_OK)
async def reporte_stock_bajo():
    """
    Devuelve los artículos cuyo stock actual está en o por debajo de su stock mínimo configurado.
    """
    todos = await Articulo.find_all().to_list()
    articulos_en_alerta = []

    for art in todos:
        if art.stock_actual <= art.stock_minimo:
            articulos_en_alerta.append({
                "sku": art.sku,
                "nombre": art.nombre,
                "stock_actual": art.stock_actual,
                "stock_minimo": art.stock_minimo,
                "deficit": art.stock_minimo - art.stock_actual,
                "estado": "CRÍTICO" if art.stock_actual == 0 else "REABASTECER"
            })

    return {
        "total_alertas": len(articulos_en_alerta),
        "articulos": articulos_en_alerta
    }


@router.get("/lotes-por-vencer", status_code=status.HTTP_200_OK)
async def reporte_lotes_por_vencer(dias_limite: int = Query(default=30, description="Días de anticipación para la alerta")):
    """
    Devuelve los lotes activos (con stock > 0) cuya fecha de vencimiento esté dentro de los próximos N días.
    """
    # Buscamos lotes con fecha_vencimiento no nula y con stock disponible
    lotes = await Lote.find(
        Lote.fecha_vencimiento != None,
        Lote.cantidad_actual > 0
    ).to_list()

    fecha_actual = datetime.now()
    lotes_en_riesgo = []

    for lote in lotes:
        try:
            # Asumiendo formato YYYY-MM-DD
            fecha_venc = datetime.strptime(lote.fecha_vencimiento, "%Y-%m-%d")
            dias_restantes = (fecha_venc - fecha_actual).days

            if dias_restantes <= dias_limite:
                lotes_en_riesgo.append({
                    "sku_articulo": lote.sku_articulo,
                    "numero_lote": lote.numero_lote,
                    "cantidad_actual": lote.cantidad_actual,
                    "costo_unitario": lote.costo_unitario,
                    "fecha_vencimiento": lote.fecha_vencimiento,
                    "dias_restantes": dias_restantes,
                    "estado": "VENCIDO" if dias_restantes < 0 else "POR_VENCER"
                })
        except (ValueError, TypeError):
            # En caso de que la fecha tenga otro formato o esté mal formateada
            continue

    # Ordenamos del más próximo a vencer al más lejano
    lotes_en_riesgo.sort(key=lambda x: x["dias_restantes"])

    return {
        "dias_anticipacion_evaluados": dias_limite,
        "total_lotes_en_riesgo": len(lotes_en_riesgo),
        "lotes": lotes_en_riesgo
    }