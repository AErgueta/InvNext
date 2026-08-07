from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext

# En producción, esto debe venir de un archivo .env
SECRET_KEY = "tu_super_clave_secreta_inventario" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120 # El token dura 2 horas

# Motor de encriptación
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verificar_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def obtener_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def crear_token_acceso(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt