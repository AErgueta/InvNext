import pymongo
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from enum import Enum
from typing import Optional
from pydantic import Field, field_serializer
from beanie import Document

class TipoMovimiento(str, Enum):
    ENTRADA = "IN"    
    ENTRADA_PRODUCCION = "IN_PROD"    
    SALIDA_VENTA = "OUT_SALE"         
    SALIDA_PRODUCCION = "OUT_PROD"    
    AJUSTE = "ADJ"
    ENTRADA_DEVOLUCION = "IN_RETURN"
    ANULACION_SALIDA = "REV_OUT"
    
    # --- NUEVOS TIPOS PARA MULTI-ALMACÉN ---
    ENTRADA_TRASPASO = "IN_TRANS"     # Ingreso por traspaso desde otro almacén
    SALIDA_TRASPASO = "OUT_TRANS"     # Salida por traspaso hacia otro almacén

    # --- NUEVO TIPO PARA AJUSTE FINANCIERO ---
    REVALORIZACION = "ADJ_COST"       # Ajuste exclusivo de costo (cantidad 0)

class Movimiento(Document):
    sku_articulo: str
    
    # --- CAMPO OBLIGATORIO: ALMACÉN ---
    codigo_almacen: str 
    
    numero_lote: str  
    usuario: str
    
    tipo_movimiento: TipoMovimiento
    concepto: str 
    cantidad: float
    costo_unitario: float = 0.0
    
    # --- NUEVO CAMPO PARA GOBERNANZA / FLUJOS DE APROBACIÓN ---
    # Es obligatorio porque el usuario debe seleccionar manualmente el flujo
    flujo_trabajo_seleccionado: str = Field(..., description="Flujo de trabajo/aprobación seleccionado manualmente por el usuario")
    
    precio_venta: Optional[float] = None 
    
    fecha_vencimiento: Optional[str] = None 
    
    # --- CAMPO OPCIONAL: CONTRA-PARTE DEL TRASPASO ---
    almacen_contraparte: Optional[str] = None 
    
    id_referencia: Optional[str] = None 
    notas: Optional[str] = None
    
    fecha_registro: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("America/La_Paz")))
    
    # --- CANDADO DIGITAL ---
    estado: str = "PENDIENTE"

    @field_serializer("fecha_registro")
    def a_hora_local(self, dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo("America/La_Paz")).isoformat()

    class Settings:
        name = "movimientos"
        indexes = [
            pymongo.IndexModel([("sku_articulo", pymongo.ASCENDING)]),
            pymongo.IndexModel([("codigo_almacen", pymongo.ASCENDING)]), # Índice para búsquedas rápidas por almacén
            pymongo.IndexModel([("numero_lote", pymongo.ASCENDING)])
        ]