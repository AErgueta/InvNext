document.addEventListener('DOMContentLoaded', cargarVencimientos);
document.getElementById('form-filtro-vencimientos').addEventListener('submit', (e) => {
    e.preventDefault();
    cargarVencimientos();
});

// Función global para obtener el token
function obtenerToken() {
    return localStorage.getItem('erp_token');
}

async function cargarVencimientos() {
    const tbody = document.getElementById('cuerpo-tabla-vencimientos');
    const diasLimite = document.getElementById('input-dias').value || 30;
    
    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4">⏳ Analizando fechas de caducidad...</td></tr>';

    try {
        const token = obtenerToken();
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

        // Pasamos el parámetro dias_limite al endpoint
        const response = await fetch(`/reportes/lotes-por-vencer?dias_limite=${diasLimite}`, { headers });
        
        if (response.status === 401) {
            window.location.href = '/vistas/login';
            return;
        }
        
        if (!response.ok) throw new Error("Error al consultar los vencimientos");
        
        const data = await response.json();
        const lotes = data.lotes; // Tu backend devuelve un objeto con la llave "lotes"
        
        if (lotes.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center py-5 text-success">
                        <i class="bi bi-shield-check fs-3 d-block mb-2"></i>
                        <strong>Inventario Seguro</strong><br>
                        No hay lotes que expiren en los próximos ${diasLimite} días.
                    </td>
                </tr>
            `;
            return;
        }

        let htmlFilas = "";

        lotes.forEach(lote => {
            let colorFila = "";
            let badgeHtml = "";
            let iconoDias = "";

            // Semáforo FEFO
            if (lote.dias_restantes < 0) {
                // Vencido
                colorFila = "background-color: #fff5f5;"; 
                badgeHtml = '<span class="badge bg-danger">VENCIDO</span>';
                iconoDias = '<i class="bi bi-x-circle-fill text-danger me-1"></i>';
            } else if (lote.dias_restantes <= 15) {
                // Riesgo Alto (15 días o menos)
                colorFila = "background-color: #fffdf5;"; 
                badgeHtml = '<span class="badge bg-warning text-dark">CRÍTICO</span>';
                iconoDias = '<i class="bi bi-exclamation-triangle-fill text-warning me-1"></i>';
            } else {
                // Riesgo Medio
                badgeHtml = '<span class="badge bg-info text-dark">PRÓXIMO</span>';
                iconoDias = '<i class="bi bi-info-circle-fill text-info me-1"></i>';
            }

            htmlFilas += `
                <tr style="${colorFila}">
                    <td class="text-start align-middle fw-bold">${lote.sku_articulo}</td>
                    <td class="text-start align-middle fw-semibold text-primary">
                        <i class="bi bi-box-seam me-1"></i>${lote.numero_lote}
                    </td>
                    <td class="text-center align-middle fw-bold">${lote.cantidad_actual.toLocaleString('en-US')}</td>
                    <td class="text-center align-middle text-muted">$${lote.costo_unitario.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                    <td class="text-center align-middle fw-bold">${lote.fecha_vencimiento}</td>
                    <td class="text-center align-middle fw-bold">
                        ${iconoDias} ${lote.dias_restantes} días
                    </td>
                    <td class="text-center align-middle">${badgeHtml}</td>
                </tr>
            `;
        });

        tbody.innerHTML = htmlFilas;

    } catch (error) {
        console.error("Error:", error);
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger py-4">Ocurrió un error al cargar el reporte de vencimientos.</td></tr>';
    }
}