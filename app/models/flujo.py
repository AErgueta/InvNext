from typing import List, Optional
from datetime import datetime
from beanie import Document
from pydantic import BaseModel, Field

class PasoFlujo(BaseModel):
    orden: int = Field(..., description="Número de secuencia del paso (1, 2, 3...)")
    nombre_paso: str = Field(..., description="Nombre de la etapa (ej. Solicitado, Revisión, Aprobado)")
    rol_requerido: str = Field(default="ADMIN", description="Rol necesario para autorizar este paso")
    completado: bool = Field(default=False)
    fecha_aprobacion: Optional[datetime] = None
    aprobado_por: Optional[str] = Field(default=None, description="Username o ID del usuario que autorizó")

class FlujoGobernanza(Document):
    """
    Representa una plantilla o definición de un flujo de aprobación dinámico.
    """
    codigo_flujo: str = Field(..., unique=True, description="Identificador único ej. FLUJO-SALIDA-ESPECIAL")
    nombre: str = Field(..., description="Nombre descriptivo del flujo")
    descripcion: Optional[str] = None
    pasos: List[PasoFlujo] = Field(..., description="Lista ordenada de los pasos que componen el flujo")
    activo: bool = Field(default=True)

    class Settings:
        name = "flujos_gobernanza"

class InstanciaTracking(Document):
    """
    Representa el seguimiento (tracking) vivo de una operación específica 
    que está pasando por un flujo de gobernanza seleccionado por el usuario.
    """
    referencia_id: str = Field(..., description="ID del movimiento, lote u orden asociada")
    codigo_flujo: str = Field(..., description="El flujo que el usuario decidió aplicar")
    pasos_actuales: List[PasoFlujo] = Field(..., description="Copia de los pasos y su estado de avance")
    indice_paso_actual: int = Field(default=0, description="Índice del paso que está pendiente de aprobación")
    estado_general: str = Field(default="EN_PROCESO", description="EN_PROCESO, COMPLETADO o RECHAZADO")
    fecha_creacion: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "instancias_tracking"