document.addEventListener('DOMContentLoaded', cargarAlertas);
document.getElementById('btn-refrescar-alertas').addEventListener('click', cargarAlertas);

// Función para obtener el token de seguridad
function obtenerToken() {
    return localStorage.getItem('erp_token');
}

async function cargarAlertas() {
    const tbody = document.getElementById('cuerpo-tabla-alertas');
    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4">⏳ Escaneando inventario...</td></tr>';

    try {
        const token = obtenerToken();
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

        const response = await fetch('/reportes/stock-bajo', { headers });
        
        if (response.status === 401) {
            window.location.href = '/vistas/login';
            return;
        }
        
        if (!response.ok) throw new Error("Error al consultar las alertas de stock");
        
        const alertas = await response.json();
        
        if (alertas.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center py-5 text-success">
                        <i class="bi bi-check-circle-fill fs-3 d-block mb-2"></i>
                        <strong>✅ Todo en orden</strong><br>
                        Ningún artículo requiere abastecimiento en este momento.
                    </td>
                </tr>
            `;
            return;
        }

        let htmlFilas = "";

        // Usamos tu variable 'alertas'
        alertas.forEach(alerta => {
            // Reemplazamos tus clases antiguas por las etiquetas nativas de Bootstrap
            let badgeHtml = alerta.estado_alerta === 'CRÍTICO' 
                ? '<span class="badge bg-danger">CRÍTICO</span>' 
                : '<span class="badge bg-warning text-dark">REORDEN</span>';
            
            let colorFila = alerta.estado_alerta === 'CRÍTICO' ? 'background-color: #fff5f5;' : 'background-color: #fffdf5;';

            htmlFilas += `
                <tr style="${colorFila}">
                    <!-- 1. SKU -->
                    <td class="text-start align-middle fw-bold">${alerta.sku}</td>
                    
                    <!-- 2. ALMACÉN -->
                    <td class="text-start align-middle fw-semibold text-primary">${alerta.almacen}</td> 
                    
                    <!-- 3. ESTADO (¡Ahora sí será visible!) -->
                    <td class="text-center align-middle">${badgeHtml}</td>
                    
                    <!-- 4. STOCK ACTUAL -->
                    <td class="text-center align-middle fw-bold text-danger">${alerta.stock_actual.toLocaleString('en-US')}</td>
                    
                    <!-- 5. PUNTO REORDEN -->
                    <td class="text-center align-middle">${alerta.punto_reorden.toLocaleString('en-US')}</td>
                    
                    <!-- 6. STOCK MÍNIMO -->
                    <td class="text-center align-middle text-muted">${alerta.stock_minimo.toLocaleString('en-US')}</td>
                    
                    <!-- 7. FALTANTE -->
                    <td class="text-center align-middle fw-bold text-danger">
                        ⬇ ${alerta.diferencia_reorden.toLocaleString('en-US')}
                    </td>
                </tr>
            `;
        });

        tbody.innerHTML = htmlFilas;

    } catch (error) {
        console.error("Error:", error);
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger py-4">Ocurrió un error al cargar el radar de alertas.</td></tr>';
    }
}