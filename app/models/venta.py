from datetime import datetime
from typing import List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field
from beanie import Document

# --- NUEVO: Condición de Pago ---
class CondicionPago(str, Enum):
    CONTADO = "CONTADO"
    CREDITO_15 = "CREDITO_15_DIAS"
    CREDITO_30 = "CREDITO_30_DIAS"

# --- ACTUALIZADO: Estados Financieros ---
class EstadoVenta(str, Enum):
    PENDIENTE = "PENDIENTE"
    POR_COBRAR = "POR_COBRAR"        # NUEVO: Mercadería entregada, pero el cliente debe el dinero
    PAGO_PARCIAL = "PAGO_PARCIAL"    # NUEVO: El cliente ha hecho abonos, pero aún debe una parte
    PAGADA = "PAGADA"
    CANCELADA = "CANCELADA"

class DetalleVenta(BaseModel):
    """Sub-modelo para guardar las líneas individuales del carrito"""
    sku_articulo: str
    nombre_articulo: str
    cantidad: float
    precio_unitario: float
    
    descuento_linea: float = 0.0 
    subtotal_linea: float 

class Venta(Document):
    """Modelo principal de la Orden de Venta"""
    folio: str
    cliente: str
    documento_cliente: Optional[str] = None
    
    # CORREGIDO: Se usa default_factory para obtener la hora real de la transacción
    fecha_registro: datetime = Field(default_factory=datetime.utcnow)
    
    # --- NUEVO CAMPO: Contado o Crédito ---
    condicion_pago: CondicionPago = Field(default=CondicionPago.CONTADO)
    
    articulos: List[DetalleVenta]
    
    subtotal_venta: float          
    descuento_global: float = 0.0  
    total_venta: float             
    
    # --- NUEVO CAMPO: El corazón de Cuentas por Cobrar ---
    saldo_pendiente: float = Field(default=0.0)
    
    estado: EstadoVenta = Field(default=EstadoVenta.PENDIENTE)
    referencia_movimiento_id: Optional[Union[str, List[str]]] = None

    class Settings:
        name = "ventas"