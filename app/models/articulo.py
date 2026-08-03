import pymongo
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any
from pydantic import Field, field_serializer
from beanie import Document

class Articulo(Document):
    sku: str
    nombre: str
    descripcion: Optional[str] = None
    
    stock_actual: float = 0.0
    
    # --- NUEVO CAMPO: UMBRAL DE ALERTA ---
    stock_minimo: float = 0.0
    
    # --- NUEVO CAMPO COMERCIAL ---
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