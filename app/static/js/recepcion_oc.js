document.addEventListener('DOMContentLoaded', () => {
    // Verificar autenticación
    const token = localStorage.getItem('erp_token');
    if (!token) {
        alert("Sesión no válida. Inicie sesión nuevamente.");
        window.location.href = '/vistas/login';
        return;
    }

    const btnBuscar = document.getElementById('btn-buscar-oc');
    const btnProcesar = document.getElementById('btn-procesar-recepcion');

    if (btnBuscar) {
        btnBuscar.addEventListener('click', buscarOrdenCompra);
    }

    if (btnProcesar) {
        btnProcesar.addEventListener('click', procesarRecepcionMasiva);
    }
});

let ordenActual = null;

async function buscarOrdenCompra() {
    const numOrden = document.getElementById('input-busqueda-oc').value.trim().toUpperCase();
    if (!numOrden) {
        alert("Por favor, ingrese un número de Orden de Compra.");
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
        // Buscamos la orden correspondiente
        ordenActual = ordenes.find(o => o.numero_orden.toUpperCase() === numOrden);

        if (!ordenActual) {
            alert(`No se encontró la Orden de Compra '${numOrden}'.`);
            document.getElementById('contenedor-recepcion').classList.add('d-none');
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

    orden.items.forEach((item, index) => {
        const pendiente = item.cantidad_solicitada - item.cantidad_recibida;
        const disabled = pendiente <= 0 ? 'disabled' : '';

        const fila = document.createElement('tr');
        fila.innerHTML = `
            <td class="fw-bold">${item.sku_articulo}</td>
            <td class="text-center">${item.cantidad_solicitada}</td>
            <td class="text-center text-muted">${item.cantidad_recibida}</td>
            <td class="text-center">
                <input type="number" 
                       class="form-control form-control-sm text-center input-a-recibir" 
                       data-sku="${item.sku_articulo}"
                       data-max="${pendiente}"
                       value="${pendiente > 0 ? pendiente : 0}" 
                       min="0" 
                       max="${pendiente}" 
                       step="0.01" 
                       ${disabled}>
            </td>
        `;
        tbody.appendChild(fila);
    });

    document.getElementById('contenedor-recepcion').classList.remove('d-none');
}

function getBadgeClass(estado) {
    switch (estado) {
        case 'COMPLETADA': return 'bg-success';
        case 'RECEPCION_PARCIAL': return 'bg-warning text-dark';
        case 'CANCELADA': return 'bg-danger';
        default: return 'bg-secondary';
    }
}

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

    inputs.forEach(input => {
        const cant = parseFloat(input.value) || 0;
        const sku = input.getAttribute('data-sku');
        const max = parseFloat(input.getAttribute('data-max'));

        if (cant > max) {
            alert(`La cantidad a recibir para ${sku} excede el saldo pendiente (${max}).`);
            return;
        }

        if (cant > 0) {
            itemsARecibir.push({
                sku_articulo: sku,
                cantidad_a_recibir: cant
            });
        }
    });

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
            // Volver a consultar la orden para refrescar las cantidades recibidas
            buscarOrdenCompra();
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