from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt

from pydantic import BaseModel

from app.models.usuario import Usuario, RolUsuario
from app.core.security import verificar_password, crear_token_acceso, SECRET_KEY, ALGORITHM, obtener_password_hash

router = APIRouter(tags=["Autenticación"])

# Define la URL donde FastAPI y Swagger irán a buscar el token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

class UsuarioCreate(BaseModel):
    username: str
    password: str
    rol: RolUsuario = RolUsuario.OPERADOR
    codigo_almacen: str | None = None

class EstadoUsuario(BaseModel):
    activo: bool

class CambiarPassword(BaseModel):
    password_actual: str
    nueva_password: str

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    usuario = await Usuario.find_one(Usuario.username == form_data.username)
    
    if not usuario or not verificar_password(form_data.password, usuario.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not usuario.activo:
        raise HTTPException(status_code=400, detail="Usuario inactivo")
        
    # Metemos datos clave en el token para no tener que consultar la BD a cada rato
    token = crear_token_acceso(
        data={"sub": usuario.username, "rol": usuario.rol, "almacen": usuario.codigo_almacen}
    )
    return {"access_token": token, "token_type": "bearer"}

# --- EL GUARDIA DE SEGURIDAD ---
async def obtener_usuario_actual(token: str = Depends(oauth2_scheme)) -> Usuario:
    """
    Ponemos esta dependencia en cualquier ruta que queramos proteger.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Token inválido")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token expirado o inválido")
        
    usuario = await Usuario.find_one(Usuario.username == username)
    if usuario is None:
        raise HTTPException(status_code=401, detail="El usuario ya no existe")
        
    return usuario


@router.post("/registrar", status_code=status.HTTP_201_CREATED)
async def registrar_usuario(
    datos: UsuarioCreate,
    usuario_actual: Usuario = Depends(obtener_usuario_actual) # <--- EL GUARDIA PROTEGIENDO EL REGISTRO
):
    # 0. Validamos que solo un ADMIN pueda crear otros usuarios
    if usuario_actual.rol != RolUsuario.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Solo los administradores pueden dar de alta al nuevo personal."
        )

    # 1. Verificamos que el usuario no exista ya
    existe = await Usuario.find_one(Usuario.username == datos.username)
    if existe:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya está en uso")
        
    # 2. Encriptamos la contraseña
    hash_pass = obtener_password_hash(datos.password)
    
    # 3. Guardamos en la BD el modelo seguro
    nuevo_usuario = Usuario(
        username=datos.username,
        hashed_password=hash_pass,
        rol=datos.rol,
        codigo_almacen=datos.codigo_almacen
    )
    await nuevo_usuario.insert()
    
    return {"mensaje": f"Usuario '{nuevo_usuario.username}' creado con éxito y asignado al rol {nuevo_usuario.rol}"}

@router.patch("/{username}/estado", status_code=status.HTTP_200_OK)
async def cambiar_estado_usuario(
    username: str,
    estado: EstadoUsuario,
    usuario_actual: Usuario = Depends(obtener_usuario_actual)
):
    """
    Activa o desactiva a un usuario.
    Solo accesible para Administradores.
    """
    # 1. Validamos rol
    if usuario_actual.rol != RolUsuario.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Solo los administradores pueden activar o desactivar usuarios."
        )

    # 2. Buscamos al usuario
    usuario = await Usuario.find_one(Usuario.username == username)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    # 3. Seguro anti-bloqueo: El admin no puede desactivarse a sí mismo
    if usuario.username == usuario_actual.username and not estado.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Operación rechazada: No puedes desactivar tu propia cuenta de administrador."
        )

    # 4. Aplicamos y guardamos
    usuario.activo = estado.activo
    await usuario.save()

    estado_str = "activado" if usuario.activo else "desactivado"
    return {"mensaje": f"El usuario '{username}' ha sido {estado_str} exitosamente."}


@router.put("/cambiar-password", status_code=status.HTTP_200_OK)
async def actualizar_password(
    datos: CambiarPassword,
    usuario_actual: Usuario = Depends(obtener_usuario_actual)
):
    """
    Permite a cualquier usuario autenticado cambiar su propia contraseña.
    """
    # 1. Verificar que la contraseña actual enviada sea correcta
    if not verificar_password(datos.password_actual, usuario_actual.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual es incorrecta."
        )

    # 2. Encriptar la nueva contraseña
    usuario_actual.hashed_password = obtener_password_hash(datos.nueva_password)
    
    # 3. Guardar en la base de datos
    await usuario_actual.save()

    return {"mensaje": "Contraseña actualizada exitosamente."}