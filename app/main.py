from fastapi import FastAPI

app = FastAPI(title="LedgerLine")

@app.get("/health")
def health():
    return {"status": "ok"}
