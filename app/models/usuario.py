from beanie import Document
from typing import Optional
from enum import Enum

class RolUsuario(str, Enum):
    ADMIN = "ADMIN"
    OPERADOR = "OPERADOR"
    # Opcional: Podrías agregar un rol específico de cajero si lo ves necesario
    CAJERO = "CAJERO" 

class Usuario(Document):
    username: str
    hashed_password: str
    rol: RolUsuario = RolUsuario.OPERADOR
    
    # --- CAMPOS DE ASIGNACIÓN OPERATIVA ---
    sucursal_id: Optional[str] = None
    caja_id: Optional[str] = None
    almacen_id: Optional[str] = None  # Sustituye a codigo_almacen para mantener el estándar
    
    activo: bool = True

    class Settings:
        name = "usuarios"