document.addEventListener('DOMContentLoaded', async () => {
    // Verificar autenticación
    const token = localStorage.getItem('erp_token');
    if (!token) {
        alert("Sesión no válida. Inicie sesión nuevamente.");
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
                alert("Acceso Denegado: No tienes permisos de administrador para realizar ajustes de inventario.");
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
    // CARGAR ALMACENES EN EL SELECT
    // ==========================================
    const selectAlmacen = document.getElementById('ajuste-almacen');
    try {
        const resAlm = await fetch('/almacenes/', { headers: { 'Authorization': `Bearer ${token}` } });
        if (resAlm.ok) {
            const almacenes = await resAlm.json();
            selectAlmacen.innerHTML = '<option value="">-- Seleccione un almacén --</option>';
            almacenes.filter(a => a.activo).forEach(a => {
                selectAlmacen.innerHTML += `<option value="${a.codigo}">${a.nombre} (${a.codigo})</option>`;
            });
        }
    } catch (error) {
        console.error("Error cargando almacenes:", error);
        selectAlmacen.innerHTML = '<option value="">Error al cargar almacenes</option>';
    }

    // ==========================================
    // BÚSQUEDA INTELIGENTE DE ARTÍCULOS
    // ==========================================
    const inputBusqueda = document.getElementById('input-busqueda-ajuste');
    const inputSkuOculto = document.getElementById('ajuste-sku');
    const dropdownResultados = document.getElementById('dropdown-resultados-ajuste');
    let timeoutBusqueda;

    if (inputBusqueda) {
        inputBusqueda.addEventListener('input', (e) => {
            clearTimeout(timeoutBusqueda);
            const query = e.target.value.trim();

            if (query.length < 2) {
                dropdownResultados.classList.remove('show');
                inputSkuOculto.value = '';
                // Limpiar también el lote si cambia de artículo
                document.getElementById('ajuste-lote').value = '';
                document.getElementById('msg-caducidad').textContent = 'Ingrese lote para habilitar.';
                return;
            }

            timeoutBusqueda = setTimeout(async () => {
                try {
                    const response = await fetch(`/articulos/buscar?q=${encodeURIComponent(query)}`, {
                        headers: { 'Authorization': `Bearer ${token}` }
                    });
                    
                    if (response.ok) {
                        const resultados = await response.json();
                        dropdownResultados.innerHTML = '';
                        
                        if (resultados.length === 0) {
                            dropdownResultados.innerHTML = '<li><span class="dropdown-item text-muted">No encontrado</span></li>';
                        } else {
                            resultados.forEach(art => {
                                const li = document.createElement('li');
                                li.innerHTML = `<a class="dropdown-item" href="#" style="cursor: pointer; white-space: normal;">
                                    <strong>${art.sku}</strong> - ${art.nombre} 
                                </a>`;
                                
                                li.addEventListener('click', (evento) => {
                                    evento.preventDefault();
                                    inputSkuOculto.value = art.sku;           
                                    inputBusqueda.value = `${art.sku} - ${art.nombre}`;   
                                    dropdownResultados.classList.remove('show');
                                    
                                    // Limpiar lote previo
                                    document.getElementById('ajuste-lote').value = '';
                                    document.getElementById('ajuste-caducidad').value = '';
                                    document.getElementById('ajuste-caducidad').disabled = true;
                                    
                                    document.getElementById('ajuste-lote').focus();
                                });
                                
                                dropdownResultados.appendChild(li);
                            });
                        }
                        dropdownResultados.classList.add('show');
                    }
                } catch (error) {
                    console.error("Error buscando:", error);
                }
            }, 300);
        });

        document.addEventListener('click', (e) => {
            if (!inputBusqueda.contains(e.target) && !dropdownResultados.contains(e.target)) {
                dropdownResultados.classList.remove('show');
            }
        });
    }

    // ==========================================
    // MAGIA INTELIGENTE: VALIDACIÓN DE LOTE
    // ==========================================
    const inputLote = document.getElementById('ajuste-lote');
    const inputCaducidad = document.getElementById('ajuste-caducidad');
    const msgCaducidad = document.getElementById('msg-caducidad');

    if (inputLote) {
        inputLote.addEventListener('blur', async () => {
            const sku = inputSkuOculto.value.trim();
            const lote = inputLote.value.trim().toUpperCase();

            // Si dejó el lote vacío, deshabilitamos la caducidad
            if (!lote) {
                inputCaducidad.value = '';
                inputCaducidad.disabled = true;
                inputCaducidad.required = false;
                msgCaducidad.textContent = "Ingrese lote para habilitar.";
                msgCaducidad.className = "form-text small text-info";
                return;
            }

            if (!sku) {
                alert("Primero seleccione un artículo para poder validar su lote.");
                inputLote.value = '';
                return;
            }

            // Consultar al backend
            try {
                const res = await fetch(`/lotes/${encodeURIComponent(sku)}/${encodeURIComponent(lote)}`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });

                if (res.ok) {
                    // EL LOTE YA EXISTE
                    const data = await res.json();
                    
                    // CORRECCIÓN: El backend devuelve 'fecha_vencimiento'
                    if (data.fecha_vencimiento) {
                        const fecha = new Date(data.fecha_vencimiento).toISOString().split('T')[0];
                        inputCaducidad.value = fecha;
                    } else {
                        inputCaducidad.value = ''; // Por si es un lote que se guardó sin fecha
                    }
                    
                    inputCaducidad.disabled = true; 
                    inputCaducidad.required = false;
                    msgCaducidad.textContent = "✅ Lote registrado. Fecha autocompletada.";
                    msgCaducidad.className = "form-text small text-success fw-bold";
                } else if (res.status === 404) {
                    // EL LOTE ES NUEVO (FANTASMA)
                    inputCaducidad.value = '';
                    inputCaducidad.disabled = false; 
                    inputCaducidad.required = true;  
                    msgCaducidad.textContent = "⚠️ Lote nuevo detectado. Indique la caducidad.";
                    msgCaducidad.className = "form-text small text-danger fw-bold";
                }
            } catch (error) {
                console.error("Error al validar el lote:", error);
            }
        });
    }
    
    // ==========================================
    // PROCESAMIENTO DEL FORMULARIO
    // ==========================================
    const formAjuste = document.getElementById('form-ajuste-fisico');
    const btnProcesar = document.getElementById('btn-procesar-ajuste');

    if (formAjuste) {
        formAjuste.addEventListener('submit', async (e) => {
            e.preventDefault(); 

            const sku = document.getElementById('ajuste-sku').value.trim().toUpperCase();
            const almacen = document.getElementById('ajuste-almacen').value.trim().toUpperCase();
            const lote = document.getElementById('ajuste-lote').value.trim().toUpperCase();
            const caducidad = document.getElementById('ajuste-caducidad').value;
            const cantidad = parseFloat(document.getElementById('ajuste-cantidad').value);
            const flujo = document.getElementById('ajuste-flujo').value;
            const concepto = document.getElementById('ajuste-concepto').value.trim();

            if (!sku) {
                alert("⚠️ Por favor, busque y seleccione un artículo de la lista desplegable.");
                inputBusqueda.focus();
                return;
            }

            if (!flujo) {
                alert("⚠️ Debe elegir manualmente un flujo de seguimiento obligatoriamente.");
                return;
            }

            const payload = {
                sku_articulo: sku,
                codigo_almacen: almacen,
                cantidad_encontrada: cantidad,
                concepto: concepto,
                flujo_trabajo_seleccionado: flujo,
                numero_lote: lote || null,
                fecha_caducidad: caducidad || null // Añadimos la fecha por si es un lote nuevo
            };

            btnProcesar.disabled = true;
            btnProcesar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Registrando...';

            try {
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
                    formAjuste.reset(); 
                    inputSkuOculto.value = ''; 
                    inputCaducidad.disabled = true;
                    msgCaducidad.textContent = "Ingrese lote para habilitar.";
                    msgCaducidad.className = "form-text small text-info";
                } else {
                    alert(`❌ Error: ${data.detail || 'No se pudo procesar el ajuste.'}`);
                }
            } catch (error) {
                console.error("Error al procesar el ajuste:", error);
                alert("Error de conexión con el servidor.");
            } finally {
                btnProcesar.disabled = false;
                btnProcesar.innerHTML = '<i class="bi bi-save"></i> Registrar Conteo y Ajustar Stock';
            }
        });
    }
});