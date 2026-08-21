document.addEventListener('DOMContentLoaded', async () => {
    // 1. Verificamos que el usuario tenga un token válido
    const token = localStorage.getItem('erp_token');
    if (!token) {
        // Si no hay token, lo pateamos de vuelta al login
        window.location.href = '/vistas/login';
        return;
    }

    // 2. Función maestra para consultar a tu API de forma segura
    async function fetchConToken(url) {
        const respuesta = await fetch(url, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`, // ¡Aquí enviamos el pase de entrada!
                'Content-Type': 'application/json'
            }
        });

        if (respuesta.status === 401) {
            // Si el token expiró o es inválido, cerramos la sesión
            cerrarSesion();
            throw new Error("Sesión expirada");
        }
        
        return respuesta.json();
    }

    // 3. Cargamos los datos reales desde el endpoint del dashboard
    try {
        const datos = await fetchConToken('/reportes/resumen-dashboard');

        // Llenamos los KPIs
        document.getElementById('kpi-articulos').textContent = datos.kpis.total_articulos;
        
        // Formateamos el valor a moneda (ej. $ 1,500.50)
        const valorMoneda = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(datos.kpis.valor_inventario);
        document.getElementById('kpi-valor').textContent = valorMoneda;
        
        document.getElementById('kpi-alertas').textContent = datos.kpis.alertas_stock;
        document.getElementById('kpi-movimientos').textContent = datos.kpis.movimientos_hoy;

        // Llenamos la tabla de últimos movimientos
        const tbody = document.getElementById('tabla-ultimos-mov');
        tbody.innerHTML = ''; // Limpiamos el mensaje de "Cargando..."

        if (datos.ultimos_movimientos.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center py-3 text-muted">No hay movimientos recientes.</td></tr>';
            return;
        }

        // Construimos las filas dinámicamente
        datos.ultimos_movimientos.forEach(mov => {
            // Asignamos colores según el tipo de movimiento
            let badgeClass = 'bg-secondary';
            if (mov.tipo.includes('IN_')) badgeClass = 'bg-success';
            if (mov.tipo.includes('OUT_')) badgeClass = 'bg-danger';

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><span class="badge ${badgeClass}">${mov.tipo.replace('_', ' ')}</span></td>
                <td><strong>${mov.articulo}</strong></td>
                <td>${mov.tipo.includes('IN_') ? '+' : '-'}${mov.cantidad}</td>
                <td class="text-muted small">${mov.fecha}</td>
            `;
            tbody.appendChild(tr);
        });

    } catch (error) {
        console.error("Error al cargar el dashboard:", error);
        const tbody = document.getElementById('tabla-ultimos-mov');
        tbody.innerHTML = '<tr><td colspan="4" class="text-center py-3 text-danger">Error de conexión al cargar datos.</td></tr>';
    }
});