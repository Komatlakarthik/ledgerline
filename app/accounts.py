import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from .db import get_conn
from .deps import current_user, require_roles

router = APIRouter(prefix="/accounts", tags=["accounts"])


class NewAccount(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    owner_id: int | None = None          # admin only


@router.post("", status_code=201)
def create_account(body: NewAccount, user=Depends(require_roles("holder", "admin")),
                   conn=Depends(get_conn)):
    if user["role"] == "holder":
        if body.owner_id not in (None, user["id"]):
            raise HTTPException(403, "Forbidden")
        owner = user["id"]
    else:
        if body.owner_id is None:
            raise HTTPException(422, "owner_id required")
        owner = body.owner_id
    try:
        return conn.execute(
            "INSERT INTO accounts (owner_id, name) VALUES (%s,%s) "
            "RETURNING id, owner_id, name, balance_paise", (owner, body.name)).fetchone()
    except psycopg.errors.ForeignKeyViolation:
        raise HTTPException(404, "Owner not found")


@router.get("")
def list_accounts(user=Depends(current_user), conn=Depends(get_conn)):
    if user["role"] in ("admin", "auditor"):
        return conn.execute("SELECT id, owner_id, name, balance_paise FROM accounts ORDER BY id").fetchall()
    return conn.execute("SELECT id, owner_id, name, balance_paise FROM accounts "
                        "WHERE owner_id=%s ORDER BY id", (user["id"],)).fetchall()


@router.get("/{account_id}")
def get_account(account_id: int, user=Depends(current_user), conn=Depends(get_conn)):
    row = conn.execute("SELECT id, owner_id, name, balance_paise FROM accounts WHERE id=%s",
                       (account_id,)).fetchone()
    if row is None or (user["role"] == "holder" and row["owner_id"] != user["id"]):
        raise HTTPException(404, "Account not found")
    return row
