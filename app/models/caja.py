from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional
from pydantic import Field, field_serializer
from beanie import Document
import pymongo

class Caja(Document):
    codigo: str  # Ej. "CAJA-01-CENTRAL"
    nombre: str                         # Ej. "Caja Mostrador 1"
    codigo_sucursal: str                # Vínculo con la Sucursal
    codigo_almacen: Optional[str] = None
    
    activa: bool = Field(default=True)
    en_uso: bool = Field(default=False, description="Indica si hay una sesión de caja abierta actualmente")
    
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("America/La_Paz")))

    @field_serializer("fecha_creacion")
    def a_hora_local(self, dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo("America/La_Paz")).isoformat()

    class Settings:
        name = "cajas"
        indexes = [
            pymongo.IndexModel([("codigo", pymongo.ASCENDING)], unique=True),
            pymongo.IndexModel([("codigo_sucursal", pymongo.ASCENDING)]),
            pymongo.IndexModel([("codigo_almacen", pymongo.ASCENDING)])
        ]