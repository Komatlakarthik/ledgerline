from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from .db import get_conn
from .deps import require_roles
from . import ledger

router = APIRouter(tags=["money"])
MAX_PAISE = 1_000_000_000          # keep in sync with the DB CHECK
Amount = Field(gt=0, le=MAX_PAISE, strict=True)      # strict: rejects 10.5 and "10"
IdemKey = Header(alias="Idempotency-Key", min_length=8, max_length=128)


class Single(BaseModel):
    account_id: int
    amount_paise: int = Amount


class Transfer(BaseModel):
    from_account_id: int
    to_account_id: int
    amount_paise: int = Amount


def _respond(result):
    status, body = result
    return JSONResponse(status_code=status, content=body)


@router.post("/deposits")
def deposit(b: Single, key: str = IdemKey, user=Depends(require_roles("holder")),
            conn=Depends(get_conn)):
    return _respond(ledger.execute(conn, user["id"], key, "deposit", None, b.account_id, b.amount_paise))


@router.post("/withdrawals")
def withdraw(b: Single, key: str = IdemKey, user=Depends(require_roles("holder")),
             conn=Depends(get_conn)):
    return _respond(ledger.execute(conn, user["id"], key, "withdrawal", b.account_id, None, b.amount_paise))


@router.post("/transfers")
def transfer(b: Transfer, key: str = IdemKey, user=Depends(require_roles("holder")),
             conn=Depends(get_conn)):
    if b.from_account_id == b.to_account_id:
        raise HTTPException(422, "Cannot transfer to the same account")
    return _respond(ledger.execute(conn, user["id"], key, "transfer",
                                   b.from_account_id, b.to_account_id, b.amount_paise))
