from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
from pydantic import BaseModel, Field, field_serializer
from beanie import Document, Indexed
import pymongo

class Sucursal(Document):
    codigo: str  # Ej. "SUC-CENTRAL", "SUC-NORTE"
    nombre: str                         # Ej. "Sucursal Central", "Sucursal Av. Banzer"
    codigo_almacen: str                 # Ej. "ALM-CENTRAL", "ALM-NORTE" (Vínculo con inventario)
    
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    activa: bool = Field(default=True, description="Controla el borrado lógico")
    
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("America/La_Paz")))

    @field_serializer("fecha_creacion")
    def a_hora_local(self, dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(ZoneInfo("America/La_Paz")).isoformat()

    class Settings:
        name = "sucursales"
        indexes = [
            pymongo.IndexModel([("codigo", pymongo.ASCENDING)], unique=True)
        ]