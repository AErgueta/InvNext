document.addEventListener('DOMContentLoaded', cargarAlertas);
document.getElementById('btn-refrescar-alertas').addEventListener('click', cargarAlertas);

async function cargarAlertas() {
    const tbody = document.getElementById('cuerpo-tabla-alertas');
    tbody.innerHTML = '<tr><td colspan="6">⏳ Escaneando inventario...</td></tr>';

    try {
        const response = await fetch('/reportes/stock-bajo');
        if (!response.ok) throw new Error("Error al consultar las alertas de stock");
        
        const alertas = await response.json();
        
        if (alertas.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" style="padding: 30px; color: green; font-weight: bold;">
                        ✅ Todo en orden. Ningún artículo requiere abastecimiento en este momento.
                    </td>
                </tr>
            `;
            return;
        }

        let htmlFilas = "";

        alertas.forEach(alerta => {
            // Lógica para asignar el color de la etiqueta
            let claseBadge = alerta.estado_alerta === 'CRÍTICO' ? 'badge-critico' : 'badge-reorden';
            
            // Resaltar en rojo también el número del stock actual si es crítico
            let colorStock = alerta.estado_alerta === 'CRÍTICO' ? 'color: red; font-weight: bold;' : 'font-weight: bold;';

            htmlFilas += `
                <tr>
                    <td style="font-weight: bold; font-size: 1.1em;">${alerta.sku}</td>
                    <td><span class="badge ${claseBadge}">${alerta.estado_alerta}</span></td>
                    <td style="${colorStock}">${alerta.stock_actual.toLocaleString('en-US')}</td>
                    <td>${alerta.punto_reorden.toLocaleString('en-US')}</td>
                    <td>${alerta.stock_minimo.toLocaleString('en-US')}</td>
                    <td style="color: #c0392b; font-weight: bold;">
                        ⬇ ${alerta.diferencia_reorden.toLocaleString('en-US')}
                    </td>
                </tr>
            `;
        });

        tbody.innerHTML = htmlFilas;

    } catch (error) {
        console.error("Error:", error);
        tbody.innerHTML = '<tr><td colspan="6" style="color: red;">Ocurrió un error al cargar el radar de alertas.</td></tr>';
    }
}