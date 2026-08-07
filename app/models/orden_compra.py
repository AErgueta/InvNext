import pymongo
from typing import List, Optional
from beanie import Document
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from zoneinfo import ZoneInfo

class EstadoOrden(str, Enum):
    PENDIENTE = "PENDIENTE"
    RECEPCION_PARCIAL = "RECEPCION_PARCIAL"
    COMPLETADA = "COMPLETADA"
    CANCELADA = "CANCELADA"

class EstadoPago(str, Enum):
    NO_PAGADO = "NO_PAGADO"
    PAGO_PARCIAL = "PAGO_PARCIAL"
    PAGADO = "PAGADO"

class ItemOrden(BaseModel):
    sku_articulo: str
    cantidad_solicitada: float
    cantidad_recibida: float = 0.0
    costo_unitario_estimado: float

class OrdenCompra(Document):
    numero_orden: str
    proveedor_id: str  
    
    # --- NUEVOS CAMPOS DE TRAZABILIDAD ---
    usuario_creador: str  # Quién hizo la orden
    usuario_ultimo_receptor: Optional[str] = None  # Quién recibió (última vez)
    usuario_ultimo_pagador: Optional[str] = None   # Quién pagó (última vez)
    
    estado: EstadoOrden = EstadoOrden.PENDIENTE
    estado_pago: EstadoPago = EstadoPago.NO_PAGADO
    
    monto_total: float = 0.0       
    monto_pagado: float = 0.0      
    
    items: List[ItemOrden]
    notas: Optional[str] = None
    
    fecha_emision: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("America/La_Paz")))
    fecha_actualizacion: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("America/La_Paz")))

    class Settings:
        name = "ordenes_compra"
        indexes = [
            pymongo.IndexModel([("numero_orden", pymongo.ASCENDING)], unique=True)
        ]