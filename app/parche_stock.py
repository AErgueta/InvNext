import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from datetime import datetime
from zoneinfo import ZoneInfo
    
from app.models.articulo import Articulo, StockAlmacen
from app.models.lote import Lote, StockLoteAlmacen
from app.models.traspaso import TraspasoInventario

async def ejecutar_parche():
    print("Cargando configuración de entorno...")
    load_dotenv()
    
    uri_mongo = os.getenv("URL_BASE_DATOS") or os.getenv("MONGODB_URL")
    
    if not uri_mongo:
        print("❌ Error: No se encontró la URL de MongoDB en el archivo .env")
        return

    print("🔌 Conectando a MongoDB Atlas...")
    cliente = AsyncIOMotorClient(uri_mongo)
    
    # ⚠️ ASEGÚRATE de que "invnext_db" sea el nombre exacto de tu base de datos en Atlas
    await init_beanie(
        database=cliente.invnext_db, 
        document_models=[Articulo, Lote, TraspasoInventario]
    )

    print("🔍 Buscando traspasos antiguos para corregir...")
    traspasos = await TraspasoInventario.find({"estado": {"$in": ["COMPLETADO", "COMPLETADO_CON_DISCREPANCIA"]}}).to_list()

    if not traspasos:
        print("No se encontraron traspasos para corregir.")
        return

    for traspaso in traspasos:
        print(f"\n--- 🛠️ Corrigiendo Traspaso: {traspaso.folio} ---")
        
        # 1. ORIGEN: Descontar de los Lotes
        for art in traspaso.articulos:
            sku = art.sku_articulo
            cantidad_enviada = art.cantidad
            origen = traspaso.almacen_origen_id

            lotes_origen = await Lote.find(Lote.sku_articulo == sku).to_list()
            if lotes_origen:
                lotes_origen.sort(key=lambda x: x.fecha_vencimiento if x.fecha_vencimiento else datetime.max.replace(tzinfo=ZoneInfo("America/La_Paz")))
                cant_restante = cantidad_enviada
                for lote in lotes_origen:
                    if cant_restante <= 0: break
                    stock_en_almacen = next((sl for sl in lote.stock_por_almacen if sl.codigo_almacen == origen), None)
                    if stock_en_almacen and stock_en_almacen.cantidad > 0:
                        descuento = min(cant_restante, stock_en_almacen.cantidad)
                        stock_en_almacen.cantidad -= descuento
                        cant_restante -= descuento
                        await lote.save()
                        print(f"  [-] Descontado {descuento} del lote {lote.numero_lote} en {origen}")

        # 2. DESTINO: Sumar existencias (CON ESCUDO PROTECTOR PARA TRASPASOS ANTIGUOS)
        # Si no hay detalle_recepcion, usamos los artículos originales
        lista_recepcion = traspaso.detalle_recepcion if traspaso.detalle_recepcion else traspaso.articulos

        for item in lista_recepcion:
            # Extraemos los datos dependiendo de si viene del detalle_recepcion o de articulos
            sku = getattr(item, 'sku_articulo', None)
            cantidad_recibida = getattr(item, 'cantidad_recibida', getattr(item, 'cantidad', 0))
            destino = traspaso.almacen_destino_id

            if cantidad_recibida > 0:
                # 2.A: Corregir Maestro de Artículos
                articulo = await Articulo.find_one(Articulo.sku == sku)
                if articulo:
                    stock_dest = next((s for s in articulo.stock_por_almacen if s.codigo_almacen == destino), None)
                    if not stock_dest:
                        articulo.stock_por_almacen.append(StockAlmacen(codigo_almacen=destino, cantidad=cantidad_recibida))
                        await articulo.save()
                        print(f"  [+] Añadido {cantidad_recibida} de {sku} a {destino} (Maestro Artículos)")

                # 2.B: Corregir Lotes del Destino
                lotes = await Lote.find(Lote.sku_articulo == sku).to_list()
                if lotes:
                    lotes.sort(key=lambda x: x.fecha_vencimiento if x.fecha_vencimiento else datetime.max.replace(tzinfo=ZoneInfo("America/La_Paz")))
                    lote_destino = lotes[0]
                    stock_lote_dest = next((sl for sl in lote_destino.stock_por_almacen if sl.codigo_almacen == destino), None)
                    if not stock_lote_dest:
                        lote_destino.stock_por_almacen.append(StockLoteAlmacen(codigo_almacen=destino, cantidad=cantidad_recibida))
                        await lote_destino.save()
                        print(f"  [+] Añadido {cantidad_recibida} de {sku} a {destino} (Lote: {lote_destino.numero_lote})")

    print("\n✅ ¡Todos los traspasos antiguos han sido sincronizados!")

if __name__ == "__main__":
    asyncio.run(ejecutar_parche())