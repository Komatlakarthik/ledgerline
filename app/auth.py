import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from .db import get_conn
from .security import hash_password, verify_password, make_token

router = APIRouter(prefix="/auth", tags=["auth"])

class Credentials(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=8, max_length=128)

@router.post("/register", status_code=201)
def register(body: Credentials, conn=Depends(get_conn)):
    try:
        row = conn.execute(
            "INSERT INTO users (email, password_hash, role) "
            "VALUES (%s, %s, 'holder') RETURNING id, email, role",
            (body.email.lower(), hash_password(body.password))).fetchone()
        conn.execute(
            "INSERT INTO accounts (owner_id, name, is_system, balance_paise) "
            "VALUES (%s, %s, false, 0)",
            (row["id"], f"{body.email.lower().split('@')[0]}'s Primary Account"))
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "Email already registered")
    return row

@router.post("/login")
def login(body: Credentials, conn=Depends(get_conn)):
    u = conn.execute("SELECT id, password_hash FROM users WHERE email = %s",
                     (body.email.lower(),)).fetchone()
    if not u or not verify_password(u["password_hash"], body.password):
        raise HTTPException(401, "Invalid credentials")
    return {"access_token": make_token(u["id"]), "token_type": "bearer"}
