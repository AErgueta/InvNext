document.addEventListener('DOMContentLoaded', cargarAlertas);
document.getElementById('btn-refrescar-alertas').addEventListener('click', cargarAlertas);

async function cargarAlertas() {
    const tbody = document.getElementById('cuerpo-tabla-alertas');
    // Cambiamos a colspan 7 para que cubra toda la nueva tabla
    tbody.innerHTML = '<tr><td colspan="7">⏳ Escaneando inventario...</td></tr>';

    try {
        const response = await fetch('/reportes/stock-bajo');
        if (!response.ok) throw new Error("Error al consultar las alertas de stock");
        
        const alertas = await response.json();
        
        if (alertas.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" style="padding: 30px; color: green; font-weight: bold;">
                        ✅ Todo en orden. Ningún artículo requiere abastecimiento en este momento.
                    </td>
                </tr>
            `;
            return;
        }

        let htmlFilas = "";

        alertas.forEach(alerta => {
            let claseBadge = alerta.estado_alerta === 'CRÍTICO' ? 'badge-critico' : 'badge-reorden';
            let colorStock = alerta.estado_alerta === 'CRÍTICO' ? 'color: red; font-weight: bold;' : 'font-weight: bold;';

            htmlFilas += `
                <tr>
                    <!-- 1. SKU -->
                    <td style="font-weight: bold; font-size: 1.1em;">${alerta.sku}</td>
                    
                    <!-- 2. ALMACÉN (Esta es la celda que faltaba insertar) -->
                    <td style="font-weight: bold; color: #2980b9;">${alerta.almacen}</td> 
                    
                    <!-- 3. ESTADO -->
                    <td><span class="badge ${claseBadge}">${alerta.estado_alerta}</span></td>
                    
                    <!-- 4. STOCK ACTUAL -->
                    <td style="${colorStock}">${alerta.stock_actual.toLocaleString('en-US')}</td>
                    
                    <!-- 5. PUNTO REORDEN -->
                    <td>${alerta.punto_reorden.toLocaleString('en-US')}</td>
                    
                    <!-- 6. STOCK MÍNIMO -->
                    <td>${alerta.stock_minimo.toLocaleString('en-US')}</td>
                    
                    <!-- 7. FALTANTE -->
                    <td style="color: #c0392b; font-weight: bold;">
                        ⬇ ${alerta.diferencia_reorden.toLocaleString('en-US')}
                    </td>
                </tr>
            `;
        });

        tbody.innerHTML = htmlFilas;

    } catch (error) {
        console.error("Error:", error);
        // Cambiamos a colspan 7 aquí también
        tbody.innerHTML = '<tr><td colspan="7" style="color: red;">Ocurrió un error al cargar el radar de alertas.</td></tr>';
    }
}