from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from app.routers.auth import router as auth_router
from app.db import get_db

app = FastAPI(
    title="LedgerLine API",
    description="Double-entry money movement engine with provable integrity and idempotency.",
    version="1.0.0",
)

# CORS configuration for web clients and evaluator scripts
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)

@app.get("/health", tags=["System"])
def health():
    """Health check endpoint that verifies DB connectivity."""
    db_status = "unreachable"
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                if cur.fetchone()[0] == 1:
                    db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "database": db_status,
        "service": "ledgerline-api",
    }
