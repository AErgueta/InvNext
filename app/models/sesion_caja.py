from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
from pydantic import BaseModel, Field, field_serializer
from beanie import Document

# ==========================================
# 1. MODELO DE BASE DE DATOS (MONGODB)
# ==========================================
class SesionCaja(Document):
    caja_id: str
    sucursal_id: str
    usuario: str  # El username del cajero responsable
    
    monto_inicial: float
    monto_cierre_calculado: float = 0.0
    monto_cierre_real: float = 0.0
    diferencia: float = 0.0
    
    estado: str = "ABIERTA"  # Puede ser "ABIERTA" o "CERRADA"
    
    fecha_apertura: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("America/La_Paz")))
    fecha_cierre: Optional[datetime] = None

    @field_serializer("fecha_apertura", "fecha_cierre")
    def a_hora_local(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(ZoneInfo("America/La_Paz")).isoformat()

    class Settings:
        name = "sesiones_caja"


# ==========================================
# 2. ESQUEMAS DE ENTRADA (PYDANTIC)
# ==========================================
class AperturaCajaRequest(BaseModel):
    caja_id: str
    sucursal_id: str
    monto_inicial: float = Field(..., ge=0, description="El dinero base en caja al abrir")

class CierreCajaRequest(BaseModel):
    monto_cierre_real: float = Field(..., ge=0, description="El dinero físico contado por el cajero")
    confirmar_diferencia: bool = False