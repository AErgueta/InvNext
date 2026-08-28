document.addEventListener('DOMContentLoaded', () => {
    // --- NUEVO: GUARDIA DE SEGURIDAD ---
    const token = localStorage.getItem('erp_token');
    const rutaActual = window.location.pathname;

    // Si NO hay token y la persona NO está en la página de login, bloqueamos
    if (!token && !rutaActual.includes('/login')) {
        alert("No está autenticado. Por favor, inicie sesión.");
        window.location.href = '/vistas/login';
        return; // Evita que se siga ejecutando el resto del script
    }
    // -----------------------------------

    const formLogin = document.getElementById('form-login');
    
    if (formLogin) {
        formLogin.addEventListener('submit', async (e) => {
            e.preventDefault(); // Evita que la página se recargue por defecto
            
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            
            // FastAPI OAuth2PasswordRequestForm exige los datos en formato URL-encoded, no JSON
            const formData = new URLSearchParams();
            formData.append('username', username);
            formData.append('password', password);

            try {
                // Petición al endpoint de autenticación de tu backend
                const response = await fetch('/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: formData
                });

                if (response.ok) {
                    const data = await response.json();
                    
                    // Guardamos el token JWT de acceso en el almacenamiento local del navegador
                    localStorage.setItem('erp_token', data.access_token);
                    
                    // Redirigimos al usuario a la pantalla del Kardex (o al menú principal)
                    window.location.href = '/vistas/dashboard';
                } else {
                    const errorData = await response.json();
                    mostrarError(errorData.detail || "Credenciales incorrectas");
                }
            } catch (error) {
                mostrarError("Error de conexión con el servidor.");
            }
        });
    }
});

function mostrarError(mensaje) {
    const errorDiv = document.getElementById('login-error');
    if (errorDiv) {
        errorDiv.textContent = mensaje;
        errorDiv.classList.remove('d-none');
    }
}

function cerrarSesion() {
    // Borramos el token y devolvemos al usuario al login
    localStorage.removeItem('erp_token');
    window.location.href = '/vistas/login';
}