let carritoItems = [];

// Creamos un formateador global para dinero (con 2 decimales y comas para miles)
const formateadorDinero = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
});

// Creamos un formateador para cantidades (sin forzar decimales si es número entero)
const formateadorCantidad = new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 2
});

document.addEventListener('DOMContentLoaded', () => {
    // Validar sesión
    const token = localStorage.getItem('erp_token');
    if (!token) {
        alert("Sesión no válida. Inicie sesión.");
        window.location.href = '/vistas/login';
        return;
    }

    cargarProveedores();

    // Configurar botones
    document.getElementById('btn-agregar-item').addEventListener('click', agregarItemTabla);
    document.getElementById('btn-guardar-oc').addEventListener('click', procesarNuevaOrden);
});

function agregarItemTabla() {
    const sku = document.getElementById('item-sku').value.trim().toUpperCase();
    const cantidad = parseFloat(document.getElementById('item-cant').value);
    const costo = parseFloat(document.getElementById('item-costo').value);

    // Validaciones básicas
    if (!sku || isNaN(cantidad) || cantidad <= 0 || isNaN(costo) || costo <= 0) {
        alert("Por favor, ingrese un SKU válido y valores numéricos mayores a 0.");
        return;
    }

    // Comprobar si el artículo ya está en la lista para sumar cantidades
    const itemExistente = carritoItems.find(item => item.sku_articulo === sku);
    if (itemExistente) {
        itemExistente.cantidad_solicitada += cantidad;
        itemExistente.costo_unitario_estimado = costo; // Actualizamos al último costo ingresado
    } else {
        carritoItems.push({
            sku_articulo: sku,
            cantidad_solicitada: cantidad,
            costo_unitario_estimado: costo
        });
    }

    // Limpiar inputs para el siguiente artículo
    document.getElementById('item-sku').value = '';
    document.getElementById('item-cant').value = '';
    document.getElementById('item-costo').value = '';
    document.getElementById('item-sku').focus();

    renderizarTabla();
}

function renderizarTabla() {
    const tbody = document.getElementById('tabla-crear-oc');
    tbody.innerHTML = '';
    let totalEstimado = 0;

    carritoItems.forEach((item, index) => {
        const subtotal = item.cantidad_solicitada * item.costo_unitario_estimado;
        totalEstimado += subtotal;

        const fila = document.createElement('tr');
        fila.innerHTML = `
            <td class="fw-bold">${item.sku_articulo}</td>
            <td class="text-center">${formateadorCantidad.format(item.cantidad_solicitada)}</td>
            <td class="text-end">${formateadorDinero.format(item.costo_unitario_estimado)}</td>
            <td class="text-end fw-bold">${formateadorDinero.format(subtotal)}</td>
            <td class="text-center">
                <button class="btn btn-sm btn-outline-danger" onclick="eliminarItem(${index})" title="Eliminar fila">
                    ❌
                </button>
            </td>
        `;
        tbody.appendChild(fila);
    });

    // Actualizar el gran total al pie de la tabla con formato
    document.getElementById('total-estimado').textContent = formateadorDinero.format(totalEstimado);
}

// Función global para que el botón ❌ la pueda encontrar
window.eliminarItem = function(index) {
    carritoItems.splice(index, 1);
    renderizarTabla();
}

async function procesarNuevaOrden() {
    const numeroOrden = document.getElementById('oc-numero').value.trim().toUpperCase();
    const proveedorId = document.getElementById('oc-proveedor').value.trim().toUpperCase();
    const notas = document.getElementById('oc-notas').value.trim();

    if (!numeroOrden || !proveedorId) {
        alert("El número de orden y el proveedor son obligatorios.");
        return;
    }

    if (carritoItems.length === 0) {
        alert("Debe agregar al menos un artículo a la orden.");
        return;
    }

    // Construimos el paquete de datos idéntico a PeticionNuevaOrden en Pydantic
    const payload = {
        numero_orden: numeroOrden,
        proveedor_id: proveedorId,
        items: carritoItems,
        notas: notas || null
    };

    const btnGuardar = document.getElementById('btn-guardar-oc');
    btnGuardar.disabled = true;
    btnGuardar.innerHTML = 'Procesando...';

    try {
        const token = localStorage.getItem('erp_token');
        const response = await fetch('/ordenes-compra/', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (response.ok) {
            alert(`✅ Orden ${data.numero_orden} creada con éxito.`);
            // Limpiamos la pantalla recargando
            window.location.reload();
        } else {
            alert(`❌ Error: ${data.detail || 'No se pudo crear la orden.'}`);
        }
    } catch (error) {
        console.error("Error al guardar OC:", error);
        alert("Error de conexión con el servidor.");
    } finally {
        btnGuardar.disabled = false;
        btnGuardar.innerHTML = '💾 Generar Orden de Compra';
    }
}

async function cargarProveedores() {
    const selectProveedor = document.getElementById('oc-proveedor');
    const token = localStorage.getItem('erp_token');

    try {
        const response = await fetch('/proveedores/', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            const proveedores = await response.json();
            selectProveedor.innerHTML = '<option value="" disabled selected>Seleccione un proveedor...</option>';
            
            proveedores.forEach(p => {
                const option = document.createElement('option');
                // Usamos el _id de la base de datos como valor, y mostramos la Razón Social y NIT
                option.value = p._id; 
                option.textContent = `${p.razon_social} ${p.nit_ci ? ' - NIT: ' + p.nit_ci : ''}`;
                selectProveedor.appendChild(option);
            });
        } else {
            selectProveedor.innerHTML = '<option value="" disabled selected>Error al cargar proveedores</option>';
        }
    } catch (error) {
        console.error("Error al cargar proveedores:", error);
        selectProveedor.innerHTML = '<option value="" disabled selected>Error de conexión</option>';
    }
}