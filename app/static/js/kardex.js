// --- Lógica para pintar la tabla en pantalla ---
document.getElementById('btn-consultar-kardex').addEventListener('click', async (e) => {
    const sku = document.getElementById('input-sku').value.trim();
        
    if (!sku) {
        alert("Por favor, escribe el SKU del artículo que deseas consultar.");
        return;
    }
    const inputInicio = document.getElementById('fecha-inicio').value;
    const inputFin = document.getElementById('fecha-fin').value;
    
    let url = `/movimientos/${sku}`;
    
    const params = new URLSearchParams();
    if (inputInicio) params.append('fecha_inicio', `${inputInicio}T00:00:00`);
    if (inputFin) params.append('fecha_fin', `${inputFin}T23:59:59`);
    
    if (params.toString()) {
        url += `?${params.toString()}`;
    }

    const tbody = document.getElementById('cuerpo-tabla-kardex');
    tbody.innerHTML = '<tr><td colspan="8">⏳ Cargando datos...</td></tr>';

    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error("Error al obtener los datos");
        
        const data = await response.json();
        
        // 1. Creamos un "contenedor" de texto para armar todo el HTML junto
        // Esto evita que el navegador rompa la tabla al pintarla
        let htmlFilas = "";
        let saldoActual = data.saldo_inicial;

        // Fila del saldo inicial
        htmlFilas += `
            <tr style="background-color: #f8f9fa; font-weight: bold;">
                <td>-</td>
                <td>SALDO INICIAL</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>${saldoActual}</td>
            </tr>
        `;

        if (data.movimientos.length === 0) {
            htmlFilas += `<tr><td colspan="8">No hay movimientos en este rango de fechas.</td></tr>`;
        } else {
            // 2. Armamos cada fila
            data.movimientos.forEach(mov => {
                let ingreso = 0;
                let egreso = 0;
                
                // CORRECCIÓN MATE: Ahora reconoce tus códigos "IN" (y similares)
                const tipo = mov.tipo_movimiento.toUpperCase();
                if (tipo === 'IN' || tipo.includes('ENTRADA')) {
                    ingreso = mov.cantidad;
                    saldoActual += mov.cantidad;
                } else {
                    egreso = mov.cantidad;
                    saldoActual -= mov.cantidad;
                }

                const fechaLimpia = new Date(mov.fecha_registro).toLocaleString();
                
                // BONUS: Colores tenues para saber si entró o salió
                const colorFondo = ingreso > 0 ? '#e8f5e9' : '#ffebee';
                const colorTexto = ingreso > 0 ? 'green' : 'red';

                htmlFilas += `
                    <tr style="background-color: ${colorFondo};">
                        <td style="padding: 8px;">${fechaLimpia}</td>
                        <td>${mov.concepto}</td>
                        <td>${mov.numero_lote || '-'}</td>
                        <td>${mov.tipo_movimiento}</td>
                        <td>$${mov.costo_unitario.toFixed(2)}</td>
                        <td style="color: ${colorTexto}; font-weight: bold;">${ingreso > 0 ? '+' + ingreso : '-'}</td>
                        <td style="color: ${colorTexto}; font-weight: bold;">${egreso > 0 ? '-' + egreso : '-'}</td>
                        <td style="font-weight: bold;">${saldoActual}</td>
                    </tr>
                `;
            });
        }

        // 3. Inyectamos TODO el HTML de un solo golpe al cuerpo de la tabla
        tbody.innerHTML = htmlFilas;

    } catch (error) {
        console.error("Error:", error);
        tbody.innerHTML = '<tr><td colspan="8" style="color: red;">Ocurrió un error al cargar el Kardex.</td></tr>';
    }
});