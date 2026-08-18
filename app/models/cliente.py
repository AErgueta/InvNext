from typing import Annotated, Optional
from datetime import datetime
from beanie import Document, Indexed

class Cliente(Document):
    nombre_razon_social: str
    
    # Hacemos el documento indexado y único para búsquedas ultrarrápidas desde el frontend
    documento_identidad: Annotated[str, Indexed(unique=True)]  # NIT, CI, RUT, etc.
    
    correo: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    
    # Límite de crédito opcional para futuras implementaciones
    limite_credito: float = 0.0
    
    fecha_registro: datetime = datetime.now()

    class Settings:
        name = "clientes"