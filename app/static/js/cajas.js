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

    const modalCaja = new bootstrap.Modal(document.getElementById('modalCaja'));
    const formCaja = document.getElementById('form-caja');
    const tbody = document.getElementById('tabla-cajas');
    
    const selectSucursal = document.getElementById('caja-sucursal');
    const selectAlmacen = document.getElementById('caja-almacen');
    let listaAlmacenesGlobal = [];

    const cargarCombos = async () => {
        try {
            // Cargar Sucursales
            const resSuc = await fetch('/sucursales/', { headers: { 'Authorization': `Bearer ${token}` } });
            const sucursales = await resSuc.json();
            selectSucursal.innerHTML = '<option value="">Seleccione una sucursal...</option>';
            sucursales.filter(s => s.activa).forEach(s => {
                selectSucursal.innerHTML += `<option value="${s.codigo}">${s.nombre} (${s.codigo})</option>`;
            });

            // Cargar Almacenes globales para filtrado
            const resAlm = await fetch('/almacenes/', { headers: { 'Authorization': `Bearer ${token}` } });
            listaAlmacenesGlobal = await resAlm.json();
        } catch (error) { console.error("Error cargando dependencias de infraestructura", error); }
    };

    window.filtrarAlmacenesPorSucursal = (almacenSeleccionado = '') => {
        const sucursalCodigo = selectSucursal.value;
        selectAlmacen.innerHTML = '<option value="">Seleccione un almacén...</option>';
        
        if (!sucursalCodigo) return;

        const filtrados = listaAlmacenesGlobal.filter(a => a.codigo_sucursal === sucursalCodigo && a.activo);
        filtrados.forEach(a => {
            const selected = a.codigo === almacenSeleccionado ? 'selected' : '';
            selectAlmacen.innerHTML += `<option value="${a.codigo}" ${selected}>${a.nombre} (${a.codigo})</option>`;
        });
    };

    const cargarCajas = async () => {
        try {
            const res = await fetch('/cajas/', { headers: { 'Authorization': `Bearer ${token}` } });
            const cajas = await res.json();
            
            tbody.innerHTML = '';
            if (cajas.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-3">No hay cajas registradas.</td></tr>';
                return;
            }

            cajas.forEach(c => {
                const btnEstado = c.activa 
                    ? `<button class="btn btn-sm btn-outline-danger" onclick="cambiarEstado('${c.codigo}', false)" title="Desactivar"><i class="bi bi-x-circle"></i></button>`
                    : `<button class="btn btn-sm btn-outline-success" onclick="cambiarEstado('${c.codigo}', true)" title="Activar"><i class="bi bi-check-circle"></i></button>`;

                const badgeUso = c.en_uso 
                    ? `<span class="badge bg-warning text-dark"><i class="bi bi-lock-fill"></i> Abierta</span>`
                    : `<span class="badge bg-light text-dark border"><i class="bi bi-unlock-fill"></i> Cerrada</span>`;

                tbody.innerHTML += `
                    <tr class="${!c.activa ? 'table-active text-muted' : ''}">
                        <td class="fw-bold text-primary">${c.codigo}</td>
                        <td class="fw-bold">${c.nombre}</td>
                        <td><span class="badge bg-secondary">${c.codigo_sucursal}</span></td>
                        <td><span class="badge bg-info text-dark">${c.codigo_almacen || 'N/A'}</span></td>
                        <td>${badgeUso}</td>
                        <td>${c.activa ? '<span class="badge bg-success">Activa</span>' : '<span class="badge bg-secondary">Inactiva</span>'}</td>
                        <td class="text-end">
                            <button class="btn btn-sm btn-light text-primary" onclick="abrirModalEditar('${c.codigo}', '${c.nombre}', '${c.codigo_sucursal}', '${c.codigo_almacen || ''}')">
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
        document.getElementById('caja-modo').value = 'crear';
        document.getElementById('modalCajaTitulo').textContent = 'Nueva Caja';
        document.getElementById('caja-codigo').readOnly = false;
        formCaja.reset();
        selectAlmacen.innerHTML = '<option value="">Seleccione primero una sucursal...</option>';
        modalCaja.show();
    };

    window.abrirModalEditar = (codigo, nombre, sucursal, almacen) => {
        document.getElementById('caja-modo').value = 'editar';
        document.getElementById('caja-codigo-original').value = codigo;
        document.getElementById('modalCajaTitulo').textContent = `Editar: ${codigo}`;
        
        document.getElementById('caja-codigo').value = codigo;
        document.getElementById('caja-nombre').value = nombre;
        selectSucursal.value = sucursal;
        
        filtrarAlmacenesPorSucursal(almacen);
        modalCaja.show();
    };

    formCaja.addEventListener('submit', async (e) => {
        e.preventDefault();
        const modo = document.getElementById('caja-modo').value;
        const codigoOriginal = document.getElementById('caja-codigo-original').value;
        
        const payload = {
            codigo: document.getElementById('caja-codigo').value.toUpperCase(),
            nombre: document.getElementById('caja-nombre').value,
            codigo_sucursal: selectSucursal.value,
            codigo_almacen: selectAlmacen.value
        };

        const btnGuardar = document.getElementById('btn-guardar-caja');
        btnGuardar.disabled = true;

        try {
            let url = '/cajas/';
            let method = 'POST';
            if (modo === 'editar') {
                url = `/cajas/${codigoOriginal}`;
                method = 'PUT';
            }

            const response = await fetch(url, {
                method: method,
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                modalCaja.hide();
                cargarCajas();
            } else {
                const data = await response.json();
                alert(`Error: ${data.detail}`);
            }
        } catch (error) { alert("Error de conexión."); } 
        finally { btnGuardar.disabled = false; }
    });

    window.cambiarEstado = async (codigo, activa) => {
        if (!confirm(`¿Estás seguro de ${activa ? 'activar' : 'desactivar'} la caja ${codigo}?`)) return;
        try {
            const res = await fetch(`/cajas/${codigo}/estado`, {
                method: 'PATCH',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({ activa: activa })
            });
            if (res.ok) cargarCajas();
        } catch (error) {}
    };

    cargarCombos();
    cargarCajas();
});