from beanie import Document  # O de donde estés importando Document en tu proyecto
from typing import Optional

class Almacen(Document):
    codigo: str               # Ej. "ALM-CENTRAL"
    nombre: str               # Ej. "Almacén Central"
    descripcion: Optional[str] = None
    direccion: Optional[str] = None
    activo: bool = True

    class Settings:
        name = "almacenes"    # Nombre de la colección en MongoDB