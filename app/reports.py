from fastapi import APIRouter, Depends, Query
from .db import get_conn
from .deps import require_roles

router = APIRouter(tags=["reports"])


@router.get("/reconciliation")
def reconciliation(user=Depends(require_roles("admin", "auditor")), conn=Depends(get_conn)):
    total = conn.execute("SELECT COALESCE(SUM(balance_paise),0) AS s FROM accounts").fetchone()["s"]
    bad = conn.execute(
        "SELECT a.id, a.balance_paise, COALESCE(l.s,0) AS ledger_sum FROM accounts a "
        "LEFT JOIN (SELECT account_id, SUM(amount_paise) s FROM ledger_entries GROUP BY account_id) l "
        "ON l.account_id = a.id WHERE a.balance_paise <> COALESCE(l.s,0)").fetchall()
    return {"ok": total == 0 and not bad, "total_of_all_balances_paise": total,
            "mismatched_accounts": bad}


@router.get("/audit-logs")
def audit_logs(limit: int = Query(100, ge=1, le=500), user=Depends(require_roles("admin", "auditor")),
               conn=Depends(get_conn)):
    return conn.execute("SELECT id, user_id, action, detail, created_at FROM audit_logs "
                        "ORDER BY id DESC LIMIT %s", (limit,)).fetchall()
