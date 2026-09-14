// ==========================================
// ESTADO GLOBAL DEL CARRITO
// ==========================================
let carrito = [];
let totalVentaActual = 0; // Guardamos el total para calcular el cambio

// ==========================================
// ELEMENTOS DEL DOM
// ==========================================
const inputBuscador = document.getElementById('pos-buscador');
const dropdownResultados = document.getElementById('dropdown-resultados-pos');
const tbodyCarrito = document.getElementById('carrito-body');
const btnCobrar = document.getElementById('btn-cobrar');
const selectFlujo = document.getElementById('pos-flujo');
const inputDescuento = document.getElementById('pos-descuento');

// Elementos de Método de Pago
const selectMetodoPago = document.getElementById('pos-metodo-pago');
const cajaEfectivo = document.getElementById('caja-efectivo');
const cajaReferencia = document.getElementById('caja-referencia');
const inputRecibido = document.getElementById('pos-recibido');
const textCambio = document.getElementById('pos-cambio');
const inputReferencia = document.getElementById('pos-referencia');

let timeoutBusqueda;

// Utilidad para formatear moneda
const formatearMoneda = (valor) => {
    return new Intl.NumberFormat('es-BO', { 
        minimumFractionDigits: 2, 
        maximumFractionDigits: 2 
    }).format(valor);
};

// ==========================================
// CONTROL DE SESIÓN DE CAJA MULTISUCURSAL
// ==========================================
// TODO: Estos valores deberían venir del login del usuario o de un selector previo
const CONTEXTO_ACTUAL = {
    sucursal_id: "SUC-CENTRAL", // Valor temporal para pruebas
    caja_id: "CAJA-01-CENTRAL"  // Valor temporal para pruebas
};

let sesionCajaActiva = false;
const modalApertura = new bootstrap.Modal(document.getElementById('modalAperturaCaja'));
const modalCierre = new bootstrap.Modal(document.getElementById('modalCierreCaja'));

async function verificarEstadoCaja() {
    try {
        const response = await fetch(`/cajas/${CONTEXTO_ACTUAL.caja_id}/estado`);
        const data = await response.json();
        
        if (data.abierta) {
            sesionCajaActiva = true;
            // Desbloquear interfaz
            inputBuscador.disabled = false;
        } else {
            sesionCajaActiva = false;
            // Bloquear interfaz y forzar apertura
            inputBuscador.disabled = true;
            modalApertura.show();
        }
    } catch (error) {
        console.error("Error al verificar estado de la caja:", error);
    }
}

// Ejecutar al iniciar la pantalla
document.addEventListener('DOMContentLoaded', verificarEstadoCaja);

// --- ACCIÓN: ABRIR CAJA ---
document.getElementById('btn-abrir-caja').addEventListener('click', async () => {
    const monto = parseFloat(document.getElementById('input-monto-inicial').value) || 0;
    
    try {
        const token = localStorage.getItem("erp_token");
        const response = await fetch('/cajas/abrir', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                caja_id: CONTEXTO_ACTUAL.caja_id,
                sucursal_id: CONTEXTO_ACTUAL.sucursal_id,
                monto_inicial: monto
            })
        });

        if (response.ok) {
            modalApertura.hide();
            sesionCajaActiva = true;
            inputBuscador.disabled = false;
            inputBuscador.focus();
            reproducirBeep(true);
        } else {
            const error = await response.json();
            alert("Error: " + error.detail);
        }
    } catch (error) {
        console.error("Error abriendo caja:", error);
    }
});

