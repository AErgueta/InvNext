document.addEventListener('DOMContentLoaded', cargarVencimientos);
document.getElementById('btn-refrescar-vencimientos').addEventListener('click', cargarVencimientos);

async function cargarVencimientos() {
    const tbody = document.getElementById('cuerpo-tabla-vencimientos');
    const diasLimite = document.getElementById('input-dias').value || 30;
    
    tbody.innerHTML = '<tr><td colspan="7">⏳ Escaneando lotes en riesgo...</td></tr>';

    try {
        const response = await fetch(`/reportes/lotes-por-vencer?dias_limite=${diasLimite}`);
        if (!response.ok) throw new Error("Error al consultar el radar de vencimientos");
        
        const data = await response.json();
        const lotes = data.lotes;
        
        if (lotes.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" style="padding: 30px; color: green; font-weight: bold;">
                        ✅ Todo fresco. No hay lotes próximos a vencer en los siguientes ${diasLimite} días.
                    </td>
                </tr>
            `;
            return;
        }

        let htmlFilas = "";

        lotes.forEach(lote => {
            let esVencido = lote.estado === 'VENCIDO';
            let claseBadge = esVencido ? 'badge-vencido' : 'badge-por-vencer';
            
            let textoDias = esVencido 
                ? `Vencido hace ${Math.abs(lote.dias_restantes)} días` 
                : `En ${lote.dias_restantes} días`;
            
            let colorDias = esVencido ? 'color: red; font-weight: bold;' : 'font-weight: bold;';
            
            let perdida = lote.cantidad_actual * lote.costo_unitario;

            htmlFilas += `
                <tr>
                    <!-- 1. SKU -->
                    <td style="font-weight: bold; font-size: 1.1em;">${lote.sku_articulo}</td>
                    
                    <!-- 2. Lote -->
                    <td style="font-weight: bold; color: #2980b9;">${lote.numero_lote}</td>
                    
                    <!-- 3. Estado -->
                    <td><span class="badge ${claseBadge}">${lote.estado}</span></td>
                    
                    <!-- 4. Tiempo Restante -->
                    <td style="${colorDias}">${textoDias}</td>
                    
                    <!-- 5. Fecha Límite -->
                    <td>${lote.fecha_vencimiento}</td>
                    
                    <!-- 6. Stock Actual -->
                    <td>${lote.cantidad_actual.toLocaleString('en-US')}</td>
                    
                    <!-- 7. Pérdida Potencial -->
                    <td style="color: #c0392b; font-weight: bold;">
                        $${perdida.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                    </td>
                </tr>
            `;
        });

        tbody.innerHTML = htmlFilas;

    } catch (error) {
        console.error("Error:", error);
        tbody.innerHTML = '<tr><td colspan="7" style="color: red;">Ocurrió un error al cargar el radar de vencimientos.</td></tr>';
    }
}