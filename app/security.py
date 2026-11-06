import time, jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from .config import JWT_SECRET

ph = PasswordHasher()

def hash_password(p: str) -> str:
    return ph.hash(p)

def verify_password(hashed: str, p: str) -> bool:
    try:
        return ph.verify(hashed, p)
    except VerifyMismatchError:
        return False

def make_token(user_id: int) -> str:
    now = int(time.time())
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + 3600},
                      JWT_SECRET, algorithm="HS256")
