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

    const modalUsuario = new bootstrap.Modal(document.getElementById('modalUsuario'));
    const formUsuario = document.getElementById('form-usuario');
    const tbody = document.getElementById('tabla-usuarios');

    const selectSucursal = document.getElementById('usuario-sucursal');
    const selectAlmacen = document.getElementById('usuario-almacen');
    const selectCaja = document.getElementById('usuario-caja');
    
    let listaAlmacenes = [];
    let listaCajas = [];
    let listaSucursales = [];

    // ==========================================
    // CARGAR DATOS DE INFRAESTRUCTURA
    // ==========================================
    const cargarDatosEstructurales = async () => {
        try {
            const [resSuc, resAlm, resCaj] = await Promise.all([
                fetch('/sucursales/', { headers: { 'Authorization': `Bearer ${token}` } }),
                fetch('/almacenes/', { headers: { 'Authorization': `Bearer ${token}` } }),
                fetch('/cajas/', { headers: { 'Authorization': `Bearer ${token}` } })
            ]);

            listaSucursales = await resSuc.json();
            listaAlmacenes = await resAlm.json();
            listaCajas = await resCaj.json();
        } catch (error) { 
            console.error("Error cargando infraestructura estructural:", error); 
        }
    };

    const poblarSelectSucursales = (sucursalSeleccionada = '') => {
        selectSucursal.innerHTML = '<option value="">Ninguna / Global</option>';
        listaSucursales.filter(s => s.activa).forEach(s => {
            const sel = s.codigo === sucursalSeleccionada ? 'selected' : '';
            selectSucursal.innerHTML += `<option value="${s.codigo}" ${sel}>${s.nombre} (${s.codigo})</option>`;
        });
    };

    // ==========================================
    // FILTRADO EN CASCADA
    // ==========================================
    window.filtrarDependencias = (almacenSeleccionado = '', cajaSeleccionada = '') => {
        const sucursalCodigo = selectSucursal.value;
        
        selectAlmacen.innerHTML = '<option value="">Ninguno</option>';
        selectCaja.innerHTML = '<option value="">Ninguna</option>';

        if (!sucursalCodigo) {
            selectAlmacen.innerHTML = '<option value="">Seleccione Sucursal primero...</option>';
            selectCaja.innerHTML = '<option value="">Seleccione Sucursal primero...</option>';
            return;
        }

        const almacenesFiltrados = listaAlmacenes.filter(a => a.codigo_sucursal === sucursalCodigo && a.activo);
        almacenesFiltrados.forEach(a => {
            const sel = a.codigo === almacenSeleccionado ? 'selected' : '';
            selectAlmacen.innerHTML += `<option value="${a.codigo}" ${sel}>${a.nombre} (${a.codigo})</option>`;
        });

        const cajasFiltradas = listaCajas.filter(c => c.codigo_sucursal === sucursalCodigo && c.activa);
        cajasFiltradas.forEach(c => {
            const sel = c.codigo === cajaSeleccionada ? 'selected' : '';
            selectCaja.innerHTML += `<option value="${c.codigo}" ${sel}>${c.nombre} (${c.codigo})</option>`;
        });
    };

    // ==========================================
    // LISTAR USUARIOS
    // ==========================================
    const cargarUsuarios = async () => {
        try {
            const res = await fetch('/usuarios', { headers: { 'Authorization': `Bearer ${token}` } });
            const usuarios = await res.json();
            
            tbody.innerHTML = '';
            usuarios.forEach(u => {
                const colorRol = u.rol === 'ADMIN' ? 'danger' : (u.rol === 'CAJERO' ? 'success' : 'primary');
                const btnEstado = u.activo 
                    ? `<button class="btn btn-sm btn-outline-danger" onclick="cambiarEstado('${u.username}', false)" title="Desactivar"><i class="bi bi-person-x"></i></button>`
                    : `<button class="btn btn-sm btn-outline-success" onclick="cambiarEstado('${u.username}', true)" title="Activar"><i class="bi bi-person-check"></i></button>`;

                tbody.innerHTML += `
                    <tr class="${!u.activo ? 'table-active text-muted' : ''}">
                        <td class="fw-bold">${u.username}</td>
                        <td><span class="badge bg-${colorRol}">${u.rol}</span></td>
                        <td>${u.sucursal_id || '<span class="text-muted">-</span>'}</td>
                        <td>${u.almacen_id || '<span class="text-muted">-</span>'}</td>
                        <td class="fw-bold text-success">${u.caja_id || '<span class="text-muted">-</span>'}</td>
                        <td>${u.activo ? '<span class="badge bg-success">Activo</span>' : '<span class="badge bg-secondary">Inactivo</span>'}</td>
                        <td class="text-end">
                            <button class="btn btn-sm btn-light text-primary" onclick="abrirModalEditar('${u.username}', '${u.rol}', '${u.sucursal_id || ''}', '${u.almacen_id || ''}', '${u.caja_id || ''}')">
                                <i class="bi bi-pencil-square"></i>
                            </button>
                            ${btnEstado}
                        </td>
                    </tr>
                `;
            });
        } catch (error) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Error cargando usuarios.</td></tr>';
        }
    };

    // ==========================================
    // CONTRASEÑA
    // ==========================================
    const btnTogglePassword = document.getElementById('btn-toggle-password');
    const inputPassword = document.getElementById('usuario-password');
    const iconoPassword = document.getElementById('icono-password');

    if(btnTogglePassword) {
        btnTogglePassword.addEventListener('click', () => {
            if (inputPassword.type === 'password') {
                inputPassword.type = 'text';
                iconoPassword.classList.replace('bi-eye-slash', 'bi-eye');
            } else {
                inputPassword.type = 'password';
                iconoPassword.classList.replace('bi-eye', 'bi-eye-slash');
            }
        });
    }

    // ==========================================
    // MODAL Y FORMULARIO
    // ==========================================
    window.abrirModalCrear = async () => {
        await cargarDatosEstructurales(); // Asegura datos frescos
        document.getElementById('usuario-modo').value = 'crear';
        document.getElementById('modalUsuarioTitulo').textContent = 'Nuevo Usuario';
        document.getElementById('usuario-username').readOnly = false;
        document.getElementById('grupo-password').style.display = 'block';
        document.getElementById('usuario-password').required = true;
        
        inputPassword.type = 'password';
        if(iconoPassword) iconoPassword.className = 'bi bi-eye-slash';
        
        formUsuario.reset();
        poblarSelectSucursales();
        filtrarDependencias();
        
        modalUsuario.show();
    };

    window.abrirModalEditar = async (username, rol, sucursal, almacen, caja) => {
        await cargarDatosEstructurales(); // Asegura datos frescos antes de pintar
        document.getElementById('usuario-modo').value = 'editar';
        document.getElementById('modalUsuarioTitulo').textContent = `Editar: ${username}`;
        
        document.getElementById('usuario-username').value = username;
        document.getElementById('usuario-username').readOnly = true; 
        
        document.getElementById('grupo-password').style.display = 'none'; 
        document.getElementById('usuario-password').required = false;
        
        document.getElementById('usuario-rol').value = rol;
        
        poblarSelectSucursales(sucursal);
        filtrarDependencias(almacen, caja);
        
        modalUsuario.show();
    };

    formUsuario.addEventListener('submit', async (e) => {
        e.preventDefault();
        const modo = document.getElementById('usuario-modo').value;
        const username = document.getElementById('usuario-username').value;
        
        const payload = {
            rol: document.getElementById('usuario-rol').value,
            sucursal_id: selectSucursal.value || null,
            almacen_id: selectAlmacen.value || null,
            caja_id: selectCaja.value || null
        };

        const btnGuardar = document.getElementById('btn-guardar-usuario');
        btnGuardar.disabled = true;

        try {
            let url, method, bodyData;
            
            if (modo === 'crear') {
                url = '/registrar';
                method = 'POST';
                payload.username = username;
                payload.password = document.getElementById('usuario-password').value;
                bodyData = payload;
            } else {
                url = `/usuarios/${username}`;
                method = 'PUT';
                bodyData = payload; 
            }

            const response = await fetch(url, {
                method: method,
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json' 
                },
                body: JSON.stringify(bodyData)
            });

            if (response.ok) {
                modalUsuario.hide();
                cargarUsuarios();
            } else {
                const data = await response.json();
                alert(`Error: ${data.detail}`);
            }
        } catch (error) {
            alert("Error de conexión.");
        } finally {
            btnGuardar.disabled = false;
        }
    });

    window.cambiarEstado = async (username, activo) => {
        if (!confirm(`¿Estás seguro de ${activo ? 'activar' : 'desactivar'} al usuario ${username}?`)) return;
        try {
            const res = await fetch(`/${username}/estado`, {
                method: 'PATCH',
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json' 
                },
                body: JSON.stringify({ activo: activo })
            });
            if (res.ok) cargarUsuarios();
        } catch (error) {}
    };

    // Inicializar carga de tabla
    cargarUsuarios();
});