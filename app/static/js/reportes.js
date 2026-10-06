document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('erp_token');
    if (!token) {
        window.location.href = '/vistas/login';
        return;
    }

    // ==========================================
    // BARRERA DE SEGURIDAD RBAC (FRONTEND)
    // ==========================================
    try {
        const resPerfil = await fetch('/me', {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (resPerfil.ok) {
            const perfil = await resPerfil.json();
            if (perfil.rol !== 'ADMIN') {
                alert("Acceso Denegado: Esta vista es exclusiva para Administradores.");
                window.location.href = '/vistas/dashboard';
                return;
            }
        } else {
             window.location.href = '/vistas/login';
             return;
        }
    } catch (error) {
        console.error("Error validando permisos:", error);
        window.location.href = '/vistas/dashboard';
        return;
    }

    // ==========================================
    // INICIALIZACIÓN DE FECHAS
    // ==========================================
    const inputDesde = document.getElementById('fecha-desde');
    const inputHasta = document.getElementById('fecha-hasta');
    const btnConsultar = document.getElementById('btn-consultar');

    // Por defecto, seleccionar el mes actual
    const hoy = new Date();
    const primerDiaMes = new Date(hoy.getFullYear(), hoy.getMonth(), 1);
    
    inputDesde.value = primerDiaMes.toISOString().split('T')[0];
    inputHasta.value = hoy.toISOString().split('T')[0];

    // Utilidad para moneda
    const formatearMoneda = (valor) => {
        return new Intl.NumberFormat('es-BO', { 
            style: 'currency', 
            currency: 'BOB', // Cambia a USD si prefieres
            minimumFractionDigits: 2 
        }).format(valor);
    };

    // ==========================================
    // LÓGICA DE CONSULTA
    // ==========================================
    const consultarReportes = async () => {
        // Formateamos las fechas para que FastAPI las entienda como datetime
        const fechaInicio = `${inputDesde.value}T00:00:00`;
        const fechaFin = `${inputHasta.value}T23:59:59`;

        btnConsultar.disabled = true;
        btnConsultar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Cargando...';

        try {
            // Ejecutamos las 4 llamadas en paralelo para máxima velocidad
            const headers = { 'Authorization': `Bearer ${token}` };
            const params = `?fecha_inicio=${fechaInicio}&fecha_fin=${fechaFin}`;

            const [resGenerales, resArticulos, resSucursales, resCajas] = await Promise.all([
                fetch(`/reportes/ventas-generales${params}`, { headers }),
                fetch(`/reportes/ventas-por-articulo${params}&limite=10`, { headers }),
                fetch(`/reportes/ventas-por-sucursal${params}`, { headers }),
                fetch(`/reportes/ventas-por-caja${params}`, { headers })
            ]);

            if (!resGenerales.ok) throw new Error("Error obteniendo datos generales");

            const dataGenerales = await resGenerales.json();
            const dataArticulos = await resArticulos.json();
            const dataSucursales = await resSucursales.json();
            const dataCajas = await resCajas.json();

            renderizarGenerales(dataGenerales);
            renderizarArticulos(dataArticulos);
            renderizarSucursales(dataSucursales);
            renderizarCajas(dataCajas);

        } catch (error) {
            console.error("Error al cargar reportes:", error);
            alert("No se pudieron cargar los reportes. Verifica tu conexión.");
        } finally {
            btnConsultar.disabled = false;
            btnConsultar.innerHTML = '<i class="bi bi-search"></i> Consultar';
        }
    };

    // ==========================================
    // FUNCIONES DE RENDERIZADO
    // ==========================================
    const renderizarGenerales = (data) => {
        const ingresos = data.total_ingresos || 0;
        const cantidad = data.cantidad_ventas || 0;
        const promedio = cantidad > 0 ? (ingresos / cantidad) : 0;

        document.getElementById('resumen-ingresos').textContent = formatearMoneda(ingresos);
        document.getElementById('resumen-cantidad').textContent = cantidad;
        document.getElementById('resumen-promedio').textContent = formatearMoneda(promedio);
        document.getElementById('resumen-descuentos').textContent = `Descuentos: ${formatearMoneda(data.descuentos_otorgados || 0)}`;
    };

    const renderizarArticulos = (articulos) => {
        const tbody = document.getElementById('tabla-articulos');
        tbody.innerHTML = '';

        if (!articulos || articulos.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted py-3">No hay ventas registradas en este periodo.</td></tr>';
            return;
        }

        articulos.forEach(art => {
            tbody.innerHTML += `
                <tr>
                    <td>
                        <span class="fw-bold d-block">${art.nombre_articulo}</span>
                        <small class="text-muted">${art._id}</small>
                    </td>
                    <td class="text-center fw-bold">${art.cantidad_vendida}</td>
                    <td class="text-end text-success fw-bold">${formatearMoneda(art.ingreso_generado)}</td>
                </tr>
            `;
        });
    };

    const renderizarSucursales = (sucursales) => {
        const lista = document.getElementById('lista-sucursales');
        lista.innerHTML = '';

        if (!sucursales || sucursales.length === 0) {
            lista.innerHTML = '<li class="list-group-item text-center text-muted py-3">Sin datos</li>';
            return;
        }

        sucursales.forEach(suc => {
            lista.innerHTML += `
                <li class="list-group-item d-flex justify-content-between align-items-center py-3">
                    <div>
                        <span class="fw-bold d-block"><i class="bi bi-building"></i> ${suc._id}</span>
                        <small class="text-muted">${suc.cantidad_ventas} tickets emitidos</small>
                    </div>
                    <span class="badge bg-primary rounded-pill fs-6">${formatearMoneda(suc.total_ingresos)}</span>
                </li>
            `;
        });
    };

    const renderizarCajas = (cajas) => {
        const tbody = document.getElementById('tabla-cajas');
        tbody.innerHTML = '';

        if (!cajas || !Array.isArray(cajas) || cajas.length === 0) {
            tbody.innerHTML = '<tr><td colspan="2" class="text-center text-muted py-3">Sin registros de caja</td></tr>';
            return;
        }

        cajas.forEach(c => {
            let iconoPago = 'bi-cash';
            const metodo = (c.metodo_pago || 'EFECTIVO').toUpperCase();
            if(metodo.includes('TARJETA')) iconoPago = 'bi-credit-card';
            else if(metodo.includes('TRANSFERENCIA') || metodo.includes('QR')) iconoPago = 'bi-qr-code';

            tbody.innerHTML += `
                <tr>
                    <td>
                        <span class="fw-bold d-block">${c.caja_id || 'GENERAL'}</span>
                        <small class="text-muted"><i class="bi ${iconoPago}"></i> ${c.metodo_pago || 'EFECTIVO'}</small>
                    </td>
                    <td class="text-end fw-bold">${formatearMoneda(c.total_recaudado || 0)}</td>
                </tr>
            `;
        });
    };

    // Disparar evento de submit
    document.getElementById('form-filtros').addEventListener('submit', (e) => {
        e.preventDefault();
        consultarReportes();
    });

    // Carga inicial automática
    consultarReportes();
});