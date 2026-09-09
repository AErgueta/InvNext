document.addEventListener('DOMContentLoaded', () => {
    // Verificar autenticación
    const token = localStorage.getItem('erp_token');
    if (!token) {
        alert("Sesión no válida. Inicie sesión nuevamente.");
        window.location.href = '/vistas/login';
        return;
    }

    const formAjuste = document.getElementById('form-ajuste-fisico');
    const btnProcesar = document.getElementById('btn-procesar-ajuste');

    if (formAjuste) {
        formAjuste.addEventListener('submit', async (e) => {
            e.preventDefault(); // Evitamos que la página se recargue

            // 1. Recopilamos los datos del formulario
            const sku = document.getElementById('ajuste-sku').value.trim().toUpperCase();
            const almacen = document.getElementById('ajuste-almacen').value.trim().toUpperCase();
            const lote = document.getElementById('ajuste-lote').value.trim().toUpperCase();
            const cantidad = parseFloat(document.getElementById('ajuste-cantidad').value);
            const flujo = document.getElementById('ajuste-flujo').value;
            const concepto = document.getElementById('ajuste-concepto').value.trim();

            if (!flujo) {
                alert("⚠️ Debe elegir manualmente un flujo de seguimiento obligatoriamente.");
                return;
            }

            // 2. Armamos el payload (PeticionAjusteFisico)
            const payload = {
                sku_articulo: sku,
                codigo_almacen: almacen,
                cantidad_encontrada: cantidad,
                concepto: concepto,
                flujo_trabajo_seleccionado: flujo,
                numero_lote: lote || null // Si está vacío, enviamos null
            };

            // Cambiamos el estado del botón para evitar múltiples clics
            btnProcesar.disabled = true;
            btnProcesar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Registrando...';

            try {
                // 3. Enviamos la petición al backend
                const response = await fetch('/movimientos/ajuste-fisico', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                });

                const data = await response.json();

                if (response.ok) {
                    alert(`✅ Éxito: ${data.mensaje}`);
                    formAjuste.reset(); // Limpiamos el formulario para el siguiente conteo
                    // Restaurar valores por defecto visuales si es necesario
                    document.getElementById('ajuste-almacen').value = "ALM-CENTRAL";
                } else {
                    alert(`❌ Error: ${data.detail || 'No se pudo procesar el ajuste.'}`);
                }
            } catch (error) {
                console.error("Error al procesar el ajuste:", error);
                alert("Error de conexión con el servidor.");
            } finally {
                // Restauramos el botón
                btnProcesar.disabled = false;
                btnProcesar.innerHTML = '<i class="bi bi-save"></i> Registrar Conteo y Ajustar Stock';
            }
        });
    }
});