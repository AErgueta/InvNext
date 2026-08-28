let ordenActualPago = null;

// Reutilizamos nuestro formateador para que los montos se vean bien
const formateadorDinero = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
});

document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('erp_token');
    if (!token) {
        alert("Sesión no válida. Inicie sesión.");
        window.location.href = '/vistas/login';
        return;
    }

    const btnBuscar = document.getElementById('btn-buscar-pago');
    if (btnBuscar) btnBuscar.addEventListener('click', buscarOrdenParaPago);

    const btnProcesar = document.getElementById('btn-procesar-pago');
    if (btnProcesar) btnProcesar.addEventListener('click', procesarPago);
});

async function buscarOrdenParaPago() {
    const numOrden = document.getElementById('input-busqueda-pago').value.trim().toUpperCase();
    if (!numOrden) {
        alert("Ingrese un número de Orden de Compra.");
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

        if (!response.ok) throw new Error("Error al obtener las órdenes.");

        const ordenes = await response.json();
        ordenActualPago = ordenes.find(o => o.numero_orden.toUpperCase() === numOrden);

        if (!ordenActualPago) {
            alert(`No se encontró la orden '${numOrden}'.`);
            document.getElementById('contenedor-pago').classList.add('d-none');
            return;
        }

        renderizarResumenPago(ordenActualPago);

    } catch (error) {
        console.error("Error al buscar OC:", error);
        alert(`Ocurrió un error: ${error.message}`);
    }
}

function renderizarResumenPago(orden) {
    const badge = document.getElementById('badge-estado-pago');
    badge.textContent = orden.estado_pago;
    
    if (orden.estado_pago === 'PAGADO') {
        badge.className = 'badge bg-success';
    } else if (orden.estado_pago === 'PAGO_PARCIAL') {
        badge.className = 'badge bg-warning text-dark';
    } else {
        badge.className = 'badge bg-secondary';
    }

    // Llenamos el estado de cuenta
    document.getElementById('resumen-total').textContent = formateadorDinero.format(orden.monto_total);
    document.getElementById('resumen-pagado').textContent = formateadorDinero.format(orden.monto_pagado);

    const saldo = orden.monto_total - orden.monto_pagado;
    document.getElementById('resumen-saldo').textContent = formateadorDinero.format(saldo);

    // Autocompletamos el input de pago con lo que falta
    const inputMonto = document.getElementById('pago-monto');
    inputMonto.value = saldo > 0 ? saldo.toFixed(2) : 0;
    
    // Si ya está pagado, bloqueamos el botón
    const btnProcesar = document.getElementById('btn-procesar-pago');
    if (saldo <= 0) {
        btnProcesar.disabled = true;
        btnProcesar.innerHTML = 'Orden Totalmente Pagada';
    } else {
        btnProcesar.disabled = false;
        btnProcesar.innerHTML = '<i class="bi bi-check-circle"></i> Confirmar Pago';
    }

    document.getElementById('contenedor-pago').classList.remove('d-none');
}

async function procesarPago() {
    if (!ordenActualPago) return;

    const monto = parseFloat(document.getElementById('pago-monto').value);
    const metodo = document.getElementById('pago-metodo').value;
    const referencia = document.getElementById('pago-referencia').value.trim().toUpperCase();

    const saldo = ordenActualPago.monto_total - ordenActualPago.monto_pagado;

    if (isNaN(monto) || monto <= 0) {
        alert("Ingrese un monto mayor a 0.");
        return;
    }
    if (monto > saldo) {
        alert(`El pago no puede ser mayor a la deuda (Saldo: ${saldo.toFixed(2)}).`);
        return;
    }
    if (!metodo) {
        alert("Debe elegir un método de pago.");
        return;
    }
    if (!referencia) {
        alert("La referencia o número de comprobante es obligatoria.");
        return;
    }

    // Construimos el PeticionPago para el backend
    const payload = {
        monto: monto,
        metodo_pago: metodo,
        referencia: referencia
    };

    const btnProcesar = document.getElementById('btn-procesar-pago');
    btnProcesar.disabled = true;
    btnProcesar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Registrando...';

    try {
        const token = localStorage.getItem('erp_token');
        const response = await fetch(`/ordenes-compra/${ordenActualPago.numero_orden}/pagar`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (response.ok) {
            alert(`✅ ${data.mensaje}. Saldo restante: ${data.resumen_financiero.saldo_pendiente}`);
            buscarOrdenParaPago(); // Refrescamos la pantalla
            
            // Limpiamos los inputs
            document.getElementById('pago-metodo').value = "";
            document.getElementById('pago-referencia').value = "";
        } else {
            alert(`❌ Error: ${data.detail || 'No se pudo registrar el pago.'}`);
        }
    } catch (error) {
        console.error("Error en pago:", error);
        alert("Error de conexión con el servidor.");
    } finally {
        if (btnProcesar.disabled === false || btnProcesar.innerHTML.includes('Registrando')) {
             btnProcesar.disabled = false;
             btnProcesar.innerHTML = '<i class="bi bi-check-circle"></i> Confirmar Pago';
        }
    }
}