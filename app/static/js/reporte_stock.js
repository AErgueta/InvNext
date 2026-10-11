document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('erp_token');
    if (!token) { 
        window.location.href = '/vistas/login'; 
        return; 
    }

    const selectAlmacen = document.getElementById('select-almacen-reporte');
    const btnConsultar = document.getElementById('btn-consultar-stock');
    const tbody = document.getElementById('tabla-reporte-stock');

    // 1. Cargar almacenes en el select
    try {
        const res = await fetch('/almacenes/', { headers: { 'Authorization': `Bearer ${token}` } });
        const almacenes = await res.json();
        
        selectAlmacen.innerHTML = '<option value="">-- Seleccione el almacén a consultar --</option>';
        almacenes.filter(a => a.activo).forEach(a => {
            selectAlmacen.innerHTML += `<option value="${a.codigo}">${a.nombre} (${a.codigo})</option>`;
        });

        // Intentar autoseleccionar el almacén del usuario actual
        const resPerfil = await fetch('/me', { headers: { 'Authorization': `Bearer ${token}` } });
        if (resPerfil.ok) {
            const perfil = await resPerfil.json();
            const almacenUsuario = perfil.almacen_id || perfil.codigo_almacen;
            if (almacenUsuario) {
                selectAlmacen.value = almacenUsuario;
                // Si queremos que se consulte automáticamente al entrar, descomentar:
                // btnConsultar.click();
            }
        }
    } catch (error) {
        console.error("Error cargando almacenes:", error);
        selectAlmacen.innerHTML = '<option value="">Error al cargar almacenes</option>';
    }

    // 2. Consultar y pintar el Stock
    btnConsultar.addEventListener('click', async () => {
        const almacen = selectAlmacen.value;
        if (!almacen) {
            alert("Por favor, seleccione un almacén de la lista.");
            return;
        }

        btnConsultar.disabled = true;
        btnConsultar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Cargando...';
        tbody.innerHTML = '<tr><td colspan="5" class="text-center py-5">⏳ Buscando existencias y calculando stock...</td></tr>';

        try {
            const res = await fetch(`/articulos/reporte/stock/${almacen}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!res.ok) throw new Error("Error al obtener el reporte del servidor");

            const reporte = await res.json();
            
            if (reporte.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-5">No hay artículos en el catálogo general.</td></tr>';
            } else {
                tbody.innerHTML = '';
                reporte.forEach(item => {
                    // Pintar en rojo si el stock es 0, y en verde si hay stock
                    const colorStock = item.stock <= 0 ? 'text-danger fw-bold' : 'text-success fw-bold';
                    
                    tbody.innerHTML += `
                        <tr>
                            <td class="fw-bold">${item.sku}</td>
                            <td>${item.nombre}</td>
                            <td><span class="badge bg-light text-dark border">${item.categoria}</span></td>
                            <td class="text-center fs-5 ${colorStock}">${item.stock.toLocaleString('en-US')}</td>
                            <td class="text-muted">${item.unidad_medida}</td>
                        </tr>
                    `;
                });
            }
        } catch (error) {
            console.error("Error consultando stock:", error);
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-danger py-5"><i class="bi bi-exclamation-triangle d-block fs-3 mb-2"></i> Ocurrió un error al cargar la información.</td></tr>';
        } finally {
            btnConsultar.disabled = false;
            btnConsultar.innerHTML = '<i class="bi bi-search"></i> Consultar';
        }
    });
});