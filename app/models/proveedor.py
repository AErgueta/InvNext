import pymongo
from typing import Optional
from beanie import Document
from pydantic import Field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

class Proveedor(Document):
    razon_social: str
    nit_ci: Optional[str] = None  # NIT o Carnet de Identidad
    nombre_contacto: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    direccion: Optional[str] = None
    
    # --- DATOS BANCARIOS ---
    banco: Optional[str] = None
    cuenta_bancaria: Optional[str] = None
    
    activo: bool = True
    
    fecha_registro: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("America/La_Paz")))

    class Settings:
        name = "proveedores"
        indexes = [
            pymongo.IndexModel([("nit_ci", pymongo.ASCENDING)], unique=True, sparse=True),
            pymongo.IndexModel([("razon_social", pymongo.ASCENDING)], unique=True)
        ]