import hashlib, json
from fastapi import HTTPException
from psycopg.types.json import Jsonb


def _hash(kind, from_id, to_id, amount):
    return hashlib.sha256(json.dumps([kind, from_id, to_id, amount]).encode()).hexdigest()


def _save(conn, user_id, key, status, body):
    row = conn.execute(
        "UPDATE idempotency_keys SET status_code=%s, response=%s WHERE user_id=%s AND key=%s RETURNING response",
        (status, Jsonb(body), user_id, key)).fetchone()
    return status, row["response"] if row else body


def execute(conn, user_id, key, kind, from_id, to_id, amount):
    """Run ONE money movement inside the caller's open transaction.
    from_id/to_id are account ids; for deposit/withdrawal pass None for the
    outside side. Returns (http_status, body). Raises HTTPException(404) when
    the caller may not use an account (caller's transaction then rolls back)."""
    h = _hash(kind, from_id, to_id, amount)

    # 1. Idempotency: the PRIMARY KEY (user_id, key) decides who goes first.
    #    A concurrent duplicate BLOCKS here until the first transaction ends.
    first = conn.execute(
        "INSERT INTO idempotency_keys (user_id, key, request_hash) VALUES (%s,%s,%s) "
        "ON CONFLICT (user_id, key) DO NOTHING RETURNING 1",
        (user_id, key, h)).fetchone()
    if first is None:
        prev = conn.execute(
            "SELECT request_hash, status_code, response FROM idempotency_keys "
            "WHERE user_id=%s AND key=%s", (user_id, key)).fetchone()
        if prev["request_hash"] != h:
            return 422, {"status": "error", "reason": "idempotency_key_reused_with_different_request"}
        return prev["status_code"], prev["response"]

    # 2. Authorisation: the account being debited (or deposited into) must be the caller's.
    external = conn.execute("SELECT id FROM accounts WHERE is_system").fetchone()["id"]
    src = from_id if from_id is not None else external
    dst = to_id if to_id is not None else external
    own = from_id if kind != "deposit" else to_id
    row = conn.execute("SELECT owner_id FROM accounts WHERE id=%s", (own,)).fetchone()
    if row is None or row["owner_id"] != user_id:
        raise HTTPException(404, "Account not found")          # same answer: missing or not yours
    if conn.execute("SELECT 1 FROM accounts WHERE id=%s", (dst,)).fetchone() is None:
        raise HTTPException(404, "Account not found")

    # 3. Lock both rows in ascending id order (prevents deadlock), THEN read balances.
    rows = conn.execute(
        "SELECT id, balance_paise FROM accounts WHERE id = ANY(%s) ORDER BY id FOR UPDATE",
        ([src, dst],)).fetchall()
    bal = {r["id"]: r["balance_paise"] for r in rows}

    # 4. Floor check, atomic with the debit because we hold the lock.
    if src != external and bal[src] < amount:
        conn.execute(
            "INSERT INTO transactions (kind,status,from_account_id,to_account_id,amount_paise,"
            "reason,balance_seen,initiated_by) VALUES (%s,'REFUSED',%s,%s,%s,'insufficient_funds',%s,%s)",
            (kind, src, dst, amount, bal[src], user_id))
        return _save(conn, user_id, key, 409, {"status": "refused", "reason": "insufficient_funds"})

    # 5. Post: one transaction row, two ledger entries (net zero), two balance updates.
    txn_id = conn.execute(
        "INSERT INTO transactions (kind,status,from_account_id,to_account_id,amount_paise,initiated_by) "
        "VALUES (%s,'POSTED',%s,%s,%s,%s) RETURNING id", (kind, src, dst, amount, user_id)).fetchone()["id"]
    after = {}
    for acct, delta in ((src, -amount), (dst, amount)):
        new = conn.execute(
            "UPDATE accounts SET balance_paise = balance_paise + %s WHERE id=%s RETURNING balance_paise",
            (delta, acct)).fetchone()["balance_paise"]
        conn.execute(
            "INSERT INTO ledger_entries (txn_id, account_id, amount_paise, balance_after) "
            "VALUES (%s,%s,%s,%s)", (txn_id, acct, delta, new))
        after[acct] = new
    return _save(conn, user_id, key, 201,
                 {"status": "posted", "transaction_id": txn_id, "amount_paise": amount,
                  "balance_after": after[own]})
