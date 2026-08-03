from fastapi import APIRouter, status, HTTPException
from typing import List
from app.models.proveedor import Proveedor

router = APIRouter(
    prefix="/proveedores",
    tags=["Proveedores"]
)

@router.post("/", response_model=Proveedor, status_code=status.HTTP_201_CREATED)
async def crear_proveedor(proveedor: Proveedor):
    """Registra un nuevo proveedor en el sistema."""
    # Verificamos si ya existe el NIT o la Razón Social para evitar duplicados
    existe = await Proveedor.find_one(
        {"$or": [{"razon_social": proveedor.razon_social}, {"nit_ci": proveedor.nit_ci}]}
    )
    if existe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Ya existe un proveedor con esa Razón Social o NIT."
        )
    
    await proveedor.insert()
    return proveedor

@router.get("/", response_model=List[Proveedor], status_code=status.HTTP_200_OK)
async def listar_proveedores():
    """Devuelve la lista de todos los proveedores activos."""
    return await Proveedor.find(Proveedor.activo == True).to_list()