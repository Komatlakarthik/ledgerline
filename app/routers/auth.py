from typing import Literal, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from psycopg.rows import dict_row

from app.db import get_db
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_role,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    role: Literal["admin", "holder", "auditor"] = "holder"

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    created_at: datetime
    account_id: Optional[int] = None

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest):
    """Registers a new user and creates an account for holders."""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # Check existing email
            cur.execute("SELECT id FROM users WHERE email = %s;", (payload.email.lower(),))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered",
                )

            # Insert new user with Argon2 hash
            hashed = hash_password(payload.password)
            cur.execute(
                """
                INSERT INTO users (email, password_hash, role)
                VALUES (%s, %s, %s)
                RETURNING id, email, role, created_at;
                """,
                (payload.email.lower(), hashed, payload.role),
            )
            user = cur.fetchone()

            account_id = None
            if payload.role == "holder":
                # Create initial primary account
                cur.execute(
                    """
                    INSERT INTO accounts (owner_id, name, is_system, balance_paise)
                    VALUES (%s, %s, false, 0)
                    RETURNING id;
                    """,
                    (user["id"], f"{payload.email.split('@')[0]}'s Primary Account"),
                )
                account_id = cur.fetchone()["id"]

            conn.commit()

            token = create_access_token(user["id"], user["email"], user["role"])
            user_resp = UserResponse(
                id=user["id"],
                email=user["email"],
                role=user["role"],
                created_at=user["created_at"],
                account_id=account_id,
            )
            return AuthResponse(access_token=token, user=user_resp)

@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest):
    """Authenticates a user and returns a signed JWT."""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id, email, password_hash, role, created_at FROM users WHERE email = %s;",
                (payload.email.lower(),),
            )
            user = cur.fetchone()
            if not user or not verify_password(user["password_hash"], payload.password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            account_id = None
            if user["role"] == "holder":
                cur.execute(
                    "SELECT id FROM accounts WHERE owner_id = %s LIMIT 1;",
                    (user["id"],),
                )
                acc = cur.fetchone()
                if acc:
                    account_id = acc["id"]

            token = create_access_token(user["id"], user["email"], user["role"])
            user_resp = UserResponse(
                id=user["id"],
                email=user["email"],
                role=user["role"],
                created_at=user["created_at"],
                account_id=account_id,
            )
            return AuthResponse(access_token=token, user=user_resp)

@router.get("/me", response_model=UserResponse)
def me(current_user: dict = Depends(get_current_user)):
    """Returns the authenticated profile."""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        role=current_user["role"],
        created_at=current_user["created_at"],
    )

# Role-verification endpoints for tests and auditors
@router.get("/admin-only")
def admin_only(user: dict = Depends(require_role("admin"))):
    return {"message": "Admin authorization verified", "user": user["email"]}

@router.get("/auditor-only")
def auditor_only(user: dict = Depends(require_role("auditor", "admin"))):
    return {"message": "Auditor authorization verified", "user": user["email"]}

@router.get("/holder-only")
def holder_only(user: dict = Depends(require_role("holder"))):
    return {"message": "Holder authorization verified", "user": user["email"]}
