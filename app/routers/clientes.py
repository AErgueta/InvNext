from typing import Optional, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.models.cliente import Cliente

router = APIRouter(prefix="/clientes", tags=["Clientes"])

# ==========================================
# ESQUEMA DE ENTRADA
# ==========================================
class NuevoClienteRequest(BaseModel):
    nombre_razon_social: str
    documento_identidad: str
    correo: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None

# ==========================================
# ENDPOINT: CREAR CLIENTE
# ==========================================
@router.post("/", status_code=status.HTTP_201_CREATED)
async def registrar_cliente(request: NuevoClienteRequest):
    """
    Registra un nuevo cliente en la base de datos.
    Valida que el NIT o Documento no esté duplicado para evitar inconsistencias.
    """
    cliente_existente = await Cliente.find_one(
        Cliente.documento_identidad == request.documento_identidad
    )
    
    if cliente_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un cliente con el documento: {request.documento_identidad}"
        )
        
    nuevo_cliente = Cliente(
        nombre_razon_social=request.nombre_razon_social,
        documento_identidad=request.documento_identidad,
        correo=request.correo,
        telefono=request.telefono,
        direccion=request.direccion
    )
    
    await nuevo_cliente.insert()
    return {"mensaje": "Cliente registrado exitosamente", "cliente": nuevo_cliente}

# ==========================================
# ENDPOINT: BUSCAR POR NIT / CI (Para el Frontend)
# ==========================================
@router.get("/buscar/{documento}", status_code=status.HTTP_200_OK)
async def buscar_cliente_por_documento(documento: str):
    """
    Busca un cliente por su NIT o CI. 
    Ideal para autocompletar el nombre en la vista de caja.
    """
    cliente = await Cliente.find_one(Cliente.documento_identidad == documento)
    
    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no registrado."
        )
        
    return cliente

# ==========================================
# ENDPOINT: LISTAR TODOS
# ==========================================
@router.get("/", response_model=List[Cliente], status_code=status.HTTP_200_OK)
async def listar_clientes():
    """
    Obtiene la lista de todos los clientes registrados.
    Útil para mostrar una tabla de administración en el frontend.
    """
    clientes = await Cliente.find_all().to_list()
    return clientes