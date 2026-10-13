let listaProveedores = []; // Variable global para guardar los datos cargados

document.addEventListener('DOMContentLoaded', () => {
    cargarProveedores();
    document.getElementById('form-proveedor').addEventListener('submit', guardarProveedor);
});

async function cargarProveedores() {
    const token = localStorage.getItem('erp_token');
    const tbody = document.getElementById('tabla-proveedores');
    
    try {
        const response = await fetch('/proveedores/', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            listaProveedores = await response.json();
            tbody.innerHTML = '';
            
            if (listaProveedores.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No hay proveedores registrados.</td></tr>';
                return;
            }
            
            listaProveedores.forEach((p, index) => {
                // Agregamos cursor-pointer y el evento onclick a la fila
                tbody.innerHTML += `
                    <tr style="cursor: pointer;" onclick="cargarParaEdicion(${index})" title="Clic para editar" class="table-row-hover">
                        <td class="fw-bold text-uppercase">${p.razon_social}</td>
                        <td>${p.nit_ci || '-'}</td>
                        <td class="text-capitalize">${p.nombre_contacto || '-'}</td>
                        <td>${p.telefono || '-'}</td>
                    </tr>
                `;
            });
        }
    } catch (error) {
        console.error("Error al cargar proveedores:", error);
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-danger">Error de conexión</td></tr>';
    }
}

// --- NUEVA FUNCIÓN: CARGAR DATOS AL FORMULARIO ---
function cargarParaEdicion(index) {
    const proveedor = listaProveedores[index];
    
    // Llenamos el formulario
    document.getElementById('prov-id').value = proveedor._id;
    document.getElementById('prov-razon').value = proveedor.razon_social;
    document.getElementById('prov-nit').value = proveedor.nit_ci || '';
    document.getElementById('prov-contacto').value = proveedor.nombre_contacto || '';
    document.getElementById('prov-telefono').value = proveedor.telefono || '';
    document.getElementById('prov-email').value = proveedor.email || '';
    
    // Cambiamos el aspecto de los botones
    document.getElementById('btn-guardar-prov').innerHTML = '🔄 Actualizar';
    document.getElementById('btn-guardar-prov').classList.replace('btn-primary', 'btn-warning');
    document.getElementById('btn-cancelar-edicion').classList.remove('d-none');
}

// --- NUEVA FUNCIÓN: LIMPIAR Y CANCELAR EDICIÓN ---
function cancelarEdicion() {
    document.getElementById('form-proveedor').reset();
    document.getElementById('prov-id').value = '';
    
    // Restauramos los botones
    document.getElementById('btn-guardar-prov').innerHTML = '💾 Guardar';
    document.getElementById('btn-guardar-prov').classList.replace('btn-warning', 'btn-primary');
    document.getElementById('btn-cancelar-edicion').classList.add('d-none');
}

async function guardarProveedor(e) {
    e.preventDefault();
    const token = localStorage.getItem('erp_token');
    const btnGuardar = document.getElementById('btn-guardar-prov');
    
    // Leemos el ID oculto para saber si es creación o actualización
    const idProveedor = document.getElementById('prov-id').value;
    
    const payload = {
        razon_social: document.getElementById('prov-razon').value.trim().toUpperCase(),
        nit_ci: document.getElementById('prov-nit').value.trim() || null,
        nombre_contacto: document.getElementById('prov-contacto').value.trim() || null,
        telefono: document.getElementById('prov-telefono').value.trim() || null,
        email: document.getElementById('prov-email').value.trim() || null
    };

    btnGuardar.disabled = true;
    btnGuardar.innerHTML = 'Procesando...';

    try {
        // Si hay un ID, hacemos PUT a /proveedores/{id}, sino hacemos POST a /proveedores/
        const url = idProveedor ? `/proveedores/${idProveedor}` : '/proveedores/';
        const method = idProveedor ? 'PUT' : 'POST';

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
            alert(idProveedor ? '✅ Proveedor actualizado con éxito.' : '✅ Proveedor registrado con éxito.');
            cancelarEdicion(); // Limpia el formulario y restaura botones
            cargarProveedores(); // Refrescamos la tabla
        } else {
            alert(`❌ Error: ${data.detail || 'No se pudo guardar el proveedor'}`);
        }
    } catch (error) {
        alert('Error de conexión con el servidor.');
    } finally {
        btnGuardar.disabled = false;
        // El texto original se restaura en la función cancelarEdicion() si fue exitoso, 
        // pero si falla, lo forzamos a volver al estado que tenía
        if (idProveedor) {
            btnGuardar.innerHTML = '🔄 Actualizar';
        } else {
            btnGuardar.innerHTML = '💾 Guardar';
        }
    }
}