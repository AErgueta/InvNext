import pymongo
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional, List
from pydantic import BaseModel, Field, field_serializer
from beanie import Document

# --- NUEVA CLASE PARA DISTRIBUCIÓN DEL LOTE ---
class StockLoteAlmacen(BaseModel):
    codigo_almacen: str
    cantidad: float = 0.0

class Lote(Document):
    sku_articulo: str
    numero_lote: str
    
    cantidad_inicial: float
    cantidad_actual: float  # Mantenemos el total global del lote
    
    # --- NUEVO CAMPO: DESGLOSE FÍSICO POR ALMACÉN ---
    stock_por_almacen: List[StockLoteAlmacen] = Field(default_factory=list)
    
    costo_unitario: float = 0.0
    fecha_vencimiento: Optional[str] = None
    
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("America/La_Paz")))

    # --- INTERCEPTOR ---
    @field_serializer("fecha_creacion")
    def a_hora_local(self, dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo("America/La_Paz")).isoformat()

    class Settings:
        name = "lotes"
        indexes = [
            # PRO TIP: Índice compuesto único. 
            # Garantiza que no se repita el lote para el MISMO artículo, 
            # pero permite que distintos proveedores usen el "LOTE-001" en diferentes productos.
            pymongo.IndexModel(
                [("sku_articulo", pymongo.ASCENDING), ("numero_lote", pymongo.ASCENDING)], 
                unique=True
            )
        ]