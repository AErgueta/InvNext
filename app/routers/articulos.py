from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.articulo import Articulo
from app.models.movimiento import Movimiento
from app.models.lote import Lote
from app.models.almacen import Almacen # --- NUEVA IMPORTACIÓN ---

# Creamos el enrutador con un prefijo para que todas las rutas empiecen con /articulos
router = APIRouter(
    prefix="/articulos",
    tags=["Artículos"]
)

@router.post("/", response_model=Articulo, status_code=status.HTTP_201_CREATED)
async def crear_articulo(articulo: Articulo):
    # 1. Validamos si el SKU ya existe en la base de datos
    existe = await Articulo.find_one(Articulo.sku == articulo.sku)
    
    if existe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El artículo con SKU '{articulo.sku}' ya existe en el inventario."
        )
    
    # 2. Si no existe, lo guardamos en MongoDB
    await articulo.insert()
    
    # 3. Retornamos el artículo recién creado
    return articulo

# --- ENDPOINT ACTUALIZADO PARA FRONTEND MULTI-ALMACÉN ---
@router.get("/", response_model=list[Articulo], status_code=status.HTTP_200_OK)
async def obtener_articulos(codigo_almacen: Optional[str] = None):
    # Buscamos todos los documentos
    articulos = await Articulo.find_all().to_list()
    
    # Si el frontend pide los datos para una sucursal en específico:
    if codigo_almacen:
        for art in articulos:
            # Filtramos la lista interna para que solo viaje el stock de esa sucursal
            stock_filtrado = [s for s in art.stock_por_almacen if s.codigo_almacen == codigo_almacen]
            art.stock_por_almacen = stock_filtrado
            
    return articulos

# --- ENDPOINT ACTUALIZADO ---
@router.delete("/reset", status_code=status.HTTP_200_OK)
async def limpiar_base_de_datos():
    """
    ENDPOINT TEMPORAL PARA DESARROLLO:
    Borra todos los artículos, movimientos, lotes y almacenes de la base de datos.
    """
    await Articulo.find_all().delete()
    await Movimiento.find_all().delete()
    await Lote.find_all().delete()
    await Almacen.find_all().delete() # Limpiamos también los almacenes
    
    return {"mensaje": "Base de datos completamente limpia y lista para la nueva arquitectura."}


@router.get("/{sku}/valor", status_code=status.HTTP_200_OK)
async def obtener_valor_inventario(sku: str):
    """
    Calcula el valor financiero total del inventario actual para un artículo,
    sumando el costo real de los lotes activos a nivel global.
    """
    articulo = await Articulo.find_one(Articulo.sku == sku)
    if not articulo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Artículo no encontrado"
        )

    # Buscamos solo los lotes de este artículo que tengan stock disponible
    lotes_activos = await Lote.find(
        Lote.sku_articulo == sku,
        Lote.cantidad_actual > 0
    ).to_list()

    valor_total_dinero = 0.0
    detalle_lotes = []

    # Calculamos el valor individual de cada lote
    for lote in lotes_activos:
        valor_lote = lote.cantidad_actual * lote.costo_unitario
        valor_total_dinero += valor_lote
        
        detalle_lotes.append({
            "numero_lote": lote.numero_lote,
            "cantidad_disponible": lote.cantidad_actual,
            "costo_unitario": lote.costo_unitario,
            "subtotal_dinero": valor_lote
        })

    # Calculamos el Costo Promedio Ponderado referencial
    costo_promedio = 0.0
    if articulo.stock_actual > 0:
        costo_promedio = valor_total_dinero / articulo.stock_actual

    return {
        "sku": articulo.sku,
        "nombre": articulo.nombre,
        "stock_total_unidades": articulo.stock_actual,
        "valor_total_inventario": round(valor_total_dinero, 2),
        "costo_promedio_referencial": round(costo_promedio, 2),
        "desglose_por_lote": detalle_lotes
    }

# 1. Creamos el esquema de validación para la petición
class ActualizarPrecio(BaseModel):
    precio_venta: float = Field(..., gt=0, description="El nuevo precio de venta al público (debe ser mayor a 0)")

# 2. Creamos el endpoint PUT
@router.put("/{sku}/precio", response_model=Articulo, status_code=status.HTTP_200_OK)
async def actualizar_precio_venta(sku: str, datos: ActualizarPrecio):
    """
    Actualiza exclusivamente el precio de venta global de un artículo en el catálogo.
    """
    articulo = await Articulo.find_one(Articulo.sku == sku)
    
    if not articulo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El artículo con SKU '{sku}' no existe."
        )
        
    # Actualizamos el precio
    articulo.precio_venta = datos.precio_venta
    
    # Buena práctica: dejamos constancia de cuándo se cambió el precio por última vez
    articulo.fecha_actualizacion = datetime.now(ZoneInfo("America/La_Paz"))
    
    await articulo.save()
    
    return articulo

# 1. Creamos un esquema de validación solo para los campos que se pueden editar
class ArticuloUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    stock_minimo: Optional[float] = None
    precio_venta: Optional[float] = None
    metadatos: Optional[Dict[str, Any]] = None

# 2. Creamos el endpoint PATCH
@router.patch("/{sku}", response_model=Articulo, status_code=status.HTTP_200_OK)
async def actualizar_articulo(sku: str, update_data: ArticuloUpdate):
    """
    Actualiza parcialmente un artículo. Solo modifica los campos enviados en el JSON.
    El stock_actual y controla_lotes no se pueden modificar por esta vía.
    """
    articulo = await Articulo.find_one(Articulo.sku == sku)
    
    if not articulo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"El artículo con SKU '{sku}' no existe."
        )
    
    # Extraemos solo los datos que el usuario realmente envió en el JSON
    datos_a_actualizar = update_data.model_dump(exclude_unset=True)
    
    # Aplicamos los cambios al objeto de base de datos
    for key, value in datos_a_actualizar.items():
        setattr(articulo, key, value)
        
    # Guardamos los cambios
    await articulo.save()
    
    return articulo