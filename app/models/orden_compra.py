import pymongo
from typing import List, Optional
from beanie import Document
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# --- ESTADO FÍSICO (ALMACÉN) ---
class EstadoOrden(str, Enum):
    PENDIENTE = "PENDIENTE"   # Esperando la mercancía
    RECEPCION_PARCIAL = "RECEPCION_PARCIAL"  # <--- ¡NUEVO ESTADO!
    COMPLETADA = "COMPLETADA" # La mercancía ingresó al almacén
    CANCELADA = "CANCELADA"   # Se anuló el pedido

# --- ESTADO FINANCIERO (CUENTAS POR PAGAR) ---
class EstadoPago(str, Enum):
    NO_PAGADO = "NO_PAGADO"
    PAGO_PARCIAL = "PAGO_PARCIAL"
    PAGADO = "PAGADO"

class ItemOrden(BaseModel):
    sku_articulo: str
    cantidad_solicitada: float
    cantidad_recibida: float = 0.0  # <--- ¡NUEVA VARIABLE! (Empieza en 0)
    costo_unitario_estimado: float

class OrdenCompra(Document):
    numero_orden: str
    proveedor_id: str  
    
    # Separamos los flujos
    estado: EstadoOrden = EstadoOrden.PENDIENTE
    estado_pago: EstadoPago = EstadoPago.NO_PAGADO
    
    # Control de pagos
    monto_total: float = 0.0       # Lo que suma la orden
    monto_pagado: float = 0.0      # Lo que ya le transferimos al proveedor
    
    items: List[ItemOrden]
    notas: Optional[str] = None
    
    fecha_emision: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("America/La_Paz")))
    fecha_actualizacion: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("America/La_Paz")))

    class Settings:
        name = "ordenes_compra"
        indexes = [
            pymongo.IndexModel([("numero_orden", pymongo.ASCENDING)], unique=True)
        ]