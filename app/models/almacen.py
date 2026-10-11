from beanie import Document
from typing import Optional

class Almacen(Document):
    codigo: str               
    nombre: str               
    codigo_sucursal: Optional[str] = None      # <--- NUEVO: Enlace estructural con la sucursal
    descripcion: Optional[str] = None
    direccion: Optional[str] = None
    activo: bool = True

    class Settings:
        name = "almacenes"