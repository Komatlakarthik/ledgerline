import os, threading, uuid
from dotenv import load_dotenv
load_dotenv()
import pytest, psycopg
from psycopg.rows import dict_row

TEST_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_URL:
    pytest.exit("Set TEST_DATABASE_URL (a DB separate from the deployed one)", 2)
if TEST_URL == os.environ.get("DATABASE_URL"):
    pytest.exit("TEST_DATABASE_URL must differ from DATABASE_URL", 2)

APP_URL = os.environ.get("TEST_APP_DATABASE_URL")
if not APP_URL:
    pytest.exit("Set TEST_APP_DATABASE_URL (the restricted ledgerline_app login)", 2)

os.environ["DATABASE_URL"] = APP_URL
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret")

from fastapi import HTTPException
from app import ledger


def connect():
    return psycopg.connect(TEST_URL, row_factory=dict_row)


def balance(acct_id):
    with connect() as c:
        return c.execute("SELECT balance_paise b FROM accounts WHERE id=%s", (acct_id,)).fetchone()["b"]


def new_user(role="holder"):
    with connect() as c:
        return c.execute("INSERT INTO users (email,password_hash,role) VALUES (%s,'x',%s) RETURNING id",
                         (f"{uuid.uuid4().hex}@t.test", role)).fetchone()["id"]


def new_account(owner_id, balance=0):
    with connect() as c:
        acct = c.execute("INSERT INTO accounts (owner_id,name) VALUES (%s,'t') RETURNING id",
                         (owner_id,)).fetchone()["id"]
    if balance:
        assert run_op(owner_id, uuid.uuid4().hex, "deposit", None, acct, balance)[0] == 201
    return acct


def run_op(user_id, key, kind, from_id, to_id, amount):
    """Same shape as production: own connection, commit on success, rollback on exception."""
    try:
        with psycopg.connect(APP_URL, row_factory=dict_row) as c:
            return ledger.execute(c, user_id, key, kind, from_id, to_id, amount)
    except HTTPException as e:
        return e.status_code, None


def race(fns):
    """Run callables at the same instant (barrier), return results or exceptions."""
    barrier = threading.Barrier(len(fns))
    out = [None] * len(fns)

    def worker(i, f):
        barrier.wait()
        try:
            out[i] = f()
        except Exception as e:                       # noqa: BLE001
            out[i] = e
    ts = [threading.Thread(target=worker, args=(i, f)) for i, f in enumerate(fns)]
    [t.start() for t in ts]
    [t.join(timeout=60) for t in ts]
    return out


def assert_books_balance():
    with connect() as c:
        total = c.execute("SELECT COALESCE(SUM(balance_paise),0) s FROM accounts").fetchone()["s"]
        assert total == 0, f"money created/lost: {total}"
        bad = c.execute(
            "SELECT a.id FROM accounts a LEFT JOIN (SELECT account_id, SUM(amount_paise) s "
            "FROM ledger_entries GROUP BY account_id) l ON l.account_id=a.id "
            "WHERE a.balance_paise <> COALESCE(l.s,0)").fetchall()
        assert not bad, f"balance != ledger sum for {bad}"
