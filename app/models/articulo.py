import pymongo
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_serializer
from beanie import Document

# --- NUEVA CLASE PARA MULTI-ALMACÉN ---
# Usamos BaseModel porque esto irá incrustado dentro de la colección de Artículos
class StockAlmacen(BaseModel):
    codigo_almacen: str
    cantidad: float = 0.0
    ubicacion: Optional[str] = None  # Ej. "Estante A, Fila 2"

class Articulo(Document):
    sku: str
    nombre: str
    descripcion: Optional[str] = None
    
    # Mantenemos stock_actual como el Total Global consolidado para no romper código antiguo
    stock_actual: float = 0.0
    
    # --- NUEVO CAMPO: INVENTARIO DESGLOSADO POR ALMACÉN ---
    stock_por_almacen: List[StockAlmacen] = Field(default_factory=list)
    
    # --- CAMPOS ORIGINALES CONSERVADOS ---
    stock_minimo: float = 0.0
    precio_venta: float = 0.0 
    controla_lotes: bool = True 
    metadatos: Dict[str, Any] = Field(default_factory=dict)
    
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("America/La_Paz")))
    fecha_actualizacion: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("America/La_Paz")))

    @field_serializer("fecha_creacion", "fecha_actualizacion")
    def a_hora_local(self, dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo("America/La_Paz")).isoformat()

    class Settings:
        name = "articulos"
        indexes = [
            pymongo.IndexModel([("sku", pymongo.ASCENDING)], unique=True)
        ]