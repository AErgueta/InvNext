from fastapi import APIRouter, status, Depends
from app.models.lote import Lote
from app.routers.auth import obtener_usuario_actual

router = APIRouter(
    prefix="/lotes",
    tags=["Lotes"],
    dependencies=[Depends(obtener_usuario_actual)]
)

@router.get("/", response_model=list[Lote], status_code=status.HTTP_200_OK)
async def obtener_todos_los_lotes():
    """Devuelve la lista completa de todos los lotes en el almacén."""
    lotes = await Lote.find_all().to_list()
    return lotes

@router.get("/{sku}", response_model=list[Lote], status_code=status.HTTP_200_OK)
async def obtener_lotes_por_articulo(sku: str):
    """Devuelve únicamente los lotes asociados a un SKU específico."""
    lotes = await Lote.find(Lote.sku_articulo == sku).to_list()
    return lotes