from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from .auth import router as auth_router
from .deps import current_user, require_roles

app = FastAPI(title="LedgerLine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/me")
def me(user=Depends(current_user)):
    return user

@app.get("/admin/ping")
def admin_ping(user=Depends(require_roles("admin"))):
    return {"ok": True}
