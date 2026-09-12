// Función global para obtener el token
function obtenerToken() {
    const token = localStorage.getItem('erp_token');
    if (!token) {
        alert("Tu sesión ha expirado. Por favor, inicia sesión nuevamente.");
        window.location.href = '/vistas/login';
        return null;
    }
    return token;
}

// ==========================================
// BÚSQUEDA INTELIGENTE Y CÓDIGO DE BARRAS
// ==========================================
const inputBusqueda = document.getElementById('input-busqueda');
const inputSkuOculto = document.getElementById('input-sku');
const dropdownResultados = document.getElementById('dropdown-resultados');
let timeoutBusqueda;

if (inputBusqueda) {
    // 1. Escuchar mientras el usuario escribe
    inputBusqueda.addEventListener('input', (e) => {
        clearTimeout(timeoutBusqueda);
        const query = e.target.value.trim();

        // Si borra el texto, ocultamos la lista y limpiamos el SKU oculto
        if (query.length < 2) {
            dropdownResultados.classList.remove('show');
            inputSkuOculto.value = '';
            return;
        }

        // Esperamos 300ms después de que deje de teclear (Debounce para no saturar el servidor)
        timeoutBusqueda = setTimeout(async () => {
            try {
                const token = obtenerToken();
                if (!token) return;
                
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
                        li.innerHTML = `<a class="dropdown-item" href="#" style="cursor: pointer; white-space: normal;">
                            <strong>${art.sku}</strong> - ${art.nombre} 
                            ${art.codigo_barras ? `<br><small class="text-muted"><i class="bi bi-upc"></i> ${art.codigo_barras}</small>` : ''}
                        </a>`;
                        
                        // Al hacer clic en una opción de la lista
                        li.addEventListener('click', (evento) => {
                            evento.preventDefault();
                            seleccionarArticulo(art.sku, `${art.sku} - ${art.nombre}`);
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

    // 2. Manejar el "Enter" del escáner de código de barras
    inputBusqueda.addEventListener('keypress', async (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            dropdownResultados.classList.remove('show');
            
            // Si ya hay un SKU seleccionado (por clic previo)
            if (inputSkuOculto.value) {
                document.getElementById('btn-consultar-kardex').click();
            } else {
                // Failsafe para escáner láser: Si escaneó súper rápido, buscamos directo el primer resultado exacto
                const query = inputBusqueda.value.trim();
                if(query) {
                    try {
                        const token = obtenerToken();
                        const response = await fetch(`/articulos/buscar?q=${encodeURIComponent(query)}`, {
                            headers: { 'Authorization': `Bearer ${token}` }
                        });
                        if (response.ok) {
                            const resultados = await response.json();
                            if (resultados.length > 0) {
                                seleccionarArticulo(resultados[0].sku, `${resultados[0].sku} - ${resultados[0].nombre}`);
                                document.getElementById('btn-consultar-kardex').click();
                            } else {
                                alert("Artículo no encontrado en la base de datos.");
                            }
                        }
                    } catch (error) {
                        console.error(error);
                    }
                }
            }
        }
    });

    // 3. Cerrar la lista si el usuario hace clic en otra parte de la pantalla
    document.addEventListener('click', (e) => {
        if (!inputBusqueda.contains(e.target) && !dropdownResultados.contains(e.target)) {
            dropdownResultados.classList.remove('show');
        }
    });
}

// Función auxiliar para setear el artículo elegido
function seleccionarArticulo(sku, textoMostrar) {
    if(inputSkuOculto) inputSkuOculto.value = sku;           
    if(inputBusqueda) inputBusqueda.value = textoMostrar;   
    if(dropdownResultados) dropdownResultados.classList.remove('show');
    const btnConsultar = document.getElementById('btn-consultar-kardex');
    if(btnConsultar) btnConsultar.focus(); 
}

// ==========================================
// --- Lógica para pintar la tabla en pantalla ---
// ==========================================
document.getElementById('btn-consultar-kardex').addEventListener('click', async (e) => {
    const token = obtenerToken();
    if (!token) return;

    // 1. CAPTURAMOS EL BOTÓN AL INICIO (Para no perder su estado original)
    const btnConsultar = document.getElementById('btn-consultar-kardex');
    const textoOriginalBtn = btnConsultar.innerHTML;

    let sku = document.getElementById('input-sku').value.trim();
    const inputBusquedaTexto = document.getElementById('input-busqueda').value.trim();
        
    // 2. AUTO-RESOLVER SI USAN ESCÁNER O TEXTO MANUAL SIN ELEGIR DE LA LISTA
    if (!sku) {
        if (inputBusquedaTexto) {
            btnConsultar.disabled = true;
            btnConsultar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Verificando...';

            try {
                const response = await fetch(`/articulos/buscar?q=${encodeURIComponent(inputBusquedaTexto)}`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                
                if (response.ok) {
                    const resultados = await response.json();
                    if (resultados && resultados.length > 0) {
                        // ¡Encontrado!
                        sku = resultados[0].sku;
                        seleccionarArticulo(sku, `${sku} - ${resultados[0].nombre}`);
                    } else {
                        // No existe
                        alert(`❌ No se encontró ningún artículo: ${inputBusquedaTexto}`);
                        btnConsultar.disabled = false;
                        btnConsultar.innerHTML = textoOriginalBtn;
                        return; // DETENER AQUÍ
                    }
                } else {
                    // El endpoint devolvió un error (Ej. 404 o 500)
                    console.error("Fallo en el endpoint de búsqueda");
                    alert("Error al conectar con la búsqueda de artículos.");
                    btnConsultar.disabled = false;
                    btnConsultar.innerHTML = textoOriginalBtn;
                    return; // DETENER AQUÍ
                }
            } catch (error) {
                console.error("Error buscando código:", error);
                btnConsultar.disabled = false;
                btnConsultar.innerHTML = textoOriginalBtn;
                return; // DETENER AQUÍ
            }
        } else {
            alert("Por favor, busca un artículo o escanea su código de barras primero.");
            return;
        }
    }

    // 3. CONTINUAR CON KARDEX (Si llegamos aquí, sí tenemos un SKU válido)
    const inputInicio = document.getElementById('fecha-inicio').value;
    const inputFin = document.getElementById('fecha-fin').value;

    if (inputInicio && inputFin && inputInicio > inputFin) {
        alert("Error: La Fecha de Inicio no puede ser posterior a la Fecha Fin.");
        return;
    }

    const inputAlmacen = document.getElementById('filtro_almacen').value;
    
    // Cambiamos el texto para la segunda fase
    btnConsultar.disabled = true;
    btnConsultar.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Buscando Kardex...';

    let url = `/movimientos/${sku}`;
    const params = new URLSearchParams();
    if (inputAlmacen) params.append('codigo_almacen', inputAlmacen);
    if (inputInicio) params.append('fecha_inicio', `${inputInicio}T00:00:00`);
    if (inputFin) params.append('fecha_fin', `${inputFin}T23:59:59`);
    
    if (params.toString()) url += `?${params.toString()}`;

    const tbody = document.getElementById('cuerpo-tabla-kardex');
    tbody.innerHTML = '<tr><td colspan="9" class="text-center">⏳ Cargando datos...</td></tr>';

    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.status === 401) {
            window.location.href = '/vistas/login';
            return;
        }

        if (!response.ok) throw new Error("Error al obtener los datos");
        
        const data = await response.json();
        const unidad = data.unidad_medida || ""; 
        
        let htmlFilas = `
            <tr style="background-color: #f8f9fa; font-weight: bold;">
                <td>-</td>
                <td>SALDO INICIAL</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>${data.saldo_inicial.toLocaleString('en-US')} ${unidad}</td> 
                <td>${data.saldo_inicial === 0 ? "$0.00" : "-"}</td>
            </tr>
        `;

        let saldoActual = data.saldo_inicial;

        if (data.movimientos.length === 0) {
            htmlFilas += `<tr><td colspan="9" class="text-center">No hay movimientos en este rango de fechas.</td></tr>`;
        } else {
            data.movimientos.forEach(mov => {
                let ingreso = 0;
                let egreso = 0;
                const tiposIngreso = ["IN", "IN_PROD", "IN_TRANS"];
                const tipo = mov.tipo_movimiento.toUpperCase();
                
                if (tiposIngreso.includes(tipo)) {
                    ingreso = mov.cantidad;
                    saldoActual += mov.cantidad;
                } else {
                    egreso = mov.cantidad;
                    saldoActual -= mov.cantidad;
                }

                const colorFondo = ingreso > 0 ? '#e8f5e9' : '#ffebee';
                const colorTexto = ingreso > 0 ? 'green' : 'red';
                const ingresoStr = ingreso > 0 ? `+${ingreso.toLocaleString('en-US')} ${unidad}` : '-';
                const egresoStr = egreso > 0 ? `-${egreso.toLocaleString('en-US')} ${unidad}` : '-';

                htmlFilas += `
                    <tr style="background-color: ${colorFondo};">
                        <td style="padding: 8px;">${new Date(mov.fecha_registro).toLocaleString()}</td>
                        <td>${mov.concepto}</td>
                        <td>${mov.numero_lote || '-'}</td>
                        <td>${mov.tipo_movimiento}</td>
                        <td>$${mov.costo_unitario.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                        <td style="color: ${colorTexto}; font-weight: bold;">${ingresoStr}</td>
                        <td style="color: ${colorTexto}; font-weight: bold;">${egresoStr}</td>
                        <td style="font-weight: bold;">${saldoActual.toLocaleString('en-US')} ${unidad}</td> 
                        <td style="font-weight: bold; color: #0056b3;">$${(saldoActual * mov.costo_unitario).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                    </tr>
                `;
            });
        }
        tbody.innerHTML = htmlFilas;

    } catch (error) {
        console.error("Error:", error);
        tbody.innerHTML = '<tr><td colspan="9" style="color: red; text-align: center;">Ocurrió un error al cargar el Kardex.</td></tr>';
    } finally {
        // Restauramos con el texto capturado al inicio
        btnConsultar.disabled = false;
        btnConsultar.innerHTML = textoOriginalBtn;
    }
});

// ==========================================
// --- Lógica para exportar el Kardex a CSV ---
// ==========================================
document.getElementById('btn-descargar-kardex').addEventListener('click', async () => {
    const token = obtenerToken();
    if (!token) return;

    const sku = document.getElementById('input-sku').value.trim();
        
    if (!sku) {
        alert("Por favor, busca y selecciona un artículo que deseas exportar.");
        return;
    }

    const inputInicio = document.getElementById('fecha-inicio').value;
    const inputFin = document.getElementById('fecha-fin').value;
    
    // Validación de fechas para la exportación
    if (inputInicio && inputFin) {
        if (inputInicio > inputFin) {
            alert("Error: La Fecha de Inicio no puede ser posterior a la Fecha Fin.");
            return;
        }
    }

    const inputAlmacen = document.getElementById('filtro_almacen').value;
    
    let url = `/movimientos/${sku}/exportar`;
    
    const params = new URLSearchParams();
    if (inputAlmacen) params.append('codigo_almacen', inputAlmacen);
    if (inputInicio) params.append('fecha_inicio', `${inputInicio}T00:00:00`);
    if (inputFin) params.append('fecha_fin', `${inputFin}T23:59:59`);
    
    if (params.toString()) {
        url += `?${params.toString()}`;
    }

    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) throw new Error("Error en la descarga");

        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `Kardex_${sku}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(downloadUrl);

    } catch (error) {
        console.error("Error al exportar:", error);
        alert("Hubo un problema al intentar descargar el reporte.");
    }
});

// ==========================================
// UX DEL MODAL: Autocompletado y Cálculos (CORREGIDO)
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    // 1. Lógica del Modal (Copiar SKU y Almacén)
    const modalIngresoEl = document.getElementById('modalNuevoIngreso');
    if (modalIngresoEl) {
        modalIngresoEl.addEventListener('show.bs.modal', () => {
            const skuActual = document.getElementById('input-sku').value.trim();
            const almacenActual = document.getElementById('filtro_almacen').value.trim();
            
            const inputModalSku = document.getElementById('ingreso-sku');
            const inputModalAlmacen = document.getElementById('ingreso-almacen');
            
            if (skuActual && inputModalSku) {
                inputModalSku.value = skuActual;
                inputModalSku.setAttribute('readonly', 'true');
                inputModalSku.style.backgroundColor = '#e9ecef'; 
            }
            
            if (almacenActual && inputModalAlmacen) {
                inputModalAlmacen.value = almacenActual;
            }
        });

        modalIngresoEl.addEventListener('hidden.bs.modal', () => {
            const form = document.getElementById('form-nuevo-ingreso');
            if (form) form.reset();
            const totalDisp = document.getElementById('ingreso-total-calculado');
            if (totalDisp) totalDisp.textContent = "$0.00";

            const inputModalSku = document.getElementById('ingreso-sku');
            if (inputModalSku) {
                inputModalSku.removeAttribute('readonly');
                inputModalSku.style.backgroundColor = '';
            }
        });
    }

    // 2. Lógica de la Calculadora de Totales
    const cantInput = document.getElementById('ingreso-cantidad');
    const costoInput = document.getElementById('ingreso-costo');
    const totalDisp = document.getElementById('ingreso-total-calculado');

    function calcularTotal() {
        const cant = parseFloat(cantInput?.value) || 0;
        const costo = parseFloat(costoInput?.value) || 0;
        const total = cant * costo;
        if (totalDisp) {
            totalDisp.textContent = '$' + total.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }
    }

    if (cantInput && costoInput) {
        cantInput.addEventListener('input', calcularTotal);
        costoInput.addEventListener('input', calcularTotal);
    }
});

// ==========================================
// Lógica para Registrar un Nuevo Ingreso
// ==========================================
const formIngreso = document.getElementById('form-nuevo-ingreso');

if (formIngreso) {
    formIngreso.addEventListener('submit', async (e) => {
        e.preventDefault(); 
        
        const token = obtenerToken();
        if (!token) return;

        const payload = {
            sku_articulo: document.getElementById('ingreso-sku').value.trim(),
            codigo_almacen: document.getElementById('ingreso-almacen').value.trim(),
            cantidad: parseFloat(document.getElementById('ingreso-cantidad').value),
            costo_unitario: parseFloat(document.getElementById('ingreso-costo').value),
            numero_lote: document.getElementById('ingreso-lote').value.trim() || null,
            flujo_trabajo_seleccionado: document.getElementById('ingreso-flujo').value,
            concepto: document.getElementById('ingreso-concepto').value.trim() || "Ingreso manual"
        };

        try {
            const response = await fetch('/movimientos/ingreso', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || "Error al registrar el ingreso");
            }

            const data = await response.json();
            alert(`¡Ingreso registrado con éxito! Lote asignado: ${data.lote}`);
            
            const modalElement = document.getElementById('modalNuevoIngreso');
            const modalInstance = bootstrap.Modal.getInstance(modalElement);
            modalInstance.hide();
            formIngreso.reset();

            const inputConsultaSku = document.getElementById('input-sku');
            if (inputConsultaSku.value.trim().toUpperCase() === payload.sku_articulo.toUpperCase()) {
                document.getElementById('btn-consultar-kardex').click();
            }
            
        } catch (error) {
            console.error("Error al ingresar:", error);
            alert(`Ocurrió un error: ${error.message}`);
        }
    });
}

// ==========================================
// UX DEL MODAL: EGRESO MANUAL (FEFO)
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    const modalEgresoEl = document.getElementById('modalEgreso');
    
    if (modalEgresoEl) {
        // Autocompletar datos al abrir el modal
        modalEgresoEl.addEventListener('show.bs.modal', () => {
            const skuActual = document.getElementById('input-sku').value.trim();
            const almacenActual = document.getElementById('filtro_almacen').value.trim();
            
            const inputModalSku = document.getElementById('egreso-sku');
            const inputModalAlmacen = document.getElementById('egreso-almacen');
            
            if (skuActual && inputModalSku) {
                inputModalSku.value = skuActual;
                inputModalSku.style.backgroundColor = '#e9ecef'; 
            }
            
            if (almacenActual && inputModalAlmacen) {
                inputModalAlmacen.value = almacenActual || 'ALM-CENTRAL';
            }
        });

        // Limpiar el formulario al cerrar
        modalEgresoEl.addEventListener('hidden.bs.modal', () => {
            const form = document.getElementById('form-egreso');
            if (form) form.reset();
        });
    }
});

// ==========================================
// Lógica para Procesar el Egreso Manual
// ==========================================
const formEgreso = document.getElementById('form-egreso');

if (formEgreso) {
    formEgreso.addEventListener('submit', async (e) => {
        e.preventDefault();

        const btnProcesar = document.getElementById('btn-procesar-egreso');
        btnProcesar.disabled = true;
        btnProcesar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Procesando...';

        // 1. Recolectar datos
        const sku = document.getElementById('egreso-sku').value;
        const almacen = document.getElementById('egreso-almacen').value;
        const flujoSeleccionado = document.getElementById('egreso-flujo').value;
        const cantidad = parseFloat(document.getElementById('egreso-cantidad').value);
        const concepto = document.getElementById('egreso-concepto').value;

        // 2. Mapear el flujo elegido a un TipoMovimiento válido para el backend
        let tipoMovimiento = "OUT_SALE"; 
        if (flujoSeleccionado === "consumo_interno" || flujoSeleccionado === "baja_merma" || flujoSeleccionado === "control_calidad") {
            tipoMovimiento = "OUT_PROD"; 
        }

        const payload = {
            sku_articulo: sku,
            codigo_almacen: almacen,
            tipo_movimiento: tipoMovimiento,
            cantidad: cantidad,
            concepto: concepto,
            flujo_trabajo_seleccionado: flujoSeleccionado
        };

        try {
            const token = obtenerToken();
            if (!token) return;

            const response = await fetch('/movimientos/egreso', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (response.ok) {
                alert(`✅ ${data.mensaje}\nLotes afectados en cascada: ${data.lotes_afectados}`);
                
                // Ocultar modal usando Bootstrap nativo
                const modalInstance = bootstrap.Modal.getInstance(document.getElementById('modalEgreso'));
                modalInstance.hide();
                
                // Hacer clic virtual en el botón de consultar para recargar la tabla
                document.getElementById('btn-consultar-kardex').click();
            } else {
                alert(`❌ Error: ${data.detail || 'No se pudo procesar la salida'}`);
            }
        } catch (error) {
            console.error("Error en la petición:", error);
            alert("Ocurrió un error de conexión con el servidor.");
        } finally {
            // Restaurar el botón a su estado original
            btnProcesar.disabled = false;
            btnProcesar.innerHTML = '<i class="bi bi-check2-circle"></i> Procesar Salida';
        }
    });
}