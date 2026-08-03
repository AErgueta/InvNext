import pymongo
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional
from pydantic import Field, field_serializer  # <--- Importamos field_serializer
from beanie import Document

class Lote(Document):
    sku_articulo: str
    numero_lote: str
    
    cantidad_inicial: float
    cantidad_actual: float
    
    costo_unitario: float = 0.0
    fecha_vencimiento: Optional[str] = None
    
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("America/La_Paz")))

    # --- NUEVO INTERCEPTOR ---
    @field_serializer("fecha_creacion")
    def a_hora_local(self, dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo("America/La_Paz")).isoformat()

    class Settings:
        name = "lotes"
        indexes = [
            pymongo.IndexModel([("sku_articulo", pymongo.ASCENDING)]),
            pymongo.IndexModel([("numero_lote", pymongo.ASCENDING)], unique=True)
        ]