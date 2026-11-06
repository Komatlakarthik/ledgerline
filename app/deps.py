import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from .config import JWT_SECRET
from .db import get_conn

bearer = HTTPBearer()

def current_user(creds=Depends(bearer), conn=Depends(get_conn)):
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    user = conn.execute("SELECT id, email, role FROM users WHERE id = %s",
                        (int(payload["sub"]),)).fetchone()
    if not user:
        raise HTTPException(401, "Invalid or expired token")
    return user

def require_roles(*roles):
    def dep(user=Depends(current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "Forbidden")
        return user
    return dep
