document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('erp_token');
    if (!token) { window.location.href = '/vistas/login'; return; }

    try {
        const resPerfil = await fetch('/me', { headers: { 'Authorization': `Bearer ${token}` } });
        const perfil = await resPerfil.json();
        if (perfil.rol !== 'ADMIN') {
            alert("Acceso Denegado.");
            window.location.href = '/vistas/dashboard';
            return;
        }
    } catch (e) { window.location.href = '/vistas/login'; return; }

    const modalAlmacen = new bootstrap.Modal(document.getElementById('modalAlmacen'));
    const formAlmacen = document.getElementById('form-almacen');
    const tbody = document.getElementById('tabla-almacenes');
    const selectSucursal = document.getElementById('almacen-sucursal');

    // Cargar sucursales para el select
    const cargarComboSucursales = async () => {
        try {
            const res = await fetch('/sucursales/', { headers: { 'Authorization': `Bearer ${token}` } });
            const sucursales = await res.json();
            selectSucursal.innerHTML = '<option value="">Seleccione una sucursal...</option>';
            sucursales.filter(s => s.activa).forEach(s => {
                selectSucursal.innerHTML += `<option value="${s.codigo}">${s.nombre} (${s.codigo})</option>`;
            });
        } catch (error) { console.error("Error cargando sucursales"); }
    };

    const cargarAlmacenes = async () => {
        try {
            const res = await fetch('/almacenes/', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const almacenes = await res.json();
            
            tbody.innerHTML = '';
            if (almacenes.length === 0) {
                // Actualizado colspan a 7 por la nueva columna
                tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-3">No hay almacenes registrados.</td></tr>';
                return;
            }

            almacenes.forEach(a => {
                const btnEstado = a.activo 
                    ? `<button class="btn btn-sm btn-outline-danger" onclick="cambiarEstado('${a.codigo}', false)" title="Desactivar"><i class="bi bi-x-circle"></i></button>`
                    : `<button class="btn btn-sm btn-outline-success" onclick="cambiarEstado('${a.codigo}', true)" title="Activar"><i class="bi bi-check-circle"></i></button>`;

                tbody.innerHTML += `
                    <tr class="${!a.activo ? 'table-active text-muted' : ''}">
                        <td class="fw-bold text-primary">${a.codigo}</td>
                        <td class="fw-bold">${a.nombre}</td>
                        <td><span class="badge bg-secondary">${a.codigo_sucursal}</span></td>
                        <td>${a.descripcion || '<span class="text-muted">-</span>'}</td>
                        <td>${a.direccion || '<span class="text-muted">-</span>'}</td>
                        <td>${a.activo ? '<span class="badge bg-success">Activo</span>' : '<span class="badge bg-secondary">Inactivo</span>'}</td>
                        <td class="text-end">
                            <button class="btn btn-sm btn-light text-primary" onclick="abrirModalEditar('${a.codigo}', '${a.nombre}', '${a.codigo_sucursal}', '${a.descripcion || ''}', '${a.direccion || ''}')">
                                <i class="bi bi-pencil-square"></i>
                            </button>
                            ${btnEstado}
                        </td>
                    </tr>
                `;
            });
        } catch (error) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Error cargando datos.</td></tr>';
        }
    };

    window.abrirModalCrear = () => {
        document.getElementById('almacen-modo').value = 'crear';
        document.getElementById('modalAlmacenTitulo').textContent = 'Nuevo Almacén';
        document.getElementById('almacen-codigo').readOnly = false;
        formAlmacen.reset();
        modalAlmacen.show();
    };

    window.abrirModalEditar = (codigo, nombre, sucursal, descripcion, direccion) => {
        document.getElementById('almacen-modo').value = 'editar';
        document.getElementById('almacen-codigo-original').value = codigo;
        document.getElementById('modalAlmacenTitulo').textContent = `Editar: ${codigo}`;
        
        document.getElementById('almacen-codigo').value = codigo;
        document.getElementById('almacen-nombre').value = nombre;
        document.getElementById('almacen-sucursal').value = sucursal;
        document.getElementById('almacen-descripcion').value = descripcion;
        document.getElementById('almacen-direccion').value = direccion;
        
        modalAlmacen.show();
    };

    formAlmacen.addEventListener('submit', async (e) => {
        e.preventDefault();
        const modo = document.getElementById('almacen-modo').value;
        const codigoOriginal = document.getElementById('almacen-codigo-original').value;
        
        const payload = {
            codigo: document.getElementById('almacen-codigo').value.toUpperCase(),
            nombre: document.getElementById('almacen-nombre').value,
            codigo_sucursal: document.getElementById('almacen-sucursal').value,
            descripcion: document.getElementById('almacen-descripcion').value || null,
            direccion: document.getElementById('almacen-direccion').value || null,
            activo: true // Por defecto al crear
        };

        const btnGuardar = document.getElementById('btn-guardar-almacen');
        btnGuardar.disabled = true;

        try {
            let url = '/almacenes/';
            let method = 'POST';
            
            if (modo === 'editar') {
                url = `/almacenes/${codigoOriginal}`;
                method = 'PUT';
            }

            const response = await fetch(url, {
                method: method,
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json' 
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            
            if (response.ok) {
                modalAlmacen.hide();
                cargarAlmacenes();
            } else {
                alert(`Error: ${data.detail}`);
            }
        } catch (error) {
            alert("Error de conexión.");
        } finally {
            btnGuardar.disabled = false;
        }
    });

    window.cambiarEstado = async (codigo, activo) => {
        if (!confirm(`¿Estás seguro de ${activo ? 'activar' : 'desactivar'} el almacén ${codigo}?`)) return;
        try {
            const res = await fetch(`/almacenes/${codigo}/estado`, {
                method: 'PATCH',
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json' 
                },
                body: JSON.stringify({ activo: activo })
            });
            if (res.ok) cargarAlmacenes();
            else alert("Error al cambiar estado.");
        } catch (error) { console.error(error); }
    };

    // Iniciar cargando primero los combos y luego la tabla
    cargarComboSucursales();
    cargarAlmacenes();
});