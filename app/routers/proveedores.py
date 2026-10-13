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


@router.put("/{proveedor_id}", response_model=Proveedor, status_code=status.HTTP_200_OK)
async def actualizar_proveedor(proveedor_id: str, datos_actualizados: Proveedor):
    """Actualiza los datos de un proveedor existente."""
    from bson import ObjectId
    
    proveedor = await Proveedor.get(proveedor_id)
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado.")
    
    # Verificamos que el nuevo NIT o Razón Social no choquen con OTRO proveedor distinto
    existe = await Proveedor.find_one(
        {"$or": [{"razon_social": datos_actualizados.razon_social}, {"nit_ci": datos_actualizados.nit_ci}], 
         "_id": {"$ne": ObjectId(proveedor_id)}}
    )
    if existe:
        raise HTTPException(status_code=400, detail="Ya existe OTRO proveedor con esa Razón Social o NIT.")
    
    # Actualizamos los campos
    proveedor.razon_social = datos_actualizados.razon_social
    proveedor.nit_ci = datos_actualizados.nit_ci
    proveedor.nombre_contacto = datos_actualizados.nombre_contacto
    proveedor.telefono = datos_actualizados.telefono
    proveedor.email = datos_actualizados.email
    
    await proveedor.save()
    return proveedor