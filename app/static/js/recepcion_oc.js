let ordenActual = null;

document.addEventListener('DOMContentLoaded', () => {
    // Verificar autenticación
    const token = localStorage.getItem('erp_token');
    if (!token) {
        alert("Sesión no válida. Inicie sesión nuevamente.");
        window.location.href = '/vistas/login';
        return;
    }

    // 1. Cargar las órdenes pendientes en el select apenas entramos a la pantalla
    cargarOrdenesPendientes();

    // 2. Asignar eventos a los botones
    const btnBuscar = document.getElementById('btn-buscar-oc');
    const btnProcesar = document.getElementById('btn-procesar-recepcion');
    const btnAnular = document.getElementById('btn-anular-oc');

    if (btnBuscar) {
        btnBuscar.addEventListener('click', buscarOrdenCompra);
    }

    if (btnProcesar) {
        btnProcesar.addEventListener('click', procesarRecepcionMasiva);
    }
    
    if (btnAnular) {
        btnAnular.addEventListener('click', anularOrden);
    }
});

// --- NUEVA FUNCIÓN: Llenar el Select de Órdenes ---
async function cargarOrdenesPendientes() {
    const token = localStorage.getItem('erp_token');
    const select = document.getElementById('oc-numero-select');
    
    try {
        const response = await fetch('/ordenes-compra/', {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const ordenes = await response.json();
            
            // Filtramos solo las que necesitan ser procesadas
            const ordenesActivas = ordenes.filter(o => 
                o.estado === 'PENDIENTE' || o.estado === 'RECEPCION_PARCIAL'
            );
            
            select.innerHTML = '<option value="" disabled selected>Seleccione una Orden...</option>';
            
            if (ordenesActivas.length === 0) {
                select.innerHTML = '<option value="" disabled selected>No hay órdenes pendientes</option>';
                return;
            }
            
            ordenesActivas.forEach(o => {
                const texto = `${o.numero_orden} - ${o.estado} (Bs. ${o.monto_total})`;
                select.innerHTML += `<option value="${o.numero_orden}">${texto}</option>`;
            });
        } else {
             select.innerHTML = '<option value="" disabled selected>Error al cargar órdenes</option>';
        }
    } catch (error) {
        console.error("Error al cargar órdenes:", error);
        select.innerHTML = '<option value="" disabled selected>Error de conexión</option>';
    }
}

// --- FUNCIÓN MODIFICADA: Buscar y Renderizar leyendo del Select ---
async function buscarOrdenCompra() {
    const select = document.getElementById('oc-numero-select');
    const numOrden = select.value;
    
    if (!numOrden) {
        alert("Por favor, seleccione una Orden de Compra del listado.");
        return;
    }

    const token = localStorage.getItem('erp_token');
    
    try {
        const response = await fetch(`/ordenes-compra/`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) throw new Error("Error al obtener las órdenes de compra.");

        const ordenes = await response.json();
        ordenActual = ordenes.find(o => o.numero_orden === numOrden);

        if (!ordenActual) {
            alert(`No se encontró la Orden de Compra '${numOrden}'.`);
            document.getElementById('contenedor-recepcion').classList.add('d-none');
            document.getElementById('btn-anular-oc').classList.add('d-none');
            return;
        }

        renderizarDetalleOrden(ordenActual);

    } catch (error) {
        console.error("Error al buscar OC:", error);
        alert(`Ocurrió un error: ${error.message}`);
    }
}

function renderizarDetalleOrden(orden) {
    const badgeEstado = document.getElementById('badge-estado-oc');
    badgeEstado.textContent = orden.estado;
    badgeEstado.className = `badge ${getBadgeClass(orden.estado)}`;

    const tbody = document.getElementById('tabla-items-oc');
    tbody.innerHTML = "";

    orden.items.forEach((item) => {
        const pendiente = item.cantidad_solicitada - item.cantidad_recibida;
        const disabled = pendiente <= 0 ? 'disabled' : '';

        // Usamos costo_unitario_estimado que viene de la orden original
        const costoUnitario = item.costo_unitario_estimado || 0;

        const fila = document.createElement('tr');
        fila.innerHTML = `
            <td class="fw-bold">${item.sku_articulo}</td>
            <td class="text-center">${item.cantidad_solicitada}</td>
            <td class="text-center text-muted">${item.cantidad_recibida}</td>
            <td class="text-center">
                <input type="number" class="form-control form-control-sm text-end input-costo" 
                       data-sku="${item.sku_articulo}" value="${costoUnitario}" min="0" step="0.01" ${disabled}>
            </td>
            <td class="text-center">
                <input type="date" class="form-control form-control-sm input-vencimiento" 
                       data-sku="${item.sku_articulo}" ${disabled}>
            </td>
            <td class="text-center">
                <input type="number" 
                       class="form-control form-control-sm text-center input-a-recibir" 
                       data-sku="${item.sku_articulo}"
                       data-max="${pendiente}"
                       value="${pendiente > 0 ? pendiente : 0}" 
                       min="0" max="${pendiente}" step="0.01" ${disabled}>
            </td>
        `;
        tbody.appendChild(fila);
    });

    document.getElementById('contenedor-recepcion').classList.remove('d-none');
    
    // Aparece el botón de anular mágicamente
    document.getElementById('btn-anular-oc').classList.remove('d-none');
}

function getBadgeClass(estado) {
    switch (estado) {
        case 'COMPLETADA': return 'bg-success';
        case 'RECEPCION_PARCIAL': return 'bg-warning text-dark';
        case 'CANCELADA': return 'bg-danger';
        default: return 'bg-secondary';
    }
}

// --- NUEVA FUNCIÓN: Anular la Orden ---
async function anularOrden() {
    const select = document.getElementById('oc-numero-select');
    const numeroOrden = select.value;
    
    if (!numeroOrden) return;
    
    const confirmacion = confirm(`¿Estás completamente seguro de que deseas ANULAR la orden ${numeroOrden}? Esta acción no se puede deshacer.`);
    if (!confirmacion) return;
    
    const token = localStorage.getItem('erp_token');
    const btnAnular = document.getElementById('btn-anular-oc');
    btnAnular.disabled = true;
    
    try {
        const response = await fetch(`/ordenes-compra/${numeroOrden}/anular`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert(`✅ ${data.mensaje}`);
            window.location.reload(); // Recarga la página para refrescar el combo
        } else {
            alert(`❌ Error: ${data.detail}`);
        }
    } catch (error) {
        alert("Error de conexión con el servidor.");
    } finally {
        btnAnular.disabled = false;
    }
}

// --- FUNCIÓN MODIFICADA: Procesar Recepción Masiva ---
async function procesarRecepcionMasiva() {
    if (!ordenActual) return;

    const codigoAlmacen = document.getElementById('recepcion-almacen').value.trim();
    const flujoSeleccionado = document.getElementById('recepcion-flujo').value;

    if (!codigoAlmacen) {
        alert("Debe especificar un almacén de destino.");
        return;
    }

    if (!flujoSeleccionado) {
        alert("⚠️ Debe elegir manualmente un flujo de seguimiento obligatoriamente.");
        return;
    }

    const inputs = document.querySelectorAll('.input-a-recibir');
    const itemsARecibir = [];
    let errorValidacion = false;

    inputs.forEach(input => {
        const cant = parseFloat(input.value) || 0;
        const sku = input.getAttribute('data-sku');
        const max = parseFloat(input.getAttribute('data-max'));

        if (cant > max) {
            alert(`La cantidad a recibir para ${sku} excede el saldo pendiente (${max}).`);
            errorValidacion = true;
            return;
        }

        if (cant > 0) {
            const inputCosto = document.querySelector(`.input-costo[data-sku="${sku}"]`);
            const inputVencimiento = document.querySelector(`.input-vencimiento[data-sku="${sku}"]`);
            
            const costo = parseFloat(inputCosto.value) || 0;
            const vencimiento = inputVencimiento.value;

            itemsARecibir.push({
                sku_articulo: sku,
                cantidad_a_recibir: cant,
                costo_unitario: costo,
                // Permitimos enviar null si el campo está vacío (ideal para artículos sin lote como la Escoba)
                fecha_vencimiento: vencimiento || null
            });
        }
    });

    if (errorValidacion) return;

    if (itemsARecibir.length === 0) {
        alert("Debe ingresar al menos una cantidad mayor a 0 para procesar la recepción.");
        return;
    }

    const payload = {
        codigo_almacen: codigoAlmacen,
        id_referencia: ordenActual.numero_orden,
        flujo_trabajo_seleccionado: flujoSeleccionado,
        items_recibidos: itemsARecibir
    };

    const btnProcesar = document.getElementById('btn-procesar-recepcion');
    btnProcesar.disabled = true;
    btnProcesar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Procesando...';

    try {
        const token = localStorage.getItem('erp_token');
        const response = await fetch(`/ordenes-compra/${ordenActual.numero_orden}/recibir`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (response.ok) {
            alert(`✅ ${data.mensaje}\nMovimientos de entrada generados: ${data.movimientos_creados}`);
            window.location.reload(); 
        } else {
            alert(`❌ Error: ${data.detail || 'No se pudo procesar la recepción.'}`);
        }
    } catch (error) {
        console.error("Error al procesar recepción:", error);
        alert("Error de conexión con el servidor.");
    } finally {
        btnProcesar.disabled = false;
        btnProcesar.innerHTML = '<i class="bi bi-check2-all"></i> Procesar Recepción Completa';
    }
}