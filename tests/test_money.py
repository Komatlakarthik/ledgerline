import uuid
from .conftest import new_user, new_account, run_op, race, connect, assert_books_balance


def test_concurrent_withdrawals_cannot_overdraw():
    u = new_user()
    a = new_account(u, balance=10_000)                      # Rs 100
    res = race([lambda: run_op(u, uuid.uuid4().hex, "withdrawal", a, None, 3_000)
                for _ in range(20)])                        # 20 x Rs 30 against Rs 100
    assert all(isinstance(r, tuple) for r in res), res      # no crashes/deadlocks
    assert sum(r[0] == 201 for r in res) == 3
    assert sum(r[0] == 409 for r in res) == 17
    with connect() as c:
        assert c.execute("SELECT balance_paise b FROM accounts WHERE id=%s", (a,)).fetchone()["b"] == 1_000
    assert_books_balance()


def test_opposing_transfers_do_not_deadlock():
    u1, u2 = new_user(), new_user()
    a, b = new_account(u1, 100_000), new_account(u2, 100_000)
    fns = [lambda: run_op(u1, uuid.uuid4().hex, "transfer", a, b, 100) for _ in range(10)] + \
          [lambda: run_op(u2, uuid.uuid4().hex, "transfer", b, a, 100) for _ in range(10)]
    res = race(fns)
    assert all(isinstance(r, tuple) and r[0] == 201 for r in res), res
    assert_books_balance()


def test_same_key_concurrently_posts_once():
    u = new_user()
    a = new_account(u)
    key = uuid.uuid4().hex
    res = race([lambda: run_op(u, key, "deposit", None, a, 5_000) for _ in range(10)])
    assert all(isinstance(r, tuple) for r in res), res
    assert len({(r[0], str(r[1])) for r in res}) == 1       # everyone got the SAME answer
    with connect() as c:
        n = c.execute("SELECT count(*) n FROM transactions WHERE initiated_by=%s AND kind='deposit'",
                      (u,)).fetchone()["n"]
        bal = c.execute("SELECT balance_paise b FROM accounts WHERE id=%s", (a,)).fetchone()["b"]
    assert n == 1 and bal == 5_000
    assert_books_balance()
