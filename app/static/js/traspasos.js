// ==========================================
// VARIABLES GLOBALES Y ELEMENTOS DEL DOM
// ==========================================
let carritoTraspaso = [];
let CONTEXTO_USUARIO = { almacen_id: "", username: "", rol: "" };
let timeoutBusquedaTraspaso;
let enviosPendientes = []; 

const inputBuscador = document.getElementById('traspaso-buscador');
const dropdownResultados = document.getElementById('dropdown-resultados-traspaso');
const tbodyCarrito = document.getElementById('traspaso-carrito-body');

const selectOrigen = document.getElementById('traspaso-origen'); 
const selectDestino = document.getElementById('traspaso-destino');
const selectFlujo = document.getElementById('traspaso-flujo');
const inputNotas = document.getElementById('traspaso-notas');
const checkDirecto = document.getElementById('traspaso-directo');
const btnEnviar = document.getElementById('btn-enviar-traspaso');

const modalRecepcion = new bootstrap.Modal(document.getElementById('modalRecepcion'));
const inputFolioOculto = document.getElementById('recepcion-folio-oculto');
const selectFlujoRecepcion = document.getElementById('recepcion-flujo');
const btnConfirmarRecepcion = document.getElementById('btn-confirmar-recepcion');

// ==========================================
// INICIALIZACIÓN HÍBRIDA (TOKEN + BD)
// ==========================================
async function inicializarModulo() {
    const token = localStorage.getItem("erp_token");
    if (!token) return window.location.href = "/vistas/login";

    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        CONTEXTO_USUARIO.username = payload.sub || 'USUARIO';
        CONTEXTO_USUARIO.rol = payload.rol || 'OPERADOR';

        const resPerfil = await fetch('/me', { headers: { 'Authorization': `Bearer ${token}` } });
        if (resPerfil.ok) {
            const perfil = await resPerfil.json();
            CONTEXTO_USUARIO.almacen_id = perfil.almacen_id || perfil.codigo_almacen || '';
            CONTEXTO_USUARIO.rol = perfil.rol || CONTEXTO_USUARIO.rol;
        }

        await Promise.all([
            cargarAlmacenes(),
            cargarPendientes()
        ]);
        
    } catch (error) {
        console.error("Error crítico inicializando:", error);
    }
}

// ==========================================
// CARGA DINÁMICA DE ALMACENES
// ==========================================
async function cargarAlmacenes() {
    try {
        const token = localStorage.getItem("erp_token");
        const res = await fetch('/almacenes/', { headers: { 'Authorization': `Bearer ${token}` } });
        
        if (!res.ok) throw new Error("Error HTTP " + res.status);
        const almacenes = await res.json();
        
        let opcionesHTML = '<option value="">Seleccione un almacén...</option>';
        almacenes.forEach(a => {
            const codigo = a.codigo || a.id; 
            const nombre = a.nombre || codigo;
            opcionesHTML += `<option value="${codigo}">${nombre}</option>`;
        });

        if (selectOrigen) selectOrigen.innerHTML = opcionesHTML;
        if (selectDestino) selectDestino.innerHTML = opcionesHTML;

        if (CONTEXTO_USUARIO.rol === 'ADMIN') {
            if (selectOrigen) selectOrigen.disabled = false;
        } else {
            if (selectOrigen) {
                selectOrigen.value = CONTEXTO_USUARIO.almacen_id;
                selectOrigen.disabled = true;
            }
        }

        actualizarOpcionesDestino();
        if (selectOrigen) selectOrigen.addEventListener('change', actualizarOpcionesDestino);

    } catch (error) {
        console.error("Error cargando almacenes:", error);
    }
}

function actualizarOpcionesDestino() {
    if (!selectOrigen || !selectDestino) return;
    const origenSeleccionado = selectOrigen.value;

    Array.from(selectDestino.options).forEach(opt => {
        if (opt.value === origenSeleccionado && origenSeleccionado !== "") {
            opt.disabled = true; 
            if (selectDestino.value === origenSeleccionado) selectDestino.value = '';
        } else {
            opt.disabled = false;
        }
    });
}

