document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('erp_token');
    if (!token) {
        window.location.href = '/vistas/login';
        return;
    }

    let listaArticulos = [];
    let ordenAscendenteSKU = true;
    let ordenAscendenteNombre = true;
    
    const modalEditar = new bootstrap.Modal(document.getElementById('modalEditar'));

    async function cargarCatalogo() {
        try {
            const respuesta = await fetch('/articulos/', {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (respuesta.status === 401) {
                cerrarSesion();
                return;
            }
            
            listaArticulos = await respuesta.json();
            dibujarTabla(listaArticulos);

        } catch (error) {
            console.error("Error al obtener el catálogo:", error);
            const tbody = document.getElementById('tabla-articulos');
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-danger py-4">Error de conexión con el servidor.</td></tr>';
        }
    }

    function dibujarTabla(articulos) {
        const tbody = document.getElementById('tabla-articulos');
        tbody.innerHTML = '';

        if (articulos.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">Tu catálogo está vacío.</td></tr>';
            return;
        }

        articulos.forEach(art => {
            const tr = document.createElement('tr');
            
            // Si está inactivo, le bajamos la opacidad visualmente
            if (art.activo === false) {
                tr.classList.add('table-secondary', 'text-muted');
            }

            const badgeLotes = art.controla_lotes 
                ? '<span class="badge bg-warning text-dark"><i class="bi bi-check2-circle"></i> Sí (FEFO)</span>' 
                : '<span class="badge bg-secondary">No</span>';

            const precioStr = art.precio_venta != null ? parseFloat(art.precio_venta).toFixed(2) : '0.00';

            // Definimos el botón según el estado actual
            const esActivo = art.activo !== false;
            const btnEstadoClass = esActivo ? 'btn-outline-danger' : 'btn-outline-success';
            const btnEstadoIcon = esActivo ? 'bi-trash3' : 'bi-check-circle';
            const btnEstadoTitle = esActivo ? 'Desactivar' : 'Activar';

            tr.innerHTML = `
                <td>
                    <strong>${art.sku}</strong>
                    ${!esActivo ? '<span class="badge bg-danger ms-2">Inactivo</span>' : ''}
                </td>
                <td>${art.nombre || 'Sin nombre'}</td>
                <td class="text-end">$ ${precioStr}</td>
                <td>${badgeLotes}</td>
                <td class="text-end">
                    <button class="btn btn-sm btn-outline-primary btn-editar me-1" data-sku="${art.sku}" title="Editar">
                        <i class="bi bi-pencil-square"></i> Editar
                    </button>
                    <button class="btn btn-sm ${btnEstadoClass} btn-estado" data-sku="${art.sku}" title="${btnEstadoTitle}">
                        <i class="bi ${btnEstadoIcon}"></i> ${btnEstadoTitle}
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });

        // Eventos para Editar
        document.querySelectorAll('.btn-editar').forEach(btn => {
            btn.addEventListener('click', (e) => {
                abrirModalEdicion(e.currentTarget.getAttribute('data-sku'));
            });
        });

        // Eventos para Activar/Desactivar
        document.querySelectorAll('.btn-estado').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const sku = e.currentTarget.getAttribute('data-sku');
                await cambiarEstadoArticulo(sku);
            });
        });
    }

    async function cambiarEstadoArticulo(sku) {
        try {
            const respuesta = await fetch(`/articulos/${sku}/estado`, {
                method: 'PATCH',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (!respuesta.ok) {
                const err = await respuesta.json();
                alert(`No se pudo cambiar el estado: ${err.detail || 'Error desconocido'}`);
                return;
            }

            cargarCatalogo(); // Refrescamos la tabla para ver el cambio de inmediato
        } catch (error) {
            console.error("Error de red:", error);
            alert("Error de conexión al intentar cambiar el estado.");
        }
    }

    function abrirModalEdicion(sku) {
        const articulo = listaArticulos.find(a => a.sku === sku);
        if (!articulo) return;

        document.getElementById('edit-sku').value = articulo.sku;
        document.getElementById('edit-sku-original').value = articulo.sku;
        document.getElementById('edit-nombre').value = articulo.nombre || '';
        document.getElementById('edit-precio').value = articulo.precio_venta || 0;

        modalEditar.show();
    }

    document.getElementById('btn-guardar-cambios').addEventListener('click', async () => {
        const sku = document.getElementById('edit-sku-original').value;
        const nuevoNombre = document.getElementById('edit-nombre').value;
        const nuevoPrecio = parseFloat(document.getElementById('edit-precio').value);

        try {
            const respuesta = await fetch(`/articulos/${sku}`, {
                method: 'PATCH',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    nombre: nuevoNombre,
                    precio_venta: nuevoPrecio
                })
            });

            if (!respuesta.ok) {
                const err = await respuesta.json();
                alert(`Error al actualizar: ${err.detail || 'Desconocido'}`);
                return;
            }

            modalEditar.hide();
            cargarCatalogo();
        } catch (error) {
            console.error("Error de red:", error);
            alert("No se pudo conectar con el servidor.");
        }
    });

    // Ordenamientos
    document.getElementById('th-sku').addEventListener('click', () => {
        listaArticulos.sort((a, b) => (a.sku || "").localeCompare(b.sku || ""));
        ordenAscendenteSKU = !ordenAscendenteSKU;
        dibujarTabla(listaArticulos);
    });

    document.getElementById('th-nombre').addEventListener('click', () => {
        listaArticulos.sort((a, b) => (a.nombre || "").localeCompare(b.nombre || ""));
        ordenAscendenteNombre = !ordenAscendenteNombre;
        dibujarTabla(listaArticulos);
    });

    document.getElementById('btn-nuevo-articulo').addEventListener('click', () => {
        alert("¡Próximamente modal de creación!");
    });

    cargarCatalogo();
});