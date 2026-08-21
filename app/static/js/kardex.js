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

// --- Lógica para pintar la tabla en pantalla ---
document.getElementById('btn-consultar-kardex').addEventListener('click', async (e) => {
    const token = obtenerToken();
    if (!token) return;

    const sku = document.getElementById('input-sku').value.trim();
        
    if (!sku) {
        alert("Por favor, escribe el SKU del artículo que deseas consultar.");
        return;
    }

    const inputInicio = document.getElementById('fecha-inicio').value;
    const inputFin = document.getElementById('fecha-fin').value;
    const inputAlmacen = document.getElementById('filtro_almacen').value;
    
    let url = `/movimientos/${sku}`;
    
    const params = new URLSearchParams();
    if (inputAlmacen) params.append('codigo_almacen', inputAlmacen);
    if (inputInicio) params.append('fecha_inicio', `${inputInicio}T00:00:00`);
    if (inputFin) params.append('fecha_fin', `${inputFin}T23:59:59`);
    
    if (params.toString()) {
        url += `?${params.toString()}`;
    }

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
        
        // Capturamos la unidad de medida enviada por el backend
        const unidad = data.unidad_medida || ""; 
        
        let htmlFilas = "";
        let saldoActual = data.saldo_inicial;
        let valorInicial = saldoActual === 0 ? "$0.00" : "-"; 

        // Agregamos la unidad al Saldo Inicial
        htmlFilas += `
            <tr style="background-color: #f8f9fa; font-weight: bold;">
                <td>-</td>
                <td>SALDO INICIAL</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>${saldoActual.toLocaleString('en-US')} ${unidad}</td> 
                <td>${valorInicial}</td>
            </tr>
        `;

        if (data.movimientos.length === 0) {
            htmlFilas += `<tr><td colspan="9" class="text-center">No hay movimientos en este rango de fechas.</td></tr>`;
        } else {
            data.movimientos.forEach(mov => {
                let ingreso = 0;
                let egreso = 0;
                
                const tiposIngreso = ["IN", "IN_PROD", "IN_TRANS"];
                const tiposEgreso = ["OUT_SALE", "OUT_PROD", "OUT_TRANS"];
                
                const tipo = mov.tipo_movimiento.toUpperCase();
                
                if (tiposIngreso.includes(tipo)) {
                    ingreso = mov.cantidad;
                    saldoActual += mov.cantidad;
                } else if (tiposEgreso.includes(tipo)) {
                    egreso = mov.cantidad;
                    saldoActual -= mov.cantidad;
                }

                const saldoDinero = saldoActual * mov.costo_unitario;
                const fechaLimpia = new Date(mov.fecha_registro).toLocaleString();
                
                const colorFondo = ingreso > 0 ? '#e8f5e9' : '#ffebee';
                const colorTexto = ingreso > 0 ? 'green' : 'red';

                // Agregamos la unidad a los ingresos y egresos
                const ingresoStr = ingreso > 0 ? '+' + ingreso.toLocaleString('en-US') + ' ' + unidad : '-';
                const egresoStr = egreso > 0 ? '-' + egreso.toLocaleString('en-US') + ' ' + unidad : '-';

                htmlFilas += `
                    <tr style="background-color: ${colorFondo};">
                        <td style="padding: 8px;">${fechaLimpia}</td>
                        <td>${mov.concepto}</td>
                        <td>${mov.numero_lote || '-'}</td>
                        <td>${mov.tipo_movimiento}</td>
                        <td>$${mov.costo_unitario.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                        <td style="color: ${colorTexto}; font-weight: bold;">${ingresoStr}</td>
                        <td style="color: ${colorTexto}; font-weight: bold;">${egresoStr}</td>
                        <td style="font-weight: bold;">${saldoActual.toLocaleString('en-US')} ${unidad}</td> 
                        <td style="font-weight: bold; color: #0056b3;">$${saldoDinero.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                    </tr>
                `;
            });
        }

        tbody.innerHTML = htmlFilas;

    } catch (error) {
        console.error("Error:", error);
        tbody.innerHTML = '<tr><td colspan="9" style="color: red; text-align: center;">Ocurrió un error al cargar el Kardex.</td></tr>';
    }
});

// --- Lógica para exportar el Kardex a CSV ---
document.getElementById('btn-descargar-kardex').addEventListener('click', async () => {
    const token = obtenerToken();
    if (!token) return;

    const sku = document.getElementById('input-sku').value.trim();
        
    if (!sku) {
        alert("Por favor, escribe el SKU del artículo que deseas exportar.");
        return;
    }

    const inputInicio = document.getElementById('fecha-inicio').value;
    const inputFin = document.getElementById('fecha-fin').value;
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