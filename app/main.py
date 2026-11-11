from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import psycopg
from .auth import router as auth_router
from .accounts import router as accounts_router
from .money import router as money_router
from .reports import router as reports_router
from .deps import current_user, require_roles
from .config import DATABASE_URL

app = FastAPI(title="LedgerLine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(money_router)
app.include_router(reports_router)

@app.get("/")
def root():
    return {"message": "LedgerLine API is running. See /docs for API documentation and /health for system status."}

@app.get("/health")
def health():
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return {"status": "ok", "db": "connected"}
    except Exception as e:
        redacted = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL[:15]
        return {"status": "degraded", "db_error": str(e), "target": redacted}

@app.get("/ready")
def ready():
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM accounts LIMIT 1")
                return {"status": "ready", "db": "ready"}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}

@app.get("/me")
def me(user=Depends(current_user)):
    return user

@app.get("/admin/ping")
def admin_ping(user=Depends(require_roles("admin"))):
    return {"ok": True}