// ==========================================
// BUSCADOR Y CARRITO (PESTAÑA 1)
// ==========================================
if (inputBuscador) {
    inputBuscador.addEventListener('input', (e) => {
        clearTimeout(timeoutBusquedaTraspaso);
        const query = e.target.value.trim();

        if (query.length < 2) {
            dropdownResultados.classList.remove('show');
            return;
        }

        timeoutBusquedaTraspaso = setTimeout(async () => {
            try {
                const origenActual = selectOrigen ? selectOrigen.value : CONTEXTO_USUARIO.almacen_id;
                
                if (!origenActual || origenActual === "") {
                    dropdownResultados.innerHTML = '<li><span class="dropdown-item text-danger fw-bold"><i class="bi bi-exclamation-triangle"></i> Selecciona un Almacén Origen primero</span></li>';
                    dropdownResultados.classList.add('show');
                    return;
                }

                const token = localStorage.getItem("erp_token");
                const res = await fetch(`/articulos/buscar?q=${encodeURIComponent(query)}&almacen_id=${origenActual}`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                
                if (!res.ok) return;
                const resultados = await res.json();
                dropdownResultados.innerHTML = '';
                
                if (resultados.length === 0) {
                    dropdownResultados.innerHTML = '<li><span class="dropdown-item text-muted">No encontrado en el almacén origen</span></li>';
                } else {
                    resultados.forEach(art => {
                        const li = document.createElement('li');
                        li.innerHTML = `<a class="dropdown-item py-2" href="#" style="cursor: pointer;">
                            <div class="d-flex justify-content-between align-items-center">
                                <div><strong>${art.sku}</strong> - ${art.nombre}</div>
                                <span class="badge bg-primary rounded-pill">Stock: ${art.stock_en_almacen || 0}</span>
                            </div>
                        </a>`;
                        
                        li.addEventListener('click', (evento) => {
                            evento.preventDefault();
                            agregarAlCarritoTraspaso(art);
                            inputBuscador.value = '';
                            dropdownResultados.classList.remove('show');
                        });
                        dropdownResultados.appendChild(li);
                    });
                }
                dropdownResultados.classList.add('show');
            } catch (error) { console.error("Error buscando:", error); }
        }, 300);
    });
}

function agregarAlCarritoTraspaso(articulo) {
    const stockDisp = articulo.stock_en_almacen || 0;
    if (stockDisp <= 0) return alert(`No hay stock de ${articulo.nombre} en el almacén de origen.`);

    const existente = carritoTraspaso.find(i => i.sku_articulo === articulo.sku);
    if (existente) {
        if (existente.cantidad + 1 > stockDisp) return alert("Stock máximo alcanzado.");
        existente.cantidad += 1;
    } else {
        carritoTraspaso.push({ sku_articulo: articulo.sku, nombre_articulo: articulo.nombre, cantidad: 1, stock_max: stockDisp });
    }
    actualizarVistaCarrito();
}

function actualizarVistaCarrito() {
    if (!tbodyCarrito) return;
    tbodyCarrito.innerHTML = '';
    if (carritoTraspaso.length === 0) {
        tbodyCarrito.innerHTML = `<tr><td colspan="4" class="text-center py-4 text-muted">No hay artículos agregados al camión</td></tr>`;
        return;
    }

    carritoTraspaso.forEach(item => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="fw-bold">${item.sku_articulo}</td>
            <td>${item.nombre_articulo}</td>
            <td>
                <input type="number" class="form-control form-control-sm text-center" 
                value="${item.cantidad}" min="1" max="${item.stock_max}" 
                onchange="cambiarCantidad('${item.sku_articulo}', this.value)">
            </td>
            <td class="text-center">
                <button class="btn btn-sm btn-outline-danger" onclick="quitarDelCarrito('${item.sku_articulo}')"><i class="bi bi-trash"></i></button>
            </td>
        `;
        tbodyCarrito.appendChild(tr);
    });
}

window.cambiarCantidad = (sku, nuevaCant) => {
    const item = carritoTraspaso.find(i => i.sku_articulo === sku);
    if (item) {
        let cant = parseInt(nuevaCant) || 1;
        if (cant > item.stock_max) cant = item.stock_max;
        item.cantidad = cant;
        actualizarVistaCarrito();
    }
};

window.quitarDelCarrito = (sku) => {
    carritoTraspaso = carritoTraspaso.filter(i => i.sku_articulo !== sku);
    actualizarVistaCarrito();
};

// ==========================================
// PROCESAR ENVÍO
// ==========================================
if (btnEnviar) {
    btnEnviar.addEventListener('click', async () => {
        const origenSeleccionado = selectOrigen ? selectOrigen.value : CONTEXTO_USUARIO.almacen_id;

        if (carritoTraspaso.length === 0) return alert("El carrito está vacío.");
        if (!origenSeleccionado) return alert("Selecciona el almacén origen.");
        if (!selectDestino.value) return alert("Selecciona el almacén destino.");
        if (!selectFlujo.value) return alert("Selecciona un flujo de trabajo.");
        if (selectDestino.value === origenSeleccionado) return alert("El destino no puede ser igual al origen.");

        const payload = {
            almacen_origen_id: origenSeleccionado,
            almacen_destino_id: selectDestino.value,
            flujo_trabajo_seleccionado: selectFlujo.value,
            recepcion_automatica: checkDirecto.checked,
            notas: inputNotas.value,
            articulos: carritoTraspaso.map(i => ({ sku_articulo: i.sku_articulo, nombre_articulo: i.nombre_articulo, cantidad: i.cantidad }))
        };

        try {
            btnEnviar.disabled = true;
            btnEnviar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Procesando...';
            
            const token = localStorage.getItem("erp_token");
            const res = await fetch('/traspasos/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify(payload)
            });

            if (!res.ok) throw new Error(await res.text());
            
            const data = await res.json();
            alert(`¡Éxito! Boleta generada: ${data.folio}\nEstado: ${data.estado}`);
            
            carritoTraspaso = [];
            actualizarVistaCarrito();
            if (inputNotas) inputNotas.value = "";
            if (checkDirecto) checkDirecto.checked = false;
            if (selectDestino) selectDestino.value = "";
            if (selectFlujo) selectFlujo.value = "";
            
        } catch (error) {
            alert("Error al enviar: " + error.message);
        } finally {
            btnEnviar.disabled = false;
            btnEnviar.innerHTML = '<i class="bi bi-send-check"></i> PROCESAR ENVÍO';
        }
    });
}

// ==========================================
// RECEPCIONES PENDIENTES (PESTAÑA 2)
// ==========================================
async function cargarPendientes() {
    const tbodyPendientes = document.getElementById('tabla-pendientes-body');
    if (!tbodyPendientes) return; 

    const destinoBusqueda = CONTEXTO_USUARIO.almacen_id || ""; 
    
    if (!destinoBusqueda) {
        tbodyPendientes.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-warning fw-bold"><i class="bi bi-exclamation-triangle"></i> Tu usuario no tiene un almacén predeterminado.</td></tr>`;
        return; 
    }

    try {
        const token = localStorage.getItem("erp_token");
        const res = await fetch(`/traspasos/pendientes/${destinoBusqueda}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!res.ok) {
            const errorDato = await res.text();
            tbodyPendientes.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-danger fw-bold">Error del Servidor: ${res.status} <br> <span class="small text-muted">${errorDato}</span></td></tr>`;
            return;
        }

        enviosPendientes = await res.json(); 
        tbodyPendientes.innerHTML = '';
        
        if (enviosPendientes.length === 0) {
            tbodyPendientes.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-muted">No hay camiones en camino hacia este almacén.</td></tr>`;
            return;
        }

        enviosPendientes.forEach(p => {
            const totalArticulos = p.articulos.reduce((sum, art) => sum + art.cantidad, 0);
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="fw-bold text-primary">${p.folio}</td>
                <td><span class="badge bg-secondary">${p.almacen_origen_id}</span></td>
                <td>${new Date(p.fecha_envio).toLocaleString('es-BO')}</td>
                <td class="text-muted small">${p.articulos.length} Items (${totalArticulos} unid.)</td>
                <td class="text-end">
                    <!-- BOTÓN ÚNICO QUE ABRE EL MODAL INTERACTIVO -->
                    <button class="btn btn-success btn-sm fw-bold shadow-sm" onclick="abrirModalRecepcion('${p.folio}')">
                        <i class="bi bi-box-arrow-in-down"></i> VER Y RECIBIR
                    </button>
                </td>
            `;
            tbodyPendientes.appendChild(tr);
        });
    } catch (error) { 
        console.error("Error cargando pendientes:", error);
        tbodyPendientes.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-danger fw-bold">Error de red al conectar con el servidor.</td></tr>`;
    }
}

const tabPendientes = document.getElementById('pendientes-tab');
if (tabPendientes) {
    tabPendientes.addEventListener('shown.bs.tab', cargarPendientes);
}

// ==========================================
// PROCESAR RECEPCIÓN INTERACTIVA Y DISCREPANCIAS
// ==========================================
window.abrirModalRecepcion = (folio) => {
    const traspaso = enviosPendientes.find(t => t.folio === folio);
    if (!traspaso) return;

    if (inputFolioOculto) inputFolioOculto.value = folio;
    if (selectFlujoRecepcion) selectFlujoRecepcion.value = "";
    
    document.getElementById('recepcion-folio-titulo').textContent = folio;

    const tbodyDetalle = document.getElementById('detalle-recepcion-interactiva');
    if (tbodyDetalle) {
        tbodyDetalle.innerHTML = '';
        traspaso.articulos.forEach((art, index) => {
            const rowId = `rec-row-${index}`;
            tbodyDetalle.innerHTML += `
                <tr id="${rowId}">
                    <td class="text-center">
                        <input class="form-check-input check-llegada" type="checkbox" data-index="${index}" checked style="transform: scale(1.5);">
                    </td>
                    <td class="fw-bold text-muted small sku-cell">${art.sku_articulo}</td>
                    <td class="small nombre-cell">${art.nombre_articulo}</td>
                    <td class="text-center fw-bold text-secondary esperada-cell">${art.cantidad}</td>
                    <td>
                        <input type="number" class="form-control form-control-sm text-center fw-bold text-primary input-recibida" value="${art.cantidad}" min="0">
                    </td>
                    <td>
                        <input type="text" class="form-control form-control-sm input-obs" placeholder="Ej. 1 caja rota" autocomplete="off">
                    </td>
                </tr>
            `;
        });

        // Evento para deshabilitar inputs si se desmarca "Llegó"
        document.querySelectorAll('.check-llegada').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const tr = e.target.closest('tr');
                const inputRecibida = tr.querySelector('.input-recibida');
                
                if (!e.target.checked) {
                    inputRecibida.value = 0;
                    inputRecibida.disabled = true;
                    tr.classList.add('table-danger');
                } else {
                    const esperada = tr.querySelector('.esperada-cell').textContent;
                    inputRecibida.value = esperada;
                    inputRecibida.disabled = false;
                    tr.classList.remove('table-danger');
                }
            });
        });
    }

    if (modalRecepcion) modalRecepcion.show();
};

