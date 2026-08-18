from beanie import Document
from pydantic import Field
from datetime import datetime
from enum import Enum
from typing import Optional

class TipoTransaccionCxC(str, Enum):
    CARGO = "CARGO"   # Aumenta la deuda (Cuando se despacha una venta a crédito)
    ABONO = "ABONO"   # Disminuye la deuda (Cuando el cliente trae dinero)

class CuentaCorriente(Document):
    # --- Datos Desnormalizados para lectura ultrarrápida ---
    documento_cliente: str           
    cliente: str                     # ¡Tu sugerencia! Evita cruzar colecciones
    venta_id: str                    
    folio_venta: str                 # Facilita la vista en el frontend
    # -------------------------------------------------------
    
    tipo: TipoTransaccionCxC         
    monto: float                     
    concepto: str                    
    usuario: str                     
    recibo_id: Optional[str] = None  
    fecha_registro: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "cuenta_corriente"