// --- ACCIÓN: CERRAR CAJA ---
document.getElementById('btn-procesar-cierre').addEventListener('click', async () => {
    const montoReal = parseFloat(document.getElementById('input-monto-cierre').value) || 0;
    const checkConfirmar = document.getElementById('check-confirmar-diferencia').checked;
    
    if(!confirm(`¿Declarar Bs. ${montoReal} como tu efectivo final?`)) return;

    try {
        const token = localStorage.getItem("erp_token");
        const response = await fetch(`/cajas/${CONTEXTO_ACTUAL.caja_id}/cerrar`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ 
                monto_cierre_real: montoReal,
                confirmar_diferencia: checkConfirmar
            })
        });

        const data = await response.json();
        
        if (response.ok) {
            if (data.requiere_confirmacion) {
                // EL BACKEND DETUVO EL CIERRE. MOSTRAR ALERTA PARA RECTIFICAR.
                document.getElementById('alerta-descuadre').classList.remove('d-none');
                document.getElementById('texto-descuadre').innerText = data.mensaje;
                // Desmarcar el check por seguridad
                document.getElementById('check-confirmar-diferencia').checked = false;
            } else {
                // EL CIERRE FUE EXITOSO (Cuadre perfecto o diferencia confirmada)
                modalCierre.hide();
                // alert(`Arqueo Exitoso.\n\nSistema: Bs. ${formatearMoneda(data.monto_calculado_sistema)}\nDeclarado: Bs. ${formatearMoneda(data.monto_declarado_cajero)}\nDiferencia: Bs. ${formatearMoneda(data.diferencia)}\nEstado: ${data.cuadre}`);
                
                // MANDAR A IMPRIMIR EL REPORTE Z
                imprimirReporteCierre(data);

                // RECARGAR CON RETRASO
                setTimeout(() => {
                    window.location.reload(); 
                }, 1500);
            }
        } else {
            alert("Error: " + data.detail);
        }
    } catch (error) {
        console.error("Error cerrando caja:", error);
    }
});

// Ocultar alerta de descuadre si el usuario modifica el monto (significa que está rectificando)
document.getElementById('input-monto-cierre').addEventListener('input', () => {
    document.getElementById('alerta-descuadre').classList.add('d-none');
    document.getElementById('check-confirmar-diferencia').checked = false;
});


// ==========================================
// EFECTOS DE SONIDO (NATIVO DEL NAVEGADOR)
// ==========================================
function reproducirBeep(exito = true) {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return; 
    
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    
    osc.connect(gain);
    gain.connect(ctx.destination);
    
    if (exito) {
        osc.type = 'sine';
        osc.frequency.value = 800; 
        gain.gain.setValueAtTime(0.1, ctx.currentTime);
        osc.start();
        osc.stop(ctx.currentTime + 0.1); 
    } else {
        osc.type = 'sawtooth';
        osc.frequency.value = 150; 
        gain.gain.setValueAtTime(0.1, ctx.currentTime);
        osc.start();
        osc.stop(ctx.currentTime + 0.3); 
    }
}

