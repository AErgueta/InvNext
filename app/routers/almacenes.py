from fastapi import APIRouter, HTTPException, status
from typing import List
from app.models.almacen import Almacen  # Ajusta la ruta de importación si es necesario

router = APIRouter(prefix="/almacenes", tags=["Almacenes"])

@router.post("/", status_code=status.HTTP_201_CREATED)
async def crear_almacen(almacen: Almacen):
    """Crea un nuevo almacén validando que el código no exista previamente."""
    existe = await Almacen.find_one(Almacen.codigo == almacen.codigo)
    if existe:
        raise HTTPException(
            status_code=400, 
            detail=f"Ya existe un almacén con el código {almacen.codigo}"
        )
    
    await almacen.insert()
    return almacen

@router.get("/")
async def listar_almacenes():
    """Devuelve la lista de todos los almacenes que están activos."""
    almacenes = await Almacen.find(Almacen.activo == True).to_list()
    return almacenes