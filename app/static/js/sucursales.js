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

    const modalSucursal = new bootstrap.Modal(document.getElementById('modalSucursal'));
    const formSucursal = document.getElementById('form-sucursal');
    const tbody = document.getElementById('tabla-sucursales');

    const cargarSucursales = async () => {
        try {
            const res = await fetch('/sucursales/', { headers: { 'Authorization': `Bearer ${token}` } });
            const sucursales = await res.json();
            
            tbody.innerHTML = '';
            if (sucursales.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">No hay sucursales registradas.</td></tr>';
                return;
            }

            sucursales.forEach(s => {
                const btnEstado = s.activa 
                    ? `<button class="btn btn-sm btn-outline-danger" onclick="cambiarEstado('${s.codigo}', false)" title="Desactivar"><i class="bi bi-x-circle"></i></button>`
                    : `<button class="btn btn-sm btn-outline-success" onclick="cambiarEstado('${s.codigo}', true)" title="Activar"><i class="bi bi-check-circle"></i></button>`;

                tbody.innerHTML += `
                    <tr class="${!s.activa ? 'table-active text-muted' : ''}">
                        <td class="fw-bold text-primary">${s.codigo}</td>
                        <td class="fw-bold">${s.nombre}</td>
                        <td>${s.telefono || '-'}</td>
                        <td>${s.direccion || '-'}</td>
                        <td>${s.activa ? '<span class="badge bg-success">Activa</span>' : '<span class="badge bg-secondary">Inactiva</span>'}</td>
                        <td class="text-end">
                            <button class="btn btn-sm btn-light text-primary" onclick="abrirModalEditar('${s.codigo}', '${s.nombre}', '${s.direccion || ''}', '${s.telefono || ''}')">
                                <i class="bi bi-pencil-square"></i>
                            </button>
                            ${btnEstado}
                        </td>
                    </tr>
                `;
            });
        } catch (error) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Error cargando datos.</td></tr>';
        }
    };

    window.abrirModalCrear = () => {
        document.getElementById('sucursal-modo').value = 'crear';
        document.getElementById('modalSucursalTitulo').textContent = 'Nueva Sucursal';
        document.getElementById('sucursal-codigo').readOnly = false;
        formSucursal.reset();
        modalSucursal.show();
    };

    window.abrirModalEditar = (codigo, nombre, direccion, telefono) => {
        document.getElementById('sucursal-modo').value = 'editar';
        document.getElementById('sucursal-codigo-original').value = codigo;
        document.getElementById('modalSucursalTitulo').textContent = `Editar: ${codigo}`;
        
        document.getElementById('sucursal-codigo').value = codigo;
        document.getElementById('sucursal-nombre').value = nombre;
        document.getElementById('sucursal-direccion').value = direccion;
        document.getElementById('sucursal-telefono').value = telefono;
        
        modalSucursal.show();
    };

    formSucursal.addEventListener('submit', async (e) => {
        e.preventDefault();
        const modo = document.getElementById('sucursal-modo').value;
        const codigoOriginal = document.getElementById('sucursal-codigo-original').value;
        
        const payload = {
            codigo: document.getElementById('sucursal-codigo').value.toUpperCase(),
            nombre: document.getElementById('sucursal-nombre').value,
            direccion: document.getElementById('sucursal-direccion').value || null,
            telefono: document.getElementById('sucursal-telefono').value || null,
            activa: true
        };

        const btnGuardar = document.getElementById('btn-guardar-sucursal');
        btnGuardar.disabled = true;

        try {
            let url = '/sucursales/';
            let method = 'POST';
            if (modo === 'editar') {
                url = `/sucursales/${codigoOriginal}`;
                method = 'PUT';
            }

            const response = await fetch(url, {
                method: method,
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                modalSucursal.hide();
                cargarSucursales();
            } else {
                const data = await response.json();
                alert(`Error: ${data.detail}`);
            }
        } catch (error) { alert("Error de conexión."); } 
        finally { btnGuardar.disabled = false; }
    });

    window.cambiarEstado = async (codigo, activa) => {
        if (!confirm(`¿Estás seguro de ${activa ? 'activar' : 'desactivar'} la sucursal ${codigo}?`)) return;
        try {
            const res = await fetch(`/sucursales/${codigo}/estado`, {
                method: 'PATCH',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({ activa: activa })
            });
            if (res.ok) cargarSucursales();
        } catch (error) {}
    };

    cargarSucursales();
});