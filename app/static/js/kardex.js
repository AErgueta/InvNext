// --- Lógica para pintar la tabla en pantalla ---
document.getElementById('btn-consultar-kardex').addEventListener('click', async (e) => {
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
    if (inputAlmacen) {
        params.append('codigo_almacen', inputAlmacen);
    }
    if (inputInicio) params.append('fecha_inicio', `${inputInicio}T00:00:00`);
    if (inputFin) params.append('fecha_fin', `${inputFin}T23:59:59`);
    
    if (params.toString()) {
        url += `?${params.toString()}`;
    }

    const tbody = document.getElementById('cuerpo-tabla-kardex');
    tbody.innerHTML = '<tr><td colspan="9">⏳ Cargando datos...</td></tr>';

    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error("Error al obtener los datos");
        
        const data = await response.json();
        
        let htmlFilas = "";
        let saldoActual = data.saldo_inicial;

        // Fila del saldo inicial con separador de miles
        let valorInicial = saldoActual === 0 ? "$0.00" : "-"; 

        htmlFilas += `
            <tr style="background-color: #f8f9fa; font-weight: bold;">
                <td>-</td>
                <td>SALDO INICIAL</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>${saldoActual.toLocaleString('en-US')}</td>
                <td>${valorInicial}</td>
            </tr>
        `;

        if (data.movimientos.length === 0) {
            htmlFilas += `<tr><td colspan="9">No hay movimientos en este rango de fechas.</td></tr>`;
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

                // Aplicando toLocaleString('en-US') para los separadores de miles
                const ingresoStr = ingreso > 0 ? '+' + ingreso.toLocaleString('en-US') : '-';
                const egresoStr = egreso > 0 ? '-' + egreso.toLocaleString('en-US') : '-';

                htmlFilas += `
                    <tr style="background-color: ${colorFondo};">
                        <td style="padding: 8px;">${fechaLimpia}</td>
                        <td>${mov.concepto}</td>
                        <td>${mov.numero_lote || '-'}</td>
                        <td>${mov.tipo_movimiento}</td>
                        <td>$${mov.costo_unitario.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                        <td style="color: ${colorTexto}; font-weight: bold;">${ingresoStr}</td>
                        <td style="color: ${colorTexto}; font-weight: bold;">${egresoStr}</td>
                        <td style="font-weight: bold;">${saldoActual.toLocaleString('en-US')}</td>
                        <td style="font-weight: bold; color: #0056b3;">$${saldoDinero.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                    </tr>
                `;
            });
        }

        tbody.innerHTML = htmlFilas;

    } catch (error) {
        console.error("Error:", error);
        tbody.innerHTML = '<tr><td colspan="9" style="color: red;">Ocurrió un error al cargar el Kardex.</td></tr>';
    }
});

// --- Lógica para exportar el Kardex a CSV ---
document.getElementById('btn-descargar-kardex').addEventListener('click', () => {
    const sku = document.getElementById('input-sku').value.trim();
        
    if (!sku) {
        alert("Por favor, escribe el SKU del artículo que deseas exportar.");
        return;
    }

    const inputInicio = document.getElementById('fecha-inicio').value;
    const inputFin = document.getElementById('fecha-fin').value;
    const inputAlmacen = document.getElementById('filtro_almacen').value;
    
    // Apuntamos al endpoint de exportación que creaste en el backend
    let url = `/movimientos/${sku}/exportar`;
    
    const params = new URLSearchParams();
    if (inputAlmacen) {
        params.append('codigo_almacen', inputAlmacen);
    }
    if (inputInicio) params.append('fecha_inicio', `${inputInicio}T00:00:00`);
    if (inputFin) params.append('fecha_fin', `${inputFin}T23:59:59`);
    
    if (params.toString()) {
        url += `?${params.toString()}`;
    }

    // Redirige al navegador para disparar la descarga automática del archivo CSV
    window.location.href = url;
});