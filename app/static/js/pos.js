// ==========================================
// ESTADO GLOBAL DEL CARRITO
// ==========================================
let carrito = [];

// ==========================================
// ELEMENTOS DEL DOM
// ==========================================
const inputBuscador = document.getElementById('pos-buscador');
const tbodyCarrito = document.getElementById('carrito-body');
const btnCobrar = document.getElementById('btn-cobrar');
const selectFlujo = document.getElementById('pos-flujo');
const inputDescuento = document.getElementById('pos-descuento');

// Utilidad para formatear moneda con separador de miles
const formatearMoneda = (valor) => {
    return new Intl.NumberFormat('es-BO', { 
        minimumFractionDigits: 2, 
        maximumFractionDigits: 2 
    }).format(valor);
};

// ==========================================
// EFECTOS DE SONIDO (NATIVO DEL NAVEGADOR)
// ==========================================
function reproducirBeep(exito = true) {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return; // Por si el navegador es muy antiguo
    
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    
    osc.connect(gain);
    gain.connect(ctx.destination);
    
    if (exito) {
        osc.type = 'sine';
        osc.frequency.value = 800; // Tono agudo y limpio
        gain.gain.setValueAtTime(0.1, ctx.currentTime);
        osc.start();
        osc.stop(ctx.currentTime + 0.1); // Sonido cortito (100ms)
    } else {
        osc.type = 'sawtooth';
        osc.frequency.value = 150; // Tono grave de error (bzzz)
        gain.gain.setValueAtTime(0.1, ctx.currentTime);
        osc.start();
        osc.stop(ctx.currentTime + 0.3); // Sonido un poco más largo
    }
}

// ==========================================
// LÓGICA DEL BUSCADOR (CONEXIÓN REAL)
// ==========================================
inputBuscador.addEventListener('keypress', async (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        const termino = inputBuscador.value.trim();
        if (!termino) return;

        try {
            // Extraemos el token guardado en el navegador
            const token = localStorage.getItem("erp_token"); 

            // Adjuntamos el token en los headers de la petición
            const resp = await fetch(`/articulos/buscar/${termino}`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (resp.ok) {
                const data = await resp.json();
                
                // Tomamos el primer resultado de la búsqueda
                const articuloEncontrado = data[0]; 
                
                // Lo mandamos a tu función con los datos de la base de datos
                agregarAlCarrito({
                    sku_articulo: articuloEncontrado.sku,
                    nombre_articulo: articuloEncontrado.nombre, 
                    precio_unitario: articuloEncontrado.precio_venta || 0 
                });

                inputBuscador.value = ''; // Limpiamos para el siguiente escaneo
            } else {
                reproducirBeep(false); // Reproduce sonido de error
                alert("Artículo no encontrado en la base de datos.");
                inputBuscador.select(); // Resalta el texto para borrarlo rápido
            }
        } catch (error) {
            console.error("Error buscando artículo:", error);
            reproducirBeep(false); // Reproduce sonido de error
            alert("Error de conexión al buscar el artículo.");
        }
    }
});

// ==========================================
// GESTIÓN DEL CARRITO Y MATEMÁTICAS
// ==========================================
function agregarAlCarrito(producto) {
    const itemExistente = carrito.find(item => item.sku_articulo === producto.sku_articulo);
    
    if (itemExistente) {
        itemExistente.cantidad += 1;
        itemExistente.subtotal_linea = itemExistente.cantidad * itemExistente.precio_unitario;
    } else {
        carrito.push({
            sku_articulo: producto.sku_articulo,
            nombre_articulo: producto.nombre_articulo,
            cantidad: 1,
            precio_unitario: producto.precio_unitario,
            descuento_linea: 0.0,
            subtotal_linea: producto.precio_unitario
        });
    }
    
    reproducirBeep(true); // ¡Hacemos sonar el Beep de éxito!
    actualizarVista(producto.sku_articulo); // Le decimos a la vista qué producto acaba de entrar
}

function actualizarCantidad(sku, nuevaCantidad) {
    const item = carrito.find(i => i.sku_articulo === sku);
    if (item && nuevaCantidad > 0) {
        item.cantidad = parseInt(nuevaCantidad);
        item.subtotal_linea = item.cantidad * item.precio_unitario;
        actualizarVista();
    }
}

function eliminarDelCarrito(sku) {
    carrito = carrito.filter(item => item.sku_articulo !== sku);
    actualizarVista();
}

