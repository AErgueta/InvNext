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
    const modalCrear = new bootstrap.Modal(document.getElementById('modalCrear'));
    const inputBuscador = document.getElementById('buscador-tabla');

    // Utilidad para moneda
    const formatearMoneda = (valor) => {
        return new Intl.NumberFormat('es-BO', { 
            minimumFractionDigits: 2, 
            maximumFractionDigits: 2 
        }).format(valor);
    };

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
                // cerrarSesion() debería estar definido en main.hbs
                localStorage.removeItem("erp_token");
                window.location.href = "/vistas/login";
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

    function dibujarTabla(articulosParaMostrar) {
        const tbody = document.getElementById('tabla-articulos');
        tbody.innerHTML = '';
        
        document.getElementById('total-articulos').textContent = articulosParaMostrar.length;

        if (articulosParaMostrar.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">No se encontraron artículos.</td></tr>';
            return;
        }

        articulosParaMostrar.forEach(art => {
            const tr = document.createElement('tr');
            
            if (art.activo === false) {
                tr.classList.add('table-secondary', 'text-muted');
            }

            const badgeLotes = art.controla_lotes 
                ? '<span class="badge bg-warning text-dark"><i class="bi bi-layers-fill"></i> Sí</span>' 
                : '<span class="badge bg-light text-secondary border">No</span>';

            const precioStr = art.precio_venta != null ? formatearMoneda(art.precio_venta) : '0.00';

            const esActivo = art.activo !== false;
            const btnEstadoClass = esActivo ? 'btn-outline-danger' : 'btn-outline-success';
            const btnEstadoIcon = esActivo ? 'bi-archive' : 'bi-arrow-counterclockwise';
            const btnEstadoTitle = esActivo ? 'Archivar' : 'Restaurar';

            tr.innerHTML = `
                <td class="fw-bold align-middle">
                    ${art.sku}
                    ${!esActivo ? '<br><span class="badge bg-danger mt-1">Inactivo</span>' : ''}
                </td>
                <td class="align-middle">
                    ${art.nombre || 'Sin nombre'}
                    ${art.codigo_barras ? `<br><small class="text-muted"><i class="bi bi-upc"></i> ${art.codigo_barras}</small>` : ''}
                </td>
                <td class="text-end fw-bold text-success align-middle">$ ${precioStr}</td>
                <td class="text-center align-middle">${badgeLotes}</td>
                <td class="text-end align-middle">
                    <button class="btn btn-sm btn-outline-primary btn-editar me-1" data-sku="${art.sku}" title="Editar">
                        <i class="bi bi-pencil-square"></i>
                    </button>
                    <button class="btn btn-sm ${btnEstadoClass} btn-estado" data-sku="${art.sku}" title="${btnEstadoTitle}">
                        <i class="bi ${btnEstadoIcon}"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });

        // Re-asignar eventos
        document.querySelectorAll('.btn-editar').forEach(btn => {
            btn.addEventListener('click', (e) => {
                abrirModalEdicion(e.currentTarget.getAttribute('data-sku'));
            });
        });

        document.querySelectorAll('.btn-estado').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const sku = e.currentTarget.getAttribute('data-sku');
                if(confirm(`¿Estás seguro de cambiar el estado del artículo ${sku}?`)) {
                    await cambiarEstadoArticulo(sku);
                }
            });
        });
    }

    // --- BUSCADOR EN TIEMPO REAL ---
    inputBuscador.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        const filtrados = listaArticulos.filter(art => 
            (art.sku && art.sku.toLowerCase().includes(query)) ||
            (art.nombre && art.nombre.toLowerCase().includes(query)) ||
            (art.codigo_barras && art.codigo_barras.toLowerCase().includes(query))
        );
        dibujarTabla(filtrados);
    });

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

            // Mantenemos el filtro activo después de recargar
            await cargarCatalogo(); 
            inputBuscador.dispatchEvent(new Event('input'));

        } catch (error) {
            console.error("Error de red:", error);
            alert("Error de conexión al intentar cambiar el estado.");
        }
    }

    function abrirModalEdicion(sku) {
        const articulo = listaArticulos.find(a => a.sku === sku);
        if (!articulo) return;

        document.getElementById('edit-sku').value = articulo.sku;
        document.getElementById('edit-barras').value = articulo.codigo_barras || '';
        document.getElementById('edit-sku-original').value = articulo.sku;
        document.getElementById('edit-nombre').value = articulo.nombre || '';
        document.getElementById('edit-precio').value = articulo.precio_venta || 0;

        modalEditar.show();
    }

    document.getElementById('btn-guardar-cambios').addEventListener('click', async () => {
        const sku = document.getElementById('edit-sku-original').value;
        const nuevoNombre = document.getElementById('edit-nombre').value;
        const nuevoPrecio = parseFloat(document.getElementById('edit-precio').value);
        const nuevoBarras = document.getElementById('edit-barras').value.trim();

        const btnGuardar = document.getElementById('btn-guardar-cambios');
        btnGuardar.disabled = true;
        btnGuardar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Guardando...';

        try {
            const respuesta = await fetch(`/articulos/${sku}`, {
                method: 'PATCH',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    nombre: nuevoNombre,
                    precio_venta: nuevoPrecio,
                    codigo_barras: nuevoBarras || null
                })
            });

            if (!respuesta.ok) {
                const err = await respuesta.json();
                alert(`Error al actualizar: ${err.detail || 'Desconocido'}`);
                return;
            }

            modalEditar.hide();
            await cargarCatalogo();
            inputBuscador.dispatchEvent(new Event('input')); // Mantiene el filtro de búsqueda
        } catch (error) {
            console.error("Error de red:", error);
            alert("No se pudo conectar con el servidor.");
        } finally {
            btnGuardar.disabled = false;
            btnGuardar.innerHTML = '<i class="bi bi-floppy"></i> Guardar Cambios';
        }
    });

    // Ordenamientos
    document.getElementById('th-sku').addEventListener('click', () => {
        listaArticulos.sort((a, b) => {
            const res = (a.sku || "").localeCompare(b.sku || "");
            return ordenAscendenteSKU ? res : -res;
        });
        ordenAscendenteSKU = !ordenAscendenteSKU;
        inputBuscador.dispatchEvent(new Event('input')); // Aplicar el orden pero mantener el filtro
    });

    document.getElementById('th-nombre').addEventListener('click', () => {
        listaArticulos.sort((a, b) => {
            const res = (a.nombre || "").localeCompare(b.nombre || "");
            return ordenAscendenteNombre ? res : -res;
        });
        ordenAscendenteNombre = !ordenAscendenteNombre;
        inputBuscador.dispatchEvent(new Event('input')); 
    });

    // Abrir el modal de creación y limpiar campos
    document.getElementById('btn-nuevo-articulo').addEventListener('click', () => {
        document.getElementById('form-crear-articulo').reset();
        modalCrear.show();
        // Foco automático en el SKU al abrir el modal
        setTimeout(() => document.getElementById('crear-sku').focus(), 500);
    });

    // Guardar el nuevo artículo
    document.getElementById('btn-guardar-nuevo').addEventListener('click', async () => {
        const sku = document.getElementById('crear-sku').value.trim().toUpperCase(); // Forzar mayúsculas
        const nombre = document.getElementById('crear-nombre').value.trim();
        const barras = document.getElementById('crear-barras').value.trim();
        const precio = parseFloat(document.getElementById('crear-precio').value);
        const controlaLotes = document.getElementById('crear-lotes').value === 'true';
        const flujoSeguimiento = document.getElementById('crear-flujo').value;

        // Validación básica
        if (!sku || !nombre || isNaN(precio) || !flujoSeguimiento) {
            alert("Por favor, completa todos los campos obligatorios (*).");
            return;
        }

        const btnGuardarNuevo = document.getElementById('btn-guardar-nuevo');
        btnGuardarNuevo.disabled = true;
        btnGuardarNuevo.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Guardando...';

        const nuevoArticulo = {
            sku: sku,
            nombre: nombre,
            codigo_barras: barras || null,
            precio_venta: precio,
            controla_lotes: controlaLotes,
            metadatos: {
                flujo_seguimiento: flujoSeguimiento
            }
        };

        try {
            const respuesta = await fetch('/articulos/', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(nuevoArticulo)
            });

            if (!respuesta.ok) {
                const err = await respuesta.json();
                alert(`Error al crear: ${err.detail || 'Verifica los datos. El SKU podría ya existir.'}`);
                return;
            }

            modalCrear.hide();
            await cargarCatalogo(); 
            // Limpiar el buscador para ver el nuevo registro
            inputBuscador.value = '';
            inputBuscador.dispatchEvent(new Event('input'));
        } catch (error) {
            console.error("Error de red:", error);
            alert("No se pudo conectar con el servidor.");
        } finally {
            btnGuardarNuevo.disabled = false;
            btnGuardarNuevo.innerHTML = '<i class="bi bi-floppy"></i> Guardar Artículo';
        }
    });

    // Iniciar carga
    cargarCatalogo();
});