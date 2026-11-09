import random, uuid
import psycopg, pytest
from fastapi.testclient import TestClient
from app.main import app
from app.security import make_token
from .conftest import (TEST_URL, APP_URL, new_user, new_account, run_op, race, connect,
                       balance, assert_books_balance)

client = TestClient(app)
def k(): return uuid.uuid4().hex
def hdr(uid): return {"Authorization": f"Bearer {make_token(uid)}", "Idempotency-Key": k()}


def test_replayed_refusal_stays_refused_after_deposit():
    u = new_user(); a = new_account(u, 1_000)
    key = k()
    first = run_op(u, key, "withdrawal", a, None, 5_000)
    assert first[0] == 409
    assert run_op(u, k(), "deposit", None, a, 100_000)[0] == 201
    assert run_op(u, key, "withdrawal", a, None, 5_000) == first      # same answer, no money moved
    assert balance(a) == 101_000


def test_same_key_different_body_is_422_and_moves_nothing():
    u = new_user(); a = new_account(u); key = k()
    assert run_op(u, key, "deposit", None, a, 100)[0] == 201
    assert run_op(u, key, "deposit", None, a, 200)[0] == 422
    assert balance(a) == 100


def test_cannot_move_someone_elses_money_and_it_is_audited():
    victim, attacker = new_user(), new_user()
    v = new_account(victim, 50_000); m = new_account(attacker)
    results = [run_op(attacker, k(), "withdrawal", v, None, 1_000),
               run_op(attacker, k(), "transfer", v, m, 1_000),
               run_op(attacker, k(), "deposit", None, v, 1_000),
               run_op(attacker, k(), "withdrawal", 10**12, None, 1_000)]   # nonexistent account
    assert [r[0] for r in results] == [404, 404, 404, 404]                 # identical answers
    assert balance(v) == 50_000 and balance(m) == 0
    with connect() as c:
        n = c.execute("SELECT count(*) n FROM audit_logs WHERE user_id=%s", (attacker,)).fetchone()["n"]
    assert n == 4
    assert_books_balance()


@pytest.mark.parametrize("role", ["admin", "auditor"])
def test_admin_and_auditor_cannot_move_money(role):
    holder = new_user(); a = new_account(holder, 10_000); b = new_account(holder)
    u = new_user(role)
    for path, body in [("/deposits", {"account_id": a, "amount_paise": 100}),
                       ("/withdrawals", {"account_id": a, "amount_paise": 100}),
                       ("/transfers", {"from_account_id": a, "to_account_id": b, "amount_paise": 100})]:
        assert client.post(path, json=body, headers=hdr(u)).status_code == 403
    assert balance(a) == 10_000


def test_holder_cannot_read_another_holders_statement():
    h1, h2, aud = new_user(), new_user(), new_user("auditor")
    a = new_account(h1, 1_000)
    assert client.get(f"/accounts/{a}/statement", headers=hdr(h2)).status_code == 404
    assert client.get(f"/accounts/{a}/statement", headers=hdr(aud)).status_code == 200


@pytest.mark.parametrize("amt", [0, -5, 10.5, "100", 10**12, None])
def test_bad_amounts_rejected(amt):
    u = new_user(); a = new_account(u, 1_000)
    r = client.post("/withdrawals", json={"account_id": a, "amount_paise": amt}, headers=hdr(u))
    assert r.status_code == 422 and balance(a) == 1_000


def test_self_transfer_and_missing_idempotency_key_rejected():
    u = new_user(); a = new_account(u, 1_000)
    h = hdr(u)
    assert client.post("/transfers", json={"from_account_id": a, "to_account_id": a,
                       "amount_paise": 10}, headers=h).status_code == 422
    no_key = {"Authorization": h["Authorization"]}
    assert client.post("/deposits", json={"account_id": a, "amount_paise": 10},
                       headers=no_key).status_code == 422


@pytest.mark.parametrize("sql", ["UPDATE ledger_entries SET amount_paise=1", "DELETE FROM ledger_entries",
                                 "TRUNCATE ledger_entries", "UPDATE transactions SET amount_paise=1",
                                 "DELETE FROM transactions", "UPDATE audit_logs SET action='x'",
                                 "DELETE FROM audit_logs"])
@pytest.mark.parametrize("url", [TEST_URL, APP_URL])      # owner: triggers; app role: privileges
def test_ledger_and_audit_cannot_be_tampered(sql, url):
    u = new_user(); new_account(u, 1_000)
    with pytest.raises(psycopg.errors.DatabaseError):
        with psycopg.connect(url) as c:
            c.execute(sql)
    assert_books_balance()


def test_app_role_has_no_dangerous_privileges():
    with connect() as c:
        for t in ("ledger_entries", "transactions", "audit_logs"):
            for p in ("UPDATE", "DELETE", "TRUNCATE"):
                ok = c.execute("SELECT has_table_privilege('ledgerline_app', %s, %s) ok", (t, p)).fetchone()["ok"]
                assert not ok, f"app role can {p} {t}"
        for t in ("accounts", "users", "idempotency_keys"):
            assert not c.execute("SELECT has_table_privilege('ledgerline_app', %s, 'DELETE') ok", (t,)).fetchone()["ok"]


def test_balance_cannot_be_edited_directly():
    u = new_user(); a = new_account(u, 1_000)
    with pytest.raises(psycopg.errors.DatabaseError):
        with psycopg.connect(APP_URL) as c:                # raises at COMMIT (deferred trigger)
            c.execute("UPDATE accounts SET balance_paise = balance_paise + 1000000 WHERE id=%s", (a,))
    assert balance(a) == 1_000


def test_random_concurrent_mix_conserves_money():
    users = [new_user() for _ in range(4)]
    accts = [new_account(u, 50_000) for u in users]
    rnd = random.Random(42)
    fns = []
    for _ in range(60):
        i = rnd.randrange(4)
        kind = rnd.choice(["deposit", "withdrawal", "transfer"])
        amt = rnd.randrange(100, 40_000)
        j = rnd.choice([x for x in range(4) if x != i])
        src, dst = {"deposit": (None, accts[i]), "withdrawal": (accts[i], None),
                    "transfer": (accts[i], accts[j])}[kind]
        # default args freeze the loop variables, otherwise every lambda runs the LAST iteration
        fns.append(lambda u=users[i], kd=kind, s=src, d=dst, am=amt: run_op(u, k(), kd, s, d, am))
    res = race(fns)
    assert all(isinstance(r, tuple) and r[0] in (201, 409) for r in res), res
    assert all(balance(a) >= 0 for a in accts)
    assert_books_balance()
