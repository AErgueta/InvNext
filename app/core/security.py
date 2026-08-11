from datetime import datetime, timedelta, timezone
import jwt
import bcrypt

# En producción, esto debe venir de un archivo .env
SECRET_KEY = "tu_super_clave_secreta_inventario" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120 # El token dura 2 horas

def verificar_password(plain_password: str, hashed_password: str) -> bool:
    # bcrypt requiere que las cadenas sean convertidas a bytes antes de operarlas
    password_byte_enc = plain_password.encode('utf-8')
    hashed_password_byte_enc = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_byte_enc, hashed_password_byte_enc)

def obtener_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    # Devolvemos un string normal (decodificado) para que se guarde limpio en MongoDB
    return hashed_password.decode('utf-8')

def crear_token_acceso(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt