from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import List
from app.models.almacen import Almacen
from app.models.usuario import Usuario
from app.routers.auth import obtener_usuario_admin

router = APIRouter(prefix="/almacenes", tags=["Almacenes"])

class AlmacenUpdate(BaseModel):
    codigo: str
    nombre: str
    codigo_sucursal: str  # <-- Nuevo campo obligatorio
    descripcion: str | None = None
    direccion: str | None = None

class EstadoAlmacen(BaseModel):
    activo: bool

@router.post("/", status_code=status.HTTP_201_CREATED)
async def crear_almacen(almacen: Almacen, admin: Usuario = Depends(obtener_usuario_admin)):
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
async def listar_almacenes(admin: Usuario = Depends(obtener_usuario_admin)):
    """Devuelve TODOS los almacenes para el panel de administración (activos e inactivos)."""
    # Cambiamos para que traiga todos, así el admin puede ver los inactivos
    almacenes = await Almacen.find_all().to_list()
    return almacenes

@router.put("/{codigo}", status_code=status.HTTP_200_OK)
async def editar_almacen(codigo: str, datos: AlmacenUpdate, admin: Usuario = Depends(obtener_usuario_admin)):
    almacen = await Almacen.find_one(Almacen.codigo == codigo)
    if not almacen:
        raise HTTPException(status_code=404, detail="Almacén no encontrado.")
    
    if almacen.codigo != datos.codigo:
        existe = await Almacen.find_one(Almacen.codigo == datos.codigo)
        if existe:
            raise HTTPException(status_code=400, detail="El nuevo código ya está en uso.")

    almacen.codigo = datos.codigo
    almacen.nombre = datos.nombre
    almacen.codigo_sucursal = datos.codigo_sucursal  # <-- Guardar la relación
    almacen.descripcion = datos.descripcion
    almacen.direccion = datos.direccion
    
    await almacen.save()
    return almacen


@router.patch("/{codigo}/estado", status_code=status.HTTP_200_OK)
async def cambiar_estado(codigo: str, estado: EstadoAlmacen, admin: Usuario = Depends(obtener_usuario_admin)):
    almacen = await Almacen.find_one(Almacen.codigo == codigo)
    if not almacen:
        raise HTTPException(status_code=404, detail="Almacén no encontrado.")
    
    almacen.activo = estado.activo
    await almacen.save()
    return {"mensaje": "Estado actualizado correctamente."}