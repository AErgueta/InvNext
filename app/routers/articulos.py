from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.articulo import Articulo
from app.models.movimiento import Movimiento
from app.models.lote import Lote
from app.models.almacen import Almacen 
from app.routers.auth import obtener_usuario_actual
from app.models.usuario import RolUsuario

# Creamos el enrutador con un prefijo para que todas las rutas empiecen con /articulos
router = APIRouter(
    prefix="/articulos",
    tags=["Artículos"],
    dependencies=[Depends(obtener_usuario_actual)] # <--- EL GUARDIA EN LA PUERTA
)

@router.post("/", response_model=Articulo, status_code=status.HTTP_201_CREATED)
async def crear_articulo(
    articulo: Articulo,
    usuario_actual = Depends(obtener_usuario_actual) # <--- CAPTURAMOS AL USUARIO
):
    # 0. Validamos que solo los administradores puedan crear nuevos productos
    if usuario_actual.rol != RolUsuario.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Solo los administradores pueden crear nuevos artículos."
        )

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
async def limpiar_base_de_datos(
    usuario_actual = Depends(obtener_usuario_actual) # <--- CAPTURAMOS AL USUARIO
):
    """
    ENDPOINT TEMPORAL PARA DESARROLLO:
    Borra todos los artículos, movimientos, lotes y almacenes de la base de datos.
    Solo accesible para Administradores.
    """
    # Validamos que un operador no pueda borrar la base de datos
    if usuario_actual.rol != RolUsuario.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Solo los administradores pueden vaciar la base de datos."
        )

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
async def actualizar_precio_venta(
    sku: str, 
    datos: ActualizarPrecio,
    usuario_actual = Depends(obtener_usuario_actual) # <--- CAPTURAMOS AL USUARIO
):
    """
    Actualiza exclusivamente el precio de venta global de un artículo en el catálogo.
    Solo accesible para Administradores.
    """
    # 0. Validamos que solo los administradores puedan cambiar precios
    if usuario_actual.rol != RolUsuario.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Solo los administradores pueden modificar precios."
        )

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
async def actualizar_articulo(
    sku: str, 
    update_data: ArticuloUpdate,
    usuario_actual = Depends(obtener_usuario_actual) # <--- CAPTURAMOS AL USUARIO
):
    """
    Actualiza parcialmente un artículo. Solo modifica los campos enviados en el JSON.
    El stock_actual y controla_lotes no se pueden modificar por esta vía.
    Solo accesible para Administradores.
    """
    # 0. Validamos que solo los administradores puedan modificar artículos
    if usuario_actual.rol != RolUsuario.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Solo los administradores pueden modificar la información del catálogo."
        )

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

@router.get("/{sku}/lotes", status_code=status.HTTP_200_OK)
async def obtener_lotes_por_almacen(sku: str, codigo_almacen: Optional[str] = None):
    """
    Devuelve los lotes activos de un artículo.
    Si se especifica el codigo_almacen, filtra solo el stock físico en esa ubicación.
    """
    articulo = await Articulo.find_one(Articulo.sku == sku)
    if not articulo:
        raise HTTPException(status_code=404, detail=f"El artículo '{sku}' no existe.")

    # Buscamos todos los lotes de este artículo que aún tengan saldo mayor a 0
    lotes_activos = await Lote.find(
        Lote.sku_articulo == sku,
        Lote.cantidad_actual > 0
    ).to_list()

    resultado_lotes = []

    for lote in lotes_activos:
        stock_filtrado = []
        
        # Revisamos las ubicaciones físicas de este lote
        for stock_alm in lote.stock_por_almacen:
            if stock_alm.cantidad > 0:
                # Si el usuario pidió un almacén específico, filtramos
                if codigo_almacen:
                    if stock_alm.codigo_almacen == codigo_almacen:
                        stock_filtrado.append(stock_alm)
                else:
                    stock_filtrado.append(stock_alm)
        
        # Solo agregamos el lote a la respuesta si realmente tiene stock en el almacén solicitado
        if stock_filtrado:
            resultado_lotes.append({
                "numero_lote": lote.numero_lote,
                "costo_unitario": lote.costo_unitario,
                "fecha_vencimiento": lote.fecha_vencimiento,
                "stock_fisico": stock_filtrado
            })

    # Calculamos el total rápido para el almacén
    total_en_almacen = sum(
        s.cantidad for l in resultado_lotes for s in l["stock_fisico"]
    )

    return {
        "sku": articulo.sku,
        "nombre": articulo.nombre,
        "almacen_consultado": codigo_almacen or "GLOBAL (Todos los almacenes)",
        "stock_total_en_consulta": total_en_almacen,
        "lotes_disponibles": resultado_lotes
    }

@router.get("/codigo-barras/{codigo}", status_code=status.HTTP_200_OK)
async def buscar_por_codigo_barras(codigo: str):
    """
    Busca un artículo instantáneamente escaneando su código de barras.
    Ideal para integración con hardware (Punto de Venta / Lector láser).
    """
    # Buscamos la coincidencia exacta gracias al índice que creamos
    articulo = await Articulo.find_one(Articulo.codigo_barras == codigo)
    
    if not articulo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró ningún artículo con el código de barras: {codigo}"
        )
        
    return articulo

@router.get("/buscar/{termino}", status_code=status.HTTP_200_OK)
async def buscar_articulo_pos(termino: str):
    """
    Busca artículos para el Punto de Venta usando Regex (Coincidencia parcial).
    Busca tanto por SKU como por Nombre, sin diferenciar mayúsculas/minúsculas.
    """
    # Buscamos usando una expresión regular sencilla
    # $regex: termino, $options: 'i' (case-insensitive)
    query = {
        "$or": [
            {"sku": {"$regex": termino, "$options": "i"}},
            {"nombre": {"$regex": termino, "$options": "i"}}
        ]
    }
    
    # Limitamos a 10 resultados para que la respuesta sea instantánea en caja
    resultados = await Articulo.find(query).limit(10).to_list()
    
    if not resultados:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontraron artículos con ese término."
        )
        
    return resultados