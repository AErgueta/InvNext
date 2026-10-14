import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.models.lote import Lote
from app.models.movimiento import Movimiento

async def ejecutar_parche_costos():
    print("Cargando configuración de entorno...")
    load_dotenv()
    
    uri_mongo = os.getenv("URL_BASE_DATOS") or os.getenv("MONGODB_URL")
    if not uri_mongo:
        print("❌ Error: No se encontró la URL de MongoDB en el archivo .env")
        return

    print("🔌 Conectando a MongoDB Atlas...")
    cliente = AsyncIOMotorClient(uri_mongo)
    
    await init_beanie(
        database=cliente.invnext_db, 
        document_models=[Lote, Movimiento]
    )

    print("🔍 Buscando movimientos de traspaso (OUT_TRANS, IN_TRANS)...")
    
    movimientos = await Movimiento.find({
        "tipo_movimiento": {"$in": ["OUT_TRANS", "IN_TRANS"]}
    }).to_list()

    if not movimientos:
        print("✅ No se encontraron movimientos de traspaso en el Kardex.")
        return

    corregidos = 0

    for mov in movimientos:
        costo_actual = getattr(mov, 'costo_unitario', 0.0)
        
        if not costo_actual or float(costo_actual) == 0.0:
            
            # ESTRATEGIA DEFINITIVA: Buscar el costo directamente en el Lote del artículo
            lote = await Lote.find_one(Lote.sku_articulo == mov.sku_articulo)
            
            costo_real = getattr(lote, 'costo_unitario', 0.0) if lote else 0.0
            
            if costo_real > 0:
                mov.costo_unitario = float(costo_real)
                await mov.save()
                corregidos += 1
                print(f"  [+] Corregido Kardex {mov.id_referencia} ({mov.tipo_movimiento}) para {mov.sku_articulo} -> Nuevo costo (desde Lote): ${costo_real}")
            else:
                print(f"  [!] Alerta: No se encontró costo en el Lote para {mov.sku_articulo}")

    print(f"\n✅ Proceso terminado. Se corrigieron los costos de {corregidos} movimientos.")

if __name__ == "__main__":
    asyncio.run(ejecutar_parche_costos())