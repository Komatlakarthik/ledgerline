import httpx
import psycopg
import sys
import uuid

BASE_URL = "https://ledgerline-api-2kf3.onrender.com"
APP_DATABASE_URL = "postgresql://ledgerline_app:app_secret_K4rm0s_Ledger2026!@ep-long-haze-b34v5ng4-pooler.c-4.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

def run_live_verification():
    print(f"=== 1. Checking Root & Health on {BASE_URL} ===")
    r = httpx.get(f"{BASE_URL}/health", timeout=10.0)
    print("Health response:", r.status_code, r.json())
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": "connected"}

    print("\n=== 2. Login as Holder & Auditor ===")
    r_holder = httpx.post(f"{BASE_URL}/auth/login", json={"email": "holder@ledgerline.test", "password": "DemoPassword123!"}, timeout=10.0)
    assert r_holder.status_code == 200, f"Holder login failed: {r_holder.text}"
    holder_token = r_holder.json()["access_token"]
    holder_headers = {"Authorization": f"Bearer {holder_token}"}

    r_me = httpx.get(f"{BASE_URL}/me", headers=holder_headers, timeout=10.0)
    holder_user = r_me.json()
    print(f"Holder logged in: user_id={holder_user['id']}, role={holder_user['role']}")

    # Get or create account for holder
    r_accts = httpx.get(f"{BASE_URL}/accounts", headers=holder_headers, timeout=10.0)
    accounts = r_accts.json()
    if not accounts:
        r_create = httpx.post(f"{BASE_URL}/accounts", json={"name": "Holder Main Checking"}, headers=holder_headers, timeout=10.0)
        assert r_create.status_code == 201, f"Create account failed: {r_create.text}"
        account_id = r_create.json()["id"]
        print(f"Created new account for holder: id={account_id}")
    else:
        account_id = accounts[0]["id"]
        print(f"Using existing account for holder: id={account_id}")

    r_auditor = httpx.post(f"{BASE_URL}/auth/login", json={"email": "auditor@ledgerline.test", "password": "DemoPassword123!"}, timeout=10.0)
    assert r_auditor.status_code == 200, f"Auditor login failed: {r_auditor.text}"
    auditor_token = r_auditor.json()["access_token"]
    auditor_headers = {"Authorization": f"Bearer {auditor_token}"}
    print("Auditor logged in successfully.")

    print("\n=== 3. Deposit money to Holder account ===")
    dep_key = str(uuid.uuid4())
    r_dep = httpx.post(
        f"{BASE_URL}/deposits",
        json={"account_id": account_id, "amount_paise": 5000},
        headers={**holder_headers, "Idempotency-Key": dep_key},
        timeout=10.0
    )
    assert r_dep.status_code == 201, f"Deposit failed ({r_dep.status_code}): {r_dep.text}"
    print("Deposit result:", r_dep.json())

    print("\n=== 4. Trigger Overdraft Refusal ===")
    overdraw_key = str(uuid.uuid4())
    r_wd = httpx.post(
        f"{BASE_URL}/withdrawals",
        json={"account_id": account_id, "amount_paise": 1000000000},
        headers={**holder_headers, "Idempotency-Key": overdraw_key},
        timeout=10.0
    )
    print("Overdraft response code:", r_wd.status_code)
    print("Overdraft body:", r_wd.json())
    assert r_wd.status_code == 409, f"Expected 409, got {r_wd.status_code}"
    assert r_wd.json()["status"] == "refused"
    assert "insufficient_funds" in r_wd.json()["reason"]

    print("\n=== 5. Fetch Statement for Holder Account ===")
    r_stmt = httpx.get(f"{BASE_URL}/accounts/{account_id}/statement", headers=holder_headers, timeout=10.0)
    assert r_stmt.status_code == 200, f"Statement failed: {r_stmt.text}"
    stmt = r_stmt.json()
    print(f"Statement retrieved: total items={len(stmt)}")
    has_refused = any(item.get("status") == "REFUSED" for item in stmt)
    print(f"Statement contains refused row: {has_refused}")
    assert has_refused, "Statement did not contain the refused transaction!"
    for item in stmt:
        if item.get("status") == "REFUSED":
            print("Refused item details:", item)
            assert item["reason"] is not None
            assert item["balance_after"] is not None   # stores balance_seen
            break

    print("\n=== 6. Reconciliation Endpoint Permissions ===")
    r_recon_holder = httpx.get(f"{BASE_URL}/reconciliation", headers=holder_headers, timeout=10.0)
    print("Holder access to /reconciliation status:", r_recon_holder.status_code)
    assert r_recon_holder.status_code == 403, f"Expected 403 for holder on /reconciliation, got {r_recon_holder.status_code}"

    r_recon_auditor = httpx.get(f"{BASE_URL}/reconciliation", headers=auditor_headers, timeout=10.0)
    print("Auditor access to /reconciliation status:", r_recon_auditor.status_code)
    assert r_recon_auditor.status_code == 200, f"Expected 200 for auditor, got {r_recon_auditor.status_code}"
    recon_data = r_recon_auditor.json()
    print("Reconciliation response:", recon_data)
    assert recon_data["ok"] is True, f"Reconciliation returned ok=False: {recon_data}"
    assert recon_data["total_of_all_balances_paise"] == 0
    assert recon_data["mismatched_accounts"] == []

    print("\n=== 7. Direct Database Privilege Check (ledgerline_app) ===")
    with psycopg.connect(APP_DATABASE_URL) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("DELETE FROM ledger_entries;")
                print("SECURITY FAIL: ledgerline_app was able to DELETE from ledger_entries!")
                sys.exit(1)
            except psycopg.errors.InsufficientPrivilege as e:
                print("SUCCESS: InsufficientPrivilege caught as expected when ledgerline_app attempted DELETE:")
                print("  ", str(e).strip())

    print("\n>>> ALL DAY 3 LIVE VERIFICATIONS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    run_live_verification()