// Nueva función para el descuento por línea
function actualizarDescuentoLinea(sku, nuevoDescuento) {
    const item = carrito.find(i => i.sku_articulo === sku);
    if (item) {
        let desc = parseFloat(nuevoDescuento) || 0;
        // Evitar que el descuento sea mayor al total de esa línea
        const maxDescuento = item.cantidad * item.precio_unitario;
        if (desc > maxDescuento) desc = maxDescuento;
        
        item.descuento_linea = desc;
        item.subtotal_linea = (item.cantidad * item.precio_unitario) - item.descuento_linea;
        actualizarVista();
    }
}

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
        btnCobrar.disabled = true;
    } else {
        carrito.forEach(item => {
            subtotalGeneral += item.subtotal_linea;
            
            const tr = document.createElement('tr');
            // Si es el producto que acabamos de escanear, le ponemos la clase del destello
            if (item.sku_articulo === skuDestacado) {
                tr.classList.add('fila-destello');
            }
            
            tr.innerHTML = `
                <td class="fw-bold align-middle">${item.sku_articulo}</td>
                <td class="align-middle">${item.nombre_articulo}</td>
                <td>
                    <input type="number" class="form-control form-control-sm text-center fw-bold" 
                           value="${item.cantidad}" min="1"
                           onchange="actualizarCantidad('${item.sku_articulo}', this.value)">
                </td>
                <td>
                    <input type="number" class="form-control form-control-sm text-end fw-bold" 
                        value="${item.precio_unitario}" min="0" step="0.10"
                        onchange="actualizarPrecioUnitario('${item.sku_articulo}', this.value)">
                </td>
                <td>
                    <input type="number" class="form-control form-control-sm text-center text-danger" 
                           value="${item.descuento_linea || 0}" min="0" step="0.5"
                           onchange="actualizarDescuentoLinea('${item.sku_articulo}', this.value)">
                </td>
                <td class="text-end fw-bold align-middle fs-5">${formatearMoneda(item.subtotal_linea)}</td>
                <td class="text-center align-middle">
                    <button class="btn btn-sm btn-outline-danger" onclick="eliminarDelCarrito('${item.sku_articulo}')" title="Eliminar línea">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            `;
            tbodyCarrito.appendChild(tr);
        });
        btnCobrar.disabled = false;
    }

    const descuentoGlobal = parseFloat(inputDescuento.value) || 0;
    const totalFinal = subtotalGeneral - descuentoGlobal;

    document.getElementById('pos-subtotal').textContent = formatearMoneda(subtotalGeneral);
    document.getElementById('pos-total').textContent = formatearMoneda(totalFinal);
}

// Función para permitir la edición manual del precio unitario en caja
function actualizarPrecioUnitario(sku, nuevoPrecio) {
    const item = carrito.find(i => i.sku_articulo === sku);
    if (item) {
        let precio = parseFloat(nuevoPrecio) || 0;
        if (precio < 0) precio = 0; // Evitar precios negativos
        
        item.precio_unitario = precio;
        // Recalculamos el subtotal de la línea considerando también si tenía descuento
        item.subtotal_linea = (item.cantidad * item.precio_unitario) - (item.descuento_linea || 0);
        actualizarVista();
    }
}

// Recalcular si cambia el descuento manual
inputDescuento.addEventListener('input', actualizarVista);

// ==========================================
// PROCESAR LA VENTA CON EL BACKEND
// ==========================================
btnCobrar.addEventListener('click', async () => {
    // 1. Validación estricta del Flujo de Seguimiento
    const flujoSeleccionado = selectFlujo.value;
    if (!flujoSeleccionado) {
        alert("¡Alto! Debes seleccionar un Flujo de Seguimiento manualmente para esta venta.");
        selectFlujo.focus();
        return;
    }

    // 2. Preparar el Payload (Exactamente como lo pide tu esquema Pydantic)
    const payloadVenta = {
        cliente: document.getElementById('pos-cliente').value,
        documento_cliente: document.getElementById('pos-documento').value,
        almacen_origen: document.getElementById('pos-almacen').value,
        flujo_trabajo_seleccionado: flujoSeleccionado,
        articulos: carrito,
        descuento_global: parseFloat(inputDescuento.value) || 0,
        condicion_pago: document.getElementById('pos-condicion').value
    };

    try {
        // Bloquear botón para evitar doble cobro
        btnCobrar.disabled = true;
        btnCobrar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Procesando...';

        const token = localStorage.getItem("erp_token");

        // 3. Crear la Orden de Venta
        const resVenta = await fetch('/ventas/', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}` // <--- TOKEN AÑADIDO AQUÍ
            },
            body: JSON.stringify(payloadVenta)
        });

        if (!resVenta.ok) throw new Error("Error al crear la venta");
        const dataVenta = await resVenta.json();
        const ventaId = dataVenta.venta_id;

        // 4. Disparar el Motor FEFO (Despachar)
        const resDespacho = await fetch(`/ventas/${ventaId}/despachar`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}` // <--- TOKEN AÑADIDO AQUÍ
            }
        });

        if (!resDespacho.ok) throw new Error("Error al despachar el inventario");

        // ¡ÉXITO!
        reproducirBeep(true); // Opcional: Sonido de éxito
        alert(`¡Venta procesada exitosamente!\nFolio: ${dataVenta.folio}`);
        
        // Limpiar el mostrador para el siguiente cliente
        carrito = [];
        actualizarVista();
        document.getElementById('pos-cliente').value = "Cliente Mostrador";
        document.getElementById('pos-documento').value = "S/N";
        selectFlujo.value = "";
        
    } catch (error) {
        reproducirBeep(false); // Opcional: Sonido de error
        alert("Ocurrió un problema: " + error.message);
        console.error(error);
    } finally {
        // Restaurar el botón
        btnCobrar.innerHTML = '<i class="bi bi-cash-coin"></i> PROCESAR COBRO';
        btnCobrar.disabled = false;
    }
});

// ==========================================
// BÚSQUEDA AUTOMÁTICA DE CLIENTE (REAL)
// ==========================================
const inputDocumento = document.getElementById('pos-documento');
const inputCliente = document.getElementById('pos-cliente');

inputDocumento.addEventListener('change', async (e) => {
    const documento = e.target.value.trim();
    
    // Si lo dejan vacío o en S/N, reseteamos a Cliente Mostrador
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