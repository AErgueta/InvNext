from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
from pydantic import BaseModel, Field, field_serializer
from beanie import Document, Indexed
import pymongo

class Caja(Document):
    codigo: str  # Ej. "CAJA-01-CENTRAL", "CAJA-02-NORTE"
    nombre: str                         # Ej. "Caja Principal", "Caja Rápida 2"
    codigo_sucursal: str                # Vínculo directo con la Sucursal (codigo)
    
    activa: bool = Field(default=True)
    en_uso: bool = Field(default=False, description="Indica si hay una sesión de caja abierta actualmente")
    
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("America/La_Paz")))

    @field_serializer("fecha_creacion")
    def a_hora_local(self, dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(ZoneInfo("America/La_Paz")).isoformat()

    class Settings:
        name = "cajas"
        indexes = [
            pymongo.IndexModel([("codigo", pymongo.ASCENDING)], unique=True),
            pymongo.IndexModel([("codigo_sucursal", pymongo.ASCENDING)])
        ]