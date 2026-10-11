from fastapi import APIRouter, status, Depends, HTTPException
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

# ==========================================
# NUEVO ENDPOINT: CONSULTA DE LOTE ESPECÍFICO
# ==========================================
@router.get("/{sku}/{numero_lote}", status_code=status.HTTP_200_OK)
async def obtener_lote_especifico(sku: str, numero_lote: str):
    """
    Verifica si un lote específico ya existe en el sistema.
    Ideal para autocompletar fechas de caducidad en el frontend.
    """
    lote = await Lote.find_one(Lote.sku_articulo == sku, Lote.numero_lote == numero_lote)
    
    if not lote:
        # Si no existe, devolvemos 404 para que el Frontend sepa que es un lote "fantasma"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Lote no encontrado. Es un lote nuevo."
        )
        
    return lote