from typing import List, Optional
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from enum import Enum
from beanie import Document
from pydantic import BaseModel, Field

class EstadoTraspaso(str, Enum):
    EN_TRANSITO = "EN_TRANSITO"
    COMPLETADO = "COMPLETADO"
    COMPLETADO_CON_DISCREPANCIA = "COMPLETADO_CON_DISCREPANCIA"  # <-- NUEVO
    CANCELADO = "CANCELADO"

# El detalle de las cajas que van dentro del camión
class DetalleTraspaso(BaseModel):
    sku_articulo: str
    nombre_articulo: str
    cantidad: float

# ==========================================
# NUEVOS SCHEMAS PARA LA RECEPCIÓN INTERACTIVA
# ==========================================
class ArticuloRecibidoReq(BaseModel):
    sku_articulo: str
    cantidad_esperada: float
    cantidad_recibida: float
    observaciones: Optional[str] = ""

class RecepcionTraspasoReq(BaseModel):
    flujo_trabajo_seleccionado: str
    articulos_recibidos: List[ArticuloRecibidoReq]

class DetalleRecepcion(BaseModel):
    sku_articulo: str
    cantidad_esperada: float
    cantidad_recibida: float
    observaciones: Optional[str] = ""
# ==========================================

# La Boleta de Despacho Global
class TraspasoInventario(Document):
    folio: str
    estado: EstadoTraspaso = EstadoTraspaso.EN_TRANSITO
    
    almacen_origen_id: str
    almacen_destino_id: str
    
    usuario_envia: str  
    usuario_recibe: Optional[str] = None  # Se llena cuando el destino confirma
    
    fecha_envio: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("America/La_Paz")))
    fecha_recepcion: Optional[datetime] = None
    
    articulos: List[DetalleTraspaso]
    
    # NUEVO: Guarda la auditoría de discrepancias (qué llegó realmente vs qué se esperaba)
    detalle_recepcion: Optional[List[DetalleRecepcion]] = None
    
    notas: Optional[str] = None

    class Settings:
        name = "traspasos"