// ==========================================
// LÓGICA DEL BUSCADOR INTELIGENTE Y ESCÁNER
// ==========================================
inputBuscador.addEventListener('input', (e) => {
    clearTimeout(timeoutBusqueda);
    const query = e.target.value.trim();

    if (query.length < 2) {
        dropdownResultados.classList.remove('show');
        return;
    }

    timeoutBusqueda = setTimeout(async () => {
        try {
            const token = localStorage.getItem("erp_token"); 
            const response = await fetch(`/articulos/buscar?q=${encodeURIComponent(query)}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            if (!response.ok) return;
            
            const resultados = await response.json();
            dropdownResultados.innerHTML = '';
            
            if (resultados.length === 0) {
                dropdownResultados.innerHTML = '<li><span class="dropdown-item text-muted">No encontrado</span></li>';
            } else {
                resultados.forEach(art => {
                    const li = document.createElement('li');
                    li.innerHTML = `<a class="dropdown-item py-2" href="#" style="cursor: pointer; white-space: normal;">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <strong>${art.sku}</strong><br>
                                <span class="text-wrap">${art.nombre}</span>
                                ${art.codigo_barras ? `<br><small class="text-muted"><i class="bi bi-upc"></i> ${art.codigo_barras}</small>` : ''}
                            </div>
                            <span class="badge bg-success rounded-pill">$${art.precio_venta || 0}</span>
                        </div>
                    </a>`;
                    
                    li.addEventListener('click', (evento) => {
                        evento.preventDefault();
                        agregarAlCarrito({
                            sku_articulo: art.sku,
                            nombre_articulo: art.nombre,
                            precio_unitario: art.precio_venta || 0,
                            stock_actual: art.stock_en_almacen !== undefined ? art.stock_en_almacen : art.stock_actual 
                        });
                        inputBuscador.value = '';
                        dropdownResultados.classList.remove('show');
                        inputBuscador.focus(); 
                    });
                    
                    dropdownResultados.appendChild(li);
                });
            }
            dropdownResultados.classList.add('show');
            
        } catch (error) {
            console.error("Error buscando:", error);
        }
    }, 300);
});

inputBuscador.addEventListener('keypress', async (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        dropdownResultados.classList.remove('show');
        
        const query = inputBuscador.value.trim();
        if(query) {
            try {
                const token = localStorage.getItem("erp_token");
                const response = await fetch(`/articulos/buscar?q=${encodeURIComponent(query)}`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                
                if (response.ok) {
                    const resultados = await response.json();
                    if (resultados.length > 0) {
                        const art = resultados[0];
                        agregarAlCarrito({
                            sku_articulo: art.sku,
                            nombre_articulo: art.nombre,
                            precio_unitario: art.precio_venta || 0,
                            stock_actual: art.stock_en_almacen !== undefined ? art.stock_en_almacen : art.stock_actual
                        });
                        inputBuscador.value = ''; 
                    } else {
                        reproducirBeep(false); 
                        alert("❌ Artículo no encontrado.");
                        inputBuscador.select(); 
                    }
                }
            } catch (error) {
                console.error("Error con el escáner:", error);
                reproducirBeep(false);
            }
        }
    }
});

document.addEventListener('click', (e) => {
    if (!inputBuscador.contains(e.target) && !dropdownResultados.contains(e.target)) {
        dropdownResultados.classList.remove('show');
    }
});

// ==========================================
// GESTIÓN DEL CARRITO Y MATEMÁTICAS 
// ==========================================
function agregarAlCarrito(producto) {
    const stockDisponible = producto.stock_actual !== undefined ? producto.stock_actual : 0;

    if (stockDisponible <= 0) {
        reproducirBeep(false);
        alert(`❌ El artículo ${producto.nombre_articulo} no tiene stock disponible.`);
        return;
    }

    const itemExistente = carrito.find(item => item.sku_articulo === producto.sku_articulo);
    
    if (itemExistente) {
        if (itemExistente.cantidad + 1 > stockDisponible) {
            reproducirBeep(false);
            alert(`⚠️ Stock máximo alcanzado. Solo hay ${stockDisponible} unidades disponibles.`);
            return;
        }
        itemExistente.cantidad += 1;
        itemExistente.subtotal_linea = itemExistente.cantidad * itemExistente.precio_unitario;
    } else {
        carrito.push({
            sku_articulo: producto.sku_articulo,
            nombre_articulo: producto.nombre_articulo,
            precio_unitario: producto.precio_unitario,
            cantidad: 1,
            stock: stockDisponible,
            descuento_linea: 0.0,
            subtotal_linea: producto.precio_unitario
        });
    }
    
    reproducirBeep(true);
    actualizarVista(producto.sku_articulo);
}

function actualizarCantidad(sku, nuevaCantidad) {
    const item = carrito.find(i => i.sku_articulo === sku);
    if (!item) return;

    let cantidadDeseada = parseInt(nuevaCantidad) || 1;
    if (cantidadDeseada > item.stock) {
        reproducirBeep(false);
        alert(`⚠️ No puedes vender ${cantidadDeseada} unidades. El stock máximo en almacén es de ${item.stock}.`);
        cantidadDeseada = item.stock;
    }
    if (cantidadDeseada < 1) cantidadDeseada = 1;

    item.cantidad = cantidadDeseada;
    item.subtotal_linea = (item.cantidad * item.precio_unitario) - (item.descuento_linea || 0);
    actualizarVista();
}

function eliminarDelCarrito(sku) {
    carrito = carrito.filter(item => item.sku_articulo !== sku);
    actualizarVista();
}

function actualizarDescuentoLinea(sku, nuevoDescuento) {
    const item = carrito.find(i => i.sku_articulo === sku);
    if (item) {
        let desc = parseFloat(nuevoDescuento) || 0;
        const maxDescuento = item.cantidad * item.precio_unitario;
        if (desc > maxDescuento) desc = maxDescuento;
        
        item.descuento_linea = desc;
        item.subtotal_linea = (item.cantidad * item.precio_unitario) - item.descuento_linea;
        actualizarVista();
    }
}

function actualizarPrecioUnitario(sku, nuevoPrecio) {
    const item = carrito.find(i => i.sku_articulo === sku);
    if (item) {
        let precio = parseFloat(nuevoPrecio) || 0;
        if (precio < 0) precio = 0; 
        
        item.precio_unitario = precio;
        item.subtotal_linea = (item.cantidad * item.precio_unitario) - (item.descuento_linea || 0);
        actualizarVista();
    }
}

// ==========================================
// RENDERIZADO Y CONTROL DE PAGOS
// ==========================================
function actualizarVista(skuDestacado = null) {
    tbodyCarrito.innerHTML = '';
    let subtotalGeneral = 0;

    if (carrito.length === 0) {
        tbodyCarrito.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-muted py-4">
                    <i class="bi bi-cart-x fs-1 d-block mb-2"></i>
                    El carrito está vacío
                </td>
            </tr>`;
    } else {
        carrito.forEach(item => {
            subtotalGeneral += item.subtotal_linea;
            const tr = document.createElement('tr');
            if (item.sku_articulo === skuDestacado) tr.classList.add('fila-destello');
            
            tr.innerHTML = `
                <td class="fw-bold align-middle">${item.sku_articulo}</td>
                <td class="align-middle">${item.nombre_articulo}</td>
                <td><input type="number" class="form-control form-control-sm text-center fw-bold" value="${item.cantidad}" min="1" max="${item.stock}" onchange="actualizarCantidad('${item.sku_articulo}', this.value)"></td>
                <td><input type="number" class="form-control form-control-sm text-end fw-bold" value="${item.precio_unitario}" min="0" step="0.10" onchange="actualizarPrecioUnitario('${item.sku_articulo}', this.value)"></td>
                <td><input type="number" class="form-control form-control-sm text-center text-danger" value="${item.descuento_linea || 0}" min="0" step="0.5" onchange="actualizarDescuentoLinea('${item.sku_articulo}', this.value)"></td>
                <td class="text-end fw-bold align-middle fs-5">${formatearMoneda(item.subtotal_linea)}</td>
                <td class="text-center align-middle">
                    <button class="btn btn-sm btn-outline-danger" onclick="eliminarDelCarrito('${item.sku_articulo}')" title="Eliminar línea"><i class="bi bi-trash"></i></button>
                </td>
            `;
            tbodyCarrito.appendChild(tr);
        });
    }

    const descuentoGlobal = parseFloat(inputDescuento.value) || 0;
    totalVentaActual = subtotalGeneral - descuentoGlobal;

    document.getElementById('pos-subtotal').textContent = formatearMoneda(subtotalGeneral);
    document.getElementById('pos-total').textContent = formatearMoneda(totalVentaActual);
    
    calcularCambio(); 
}

inputDescuento.addEventListener('input', actualizarVista);

// Control visual del Método de Pago
selectMetodoPago.addEventListener('change', (e) => {
    const metodo = e.target.value;
    if (metodo === 'EFECTIVO') {
        cajaEfectivo.classList.remove('d-none');
        cajaReferencia.classList.add('d-none');
        inputRecibido.focus();
        calcularCambio();
    } else {
        cajaEfectivo.classList.add('d-none');
        cajaReferencia.classList.remove('d-none');
        inputReferencia.focus();
        btnCobrar.disabled = carrito.length === 0;
    }
});

function calcularCambio() {
    if (selectMetodoPago.value !== 'EFECTIVO') return;

    const recibido = parseFloat(inputRecibido.value) || 0;
    const cambio = recibido - totalVentaActual;
    
    textCambio.textContent = formatearMoneda(cambio > 0 ? cambio : 0);

    // Bloquear el cobro si es efectivo y el pago no alcanza (o si el carrito está vacío)
    if (carrito.length === 0 || (recibido < totalVentaActual && totalVentaActual > 0)) {
        textCambio.classList.replace('text-primary', 'text-danger');
        btnCobrar.disabled = true;
    } else {
        textCambio.classList.replace('text-danger', 'text-primary');
        btnCobrar.disabled = false; 
    }
}

inputRecibido.addEventListener('input', calcularCambio);

// ==========================================
// PROCESAR LA VENTA 
// ==========================================
btnCobrar.addEventListener('click', async () => {
    const flujoSeleccionado = selectFlujo.value;
    if (!flujoSeleccionado) {
        alert("¡Alto! Debes seleccionar un Flujo de Seguimiento manualmente para esta venta.");
        selectFlujo.focus();
        return;
    }

    const payloadVenta = {
        cliente: document.getElementById('pos-cliente').value,
        documento_cliente: document.getElementById('pos-documento').value,
        almacen_origen: document.getElementById('pos-almacen').value,
        flujo_trabajo_seleccionado: flujoSeleccionado,
        articulos: carrito,
        descuento_global: parseFloat(inputDescuento.value) || 0,
        condicion_pago: document.getElementById('pos-condicion').value,
        metodo_pago: selectMetodoPago.value,
        efectivo_recibido: selectMetodoPago.value === 'EFECTIVO' ? (parseFloat(inputRecibido.value) || 0) : totalVentaActual,
        referencia_pago: selectMetodoPago.value !== 'EFECTIVO' ? inputReferencia.value : "N/A",
        // --- NUEVOS CAMPOS: MULTISUCURSAL ---
        sucursal_id: CONTEXTO_ACTUAL.sucursal_id,
        caja_id: CONTEXTO_ACTUAL.caja_id
    };

    try {
        btnCobrar.disabled = true;
        btnCobrar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Procesando...';
        const token = localStorage.getItem("erp_token");

        const resVenta = await fetch('/ventas/', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(payloadVenta)
        });

        if (!resVenta.ok) throw new Error("Error al crear la venta");
        const dataVenta = await resVenta.json();
        const ventaId = dataVenta.venta_id;

        const resDespacho = await fetch(`/ventas/${ventaId}/despachar`, {
            method: 'PUT',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!resDespacho.ok) throw new Error("Error al despachar el inventario");

        reproducirBeep(true); 

        // Modificamos para enviar el dinero recibido al ticket
        imprimirTicket(
            dataVenta.folio,
            document.getElementById('pos-cliente').value,
            document.getElementById('pos-documento').value,
            carrito,
            parseFloat(inputDescuento.value) || 0,
            payloadVenta.efectivo_recibido,
            selectMetodoPago.value
        );
        
        // Reset de caja
        carrito = [];
        actualizarVista();
        document.getElementById('pos-cliente').value = "Cliente Mostrador";
        document.getElementById('pos-documento').value = "S/N";
        selectFlujo.value = "";
        inputDescuento.value = "0";
        inputRecibido.value = "";
        inputReferencia.value = "";
        
    } catch (error) {
        reproducirBeep(false); 
        alert("Ocurrió un problema: " + error.message);
        console.error(error);
    } finally {
        btnCobrar.innerHTML = '<i class="bi bi-cash-coin"></i> PROCESAR COBRO';
        // La validación de botones la hace actualizarVista
    }
});

// ==========================================
// BÚSQUEDA AUTOMÁTICA DE CLIENTE
// ==========================================
const inputDocumento = document.getElementById('pos-documento');
const inputCliente = document.getElementById('pos-cliente');

inputDocumento.addEventListener('change', async (e) => {
    const documento = e.target.value.trim();
    if (!documento || documento.toUpperCase() === 'S/N') {
        inputCliente.value = "Cliente Mostrador";
        return;
    }
    try {
        const resp = await fetch(`/clientes/buscar/${documento}`);
        if (resp.ok) {
            const data = await resp.json();
            inputCliente.value = data.nombre_razon_social;
        } else {
            inputCliente.value = "";
            inputCliente.placeholder = "Escriba el nombre del nuevo cliente...";
            inputCliente.focus();
        }
    } catch (error) {
        console.error("Error buscando cliente:", error);
        inputCliente.value = "";
    }
});

// ==========================================
// MÓDULO DE IMPRESIÓN DE TICKET
// ==========================================
function imprimirTicket(folio, cliente, documento, carrito, descuentoGlobal, recibido, metodo) {
    const subtotal = carrito.reduce((acc, item) => acc + item.subtotal_linea, 0);
    const total = subtotal - descuentoGlobal;
    const cambio = recibido - total;
    
    const ventana = window.open('', '_blank', 'width=400,height=600');
    
    let filasHTML = '';
    carrito.forEach(item => {
        filasHTML += `
            <tr>
                <td style="vertical-align: top;">${item.cantidad}</td>
                <td>${item.nombre_articulo}<br><small>${item.sku_articulo}</small></td>
                <td style="text-align: right; vertical-align: top;">${formatearMoneda(item.subtotal_linea)}</td>
            </tr>
        `;
    });

    const html = `
        <!DOCTYPE html>
        <html>
        <head>
            <title>Ticket ${folio}</title>
            <style>
                body { font-family: 'Courier New', Courier, monospace; font-size: 12px; margin: 0; padding: 10px; width: 100%; max-width: 300px; }
                .center { text-align: center; }
                .right { text-align: right; }
                table { width: 100%; border-collapse: collapse; margin: 10px 0; }
                th, td { padding: 4px 0; border-bottom: 1px dashed #ddd; }
                th { border-bottom: 1px dashed #000; border-top: 1px dashed #000; }
                .fw-bold { font-weight: bold; }
                .totales { margin-top: 10px; border-top: 2px solid #000; padding-top: 10px; }
                @media print { @page { margin: 0; } body { margin: 1cm; } }
            </style>
        </head>
        <body>
            <div class="center">
                <h2>MI EMPRESA</h2>
                <p>Santa Cruz de la Sierra, Bolivia</p>
                <p>NIT: 1234567015</p>
                <p>--------------------------------</p>
                <h3>TICKET DE VENTA</h3>
                <p class="fw-bold">Folio: ${folio}</p>
            </div>
            <p>
                <strong>Cliente:</strong> ${cliente}<br>
                <strong>NIT/CI:</strong> ${documento}<br>
                <strong>Fecha:</strong> ${new Date().toLocaleString('es-BO')}
            </p>
            <table>
                <thead>
                    <tr>
                        <th style="text-align: left; width: 15%;">Cant</th>
                        <th style="text-align: left; width: 55%;">Descripción</th>
                        <th style="text-align: right; width: 30%;">Subtotal</th>
                    </tr>
                </thead>
                <tbody>${filasHTML}</tbody>
            </table>
            
            <div class="totales right">
                <p>Subtotal: Bs. ${formatearMoneda(subtotal)}</p>
                <p>Descuento: Bs. ${formatearMoneda(descuentoGlobal)}</p>
                <h3 style="margin: 5px 0;">TOTAL: Bs. ${formatearMoneda(total)}</h3>
                <p style="margin-top: 10px;">Método de Pago: ${metodo}</p>
                ${metodo === 'EFECTIVO' ? `
                    <p>Recibido: Bs. ${formatearMoneda(recibido)}</p>
                    <p class="fw-bold">Cambio: Bs. ${formatearMoneda(cambio > 0 ? cambio : 0)}</p>
                ` : ''}
            </div>
            
            <div class="center" style="margin-top: 20px;">
                <p>¡Gracias por su compra!</p>
                <p>***</p>
            </div>
            <script>
                window.onload = function() { 
                    window.print(); 
                    setTimeout(() => window.close(), 500);
                }
            </script>
        </body>
        </html>
    `;
    ventana.document.write(html);
    ventana.document.close();
}

// ==========================================
// IMPRESIÓN DEL REPORTE DE CIERRE (TICKET Z)
// ==========================================
function imprimirReporteCierre(datosCierre) {
    const ventanaImpresion = window.open('', '_blank', 'width=400,height=600');
    
    // Validación de seguridad para navegadores estrictos (ej. Brave)
    if (!ventanaImpresion) {
        alert("⚠️ ATENCIÓN: El navegador bloqueó el ticket. Por favor, permite las ventanas emergentes para este sitio en la barra de direcciones.");
        return false;
    }

    const fechaActual = new Date().toLocaleString('es-BO', { timeZone: 'America/La_Paz' });

    const htmlTicket = `
        <!DOCTYPE html>
        <html>
        <head>
            <title>Reporte Z</title>
            <style>
                body { 
                    font-family: 'Courier New', Courier, monospace; 
                    font-size: 12px; 
                    margin: 0; 
                    padding: 10px; 
                    width: 280px; 
                    color: #000;
                }
                .text-center { text-align: center; }
                .bold { font-weight: bold; }
                .divider { border-top: 1px dashed #000; margin: 10px 0; }
                .flex-space { display: flex; justify-content: space-between; margin-bottom: 3px; }
                .signature-line { 
                    border-top: 1px solid #000; 
                    text-align: center; 
                    width: 80%; 
                    margin: 40px auto 10px auto; 
                    padding-top: 5px; 
                }
                .estado-badge {
                    display: inline-block;
                    padding: 3px 10px;
                    border: 1px solid #000;
                    margin-top: 5px;
                }
            </style>
        </head>
        <body>
            <div class="text-center bold" style="font-size: 14px;">REPORTE DE ARQUEO DE CAJA</div>
            <div class="text-center">Sistema POS</div>
            <div class="divider"></div>
            
            <div><span class="bold">Fecha/Hora:</span> ${fechaActual}</div>
            <div><span class="bold">Sucursal:</span> ${CONTEXTO_ACTUAL.sucursal_id}</div>
            <div><span class="bold">Caja ID:</span> ${CONTEXTO_ACTUAL.caja_id}</div>
            
            <div class="divider"></div>
            <div class="text-center bold">RESUMEN DE EFECTIVO</div>
            <div class="divider"></div>
            
            <div class="flex-space">
                <span>Total Calculado Sist.:</span> 
                <span>Bs. ${formatearMoneda(datosCierre.monto_calculado_sistema)}</span>
            </div>
            <div class="flex-space bold">
                <span>Total Físico Declarado:</span> 
                <span>Bs. ${formatearMoneda(datosCierre.monto_declarado_cajero)}</span>
            </div>
            
            <div class="divider"></div>
            
            <div class="flex-space bold">
                <span>Diferencia:</span> 
                <span>Bs. ${formatearMoneda(datosCierre.diferencia)}</span>
            </div>
            <div class="text-center">
                <div class="estado-badge bold">ESTADO: ${datosCierre.cuadre}</div>
            </div>

            <div class="divider"></div>
            <div class="text-center bold">DESGLOSE DE TRANSACCIONES</div>
            <div class="divider"></div>
            
            <div class="flex-space">
                <span>Fondo Inicial:</span> 
                <span>Bs. ${formatearMoneda(datosCierre.monto_inicial || 0)}</span>
            </div>
            <div class="flex-space">
                <span>Efectivo (${datosCierre.resumen_pagos?.EFECTIVO?.cantidad || 0} Tx):</span> 
                <span>Bs. ${formatearMoneda(datosCierre.resumen_pagos?.EFECTIVO?.total || 0)}</span>
            </div>
            <div class="flex-space">
                <span>Tarjetas (${datosCierre.resumen_pagos?.TARJETA?.cantidad || 0} Tx):</span> 
                <span>Bs. ${formatearMoneda(datosCierre.resumen_pagos?.TARJETA?.total || 0)}</span>
            </div>
            <div class="flex-space">
                <span>Pagos QR (${datosCierre.resumen_pagos?.QR?.cantidad || 0} Tx):</span> 
                <span>Bs. ${formatearMoneda(datosCierre.resumen_pagos?.QR?.total || 0)}</span>
            </div>
            
            <br><br>
            
            <div class="signature-line">Firma Cajero</div>
            <br>
            <div class="signature-line">Firma Supervisor</div>
            
            <div class="text-center" style="margin-top: 15px; font-size: 10px;">
                *** Fin del Reporte ***
            </div>
        </body>
        </html>
    `;

    ventanaImpresion.document.write(htmlTicket);
    ventanaImpresion.document.close();
    ventanaImpresion.focus();

    setTimeout(() => {
        ventanaImpresion.print();
        ventanaImpresion.close();
    }, 500);

    return true;
}

// ==========================================
// ATAJOS DE TECLADO GLOBALES
// ==========================================
document.addEventListener('keydown', (e) => {
    // Evitamos que las teclas 'F' recarguen la página o hagan acciones nativas del navegador (excepto F5)
    if (['F2', 'F4', 'F8', 'F12'].includes(e.key)) {
        e.preventDefault();
    }

    switch (e.key) {
        case 'F2':
            inputBuscador.focus();
            inputBuscador.select(); // Selecciona el texto si ya había algo escrito
            break;
        case 'F4':
            selectMetodoPago.focus();
            break;
        case 'F8':
            if (selectMetodoPago.value === 'EFECTIVO' && !cajaEfectivo.classList.contains('d-none')) {
                inputRecibido.focus();
                inputRecibido.select();
            } else if (!cajaReferencia.classList.contains('d-none')) {
                inputReferencia.focus();
                inputReferencia.select();
            }
            break;
        case 'F12':
            if (!btnCobrar.disabled) {
                btnCobrar.click();
            } else {
                reproducirBeep(false);
                alert("No se puede procesar el cobro. Revisa el carrito o el monto ingresado.");
            }
            break;
    }
});

// --- ACCIÓN: MOSTRAR MODAL DE CIERRE ---
document.getElementById('btn-mostrar-cierre').addEventListener('click', () => {
    // modalCierre ya está definido al inicio de tu pos.js
    modalCierre.show(); 
});