if (btnConfirmarRecepcion) {
    btnConfirmarRecepcion.addEventListener('click', async () => {
        const folio = inputFolioOculto.value;
        const flujo = selectFlujoRecepcion.value;
        
        if (!flujo) return alert("Por favor selecciona un Flujo de Ingreso para continuar.");

        // Recolectar datos interactivos de la tabla
        const articulosRecibidos = [];
        let discrepanciaDetectada = false;
        
        const filas = document.querySelectorAll('#detalle-recepcion-interactiva tr');
        filas.forEach(tr => {
            const sku = tr.querySelector('.sku-cell').textContent;
            const esperada = parseFloat(tr.querySelector('.esperada-cell').textContent);
            const recibida = parseFloat(tr.querySelector('.input-recibida').value) || 0;
            const observaciones = tr.querySelector('.input-obs').value.trim();

            if (esperada !== recibida) discrepanciaDetectada = true;

            articulosRecibidos.push({
                sku_articulo: sku,
                cantidad_esperada: esperada,
                cantidad_recibida: recibida,
                observaciones: observaciones
            });
        });

        // Advertencia si hay discrepancias
        if (discrepanciaDetectada) {
            const confirmacion = confirm("ATENCIÓN: Has reportado diferencias entre lo enviado y lo recibido. Esto generará un ajuste de inventario. ¿Estás seguro de continuar?");
            if (!confirmacion) return;
        }

        const payload = {
            flujo_trabajo_seleccionado: flujo,
            articulos_recibidos: articulosRecibidos
        };

        try {
            btnConfirmarRecepcion.disabled = true;
            btnConfirmarRecepcion.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Ingresando...';
            
            const token = localStorage.getItem("erp_token");
            const res = await fetch(`/traspasos/${folio}/recibir`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify(payload)
            });

            if (!res.ok) throw new Error(await res.text());
            
            alert("¡Mercadería ingresada al Kardex exitosamente!");
            modalRecepcion.hide();
            cargarPendientes(); 
            
        } catch (error) {
            alert("Error en recepción: " + error.message);
        } finally {
            btnConfirmarRecepcion.disabled = false;
            btnConfirmarRecepcion.innerHTML = '<i class="bi bi-check2-circle"></i> INGRESAR AL KARDEX';
        }
    });
}

// ==========================================
// DISPARADOR DE ARRANQUE SEGURO
// ==========================================
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarModulo);
} else {
    inicializarModulo();
}