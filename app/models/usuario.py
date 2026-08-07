from beanie import Document
from typing import Optional
from enum import Enum

class RolUsuario(str, Enum):
    ADMIN = "ADMIN"
    OPERADOR = "OPERADOR"

class Usuario(Document):
    username: str
    hashed_password: str
    rol: RolUsuario = RolUsuario.OPERADOR
    codigo_almacen: Optional[str] = None  # Crucial: ¿A qué sucursal pertenece?
    activo: bool = True

    class Settings:
        name = "usuarios"