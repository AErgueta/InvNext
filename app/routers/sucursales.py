from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import List
from app.models.sucursal import Sucursal
from app.models.usuario import Usuario
from app.routers.auth import obtener_usuario_admin

router = APIRouter(prefix="/sucursales", tags=["Sucursales"])

# Esquema para actualizar (ya no incluye codigo_almacen)
class SucursalUpdate(BaseModel):
    codigo: str
    nombre: str
    direccion: str | None = None
    telefono: str | None = None

# Esquema para cambiar estado lógico
class EstadoSucursal(BaseModel):
    activa: bool

@router.post("/", status_code=status.HTTP_201_CREATED)
async def crear_sucursal(sucursal: Sucursal, admin: Usuario = Depends(obtener_usuario_admin)):
    existe = await Sucursal.find_one(Sucursal.codigo == sucursal.codigo)
    if existe:
        raise HTTPException(status_code=400, detail="El código de sucursal ya existe.")
    
    await sucursal.insert()
    return sucursal

@router.get("/")
async def listar_sucursales(admin: Usuario = Depends(obtener_usuario_admin)):
    """Lista todas las sucursales (activas e inactivas) para el panel de administración."""
    return await Sucursal.find_all().to_list()

@router.put("/{codigo}", status_code=status.HTTP_200_OK)
async def editar_sucursal(codigo: str, datos: SucursalUpdate, admin: Usuario = Depends(obtener_usuario_admin)):
    sucursal = await Sucursal.find_one(Sucursal.codigo == codigo)
    if not sucursal:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada.")
    
    if sucursal.codigo != datos.codigo:
        existe = await Sucursal.find_one(Sucursal.codigo == datos.codigo)
        if existe:
            raise HTTPException(status_code=400, detail="El nuevo código ya está en uso.")

    sucursal.codigo = datos.codigo
    sucursal.nombre = datos.nombre
    sucursal.direccion = datos.direccion
    sucursal.telefono = datos.telefono
    
    await sucursal.save()
    return sucursal

@router.patch("/{codigo}/estado", status_code=status.HTTP_200_OK)
async def cambiar_estado(codigo: str, estado: EstadoSucursal, admin: Usuario = Depends(obtener_usuario_admin)):
    sucursal = await Sucursal.find_one(Sucursal.codigo == codigo)
    if not sucursal:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada.")
    
    sucursal.activa = estado.activa
    await sucursal.save()
    return {"mensaje": "Estado actualizado correctamente."}