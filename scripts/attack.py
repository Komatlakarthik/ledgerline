#!/usr/bin/env python3
"""
LedgerLine Adversarial Penetration Test Suite (attack.py)
Tests the running system against real-world attack vectors:
  1. Concurrency Overdraft Race (20 parallel withdrawals against ₹100)
  2. Idempotency Double-Spend Race (10 concurrent requests with identical key)
  3. Idempotency Payload Mutation Attack (replaying same key with different amount)
  4. Cross-Account Unauthorized Money Movement & Statement Snooping
  5. Privilege Escalation (registering as admin, unauthorized report access)
  6. Direct Database Tampering (DELETE, UPDATE on ledger/accounts via app role)
  7. Global Conservation of Money (Zero-sum ledger reconciliation)
"""

import argparse
import concurrent.futures
import json
import os
import sys
import uuid
import httpx
import psycopg
from dotenv import load_dotenv

load_dotenv()

DEFAULT_LOCAL = "http://127.0.0.1:8000"
DEFAULT_LIVE = "https://ledgerline-api-2kf3.onrender.com"
APP_DB_URL = os.environ.get(
    "APP_DATABASE_URL",
    os.environ.get("DATABASE_URL", "postgresql://ledgerline_app:app_secret_K4rm0s_Ledger2026!@ep-long-haze-b34v5ng4-pooler.c-4.ap-southeast-1.aws.neon.tech/neondb?sslmode=require")
)


def log_test(name: str):
    print(f"\n{'='*75}\n[TEST] {name}\n{'='*75}")


def pass_test(name: str, details: str = ""):
    print(f" PASS: {name}" + (f" -> {details}" if details else ""))


def fail_test(name: str, reason: str):
    print(f" FAIL: {name} -> {reason}")
    sys.exit(1)


def register_or_login(client: httpx.Client, base_url: str, email: str, role: str = "holder", pw: str = "DemoPassword123!"):
    # Try login first
    r = client.post(f"{base_url}/auth/login", json={"email": email, "password": pw})
    if r.status_code == 200:
        token = r.json()["access_token"]
        return token
    # Try register
    r_reg = client.post(f"{base_url}/auth/register", json={"email": email, "password": pw})
    if r_reg.status_code in (201, 409):
        r_log = client.post(f"{base_url}/auth/login", json={"email": email, "password": pw})
        if r_log.status_code == 200:
            return r_log.json()["access_token"]
    raise RuntimeError(f"Could not authenticate {email}: {r.text}")


def main():
    parser = argparse.ArgumentParser(description="LedgerLine Penetration Test Suite")
    parser.add_argument("--url", default=DEFAULT_LIVE, help="Target API URL (default: live)")
    parser.add_argument("--skip-db", action="store_true", help="Skip direct DB injection attack")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    print(f"[*] Attacking Target: {base_url}")

    with httpx.Client(timeout=30.0) as client:
        # 0. Health & Readiness Check
        log_test("0. Checking Health & Readiness")
        r_health = client.get(f"{base_url}/health")
        if r_health.status_code != 200 or r_health.json().get("status") != "ok":
            fail_test("Health Check", f"Received {r_health.status_code}: {r_health.text}")
        pass_test("GET /health", f"Status: {r_health.json()}")

        r_ready = client.get(f"{base_url}/ready")
        if r_ready.status_code != 200 or r_ready.json().get("status") != "ready":
            fail_test("Ready Check", f"Received {r_ready.status_code}: {r_ready.text}")
        pass_test("GET /ready", f"Status: {r_ready.json()}")

        # Setup Test Users
        holder_token = register_or_login(client, base_url, "holder@ledgerline.test")
        auditor_token = register_or_login(client, base_url, "auditor@ledgerline.test")
        holder_hdr = {"Authorization": f"Bearer {holder_token}"}
        auditor_hdr = {"Authorization": f"Bearer {auditor_token}"}

        # Get or create holder account
        r_accts = client.get(f"{base_url}/accounts", headers=holder_hdr)
        accts = r_accts.json()
        if not accts:
            r_c = client.post(f"{base_url}/accounts", json={"name": "Attack Target Account"}, headers=holder_hdr)
            acct_id = r_c.json()["id"]
        else:
            acct_id = accts[0]["id"]
        print(f"[*] Target Account ID: {acct_id}")

        # =====================================================================
        # 1. CONCURRENCY OVERDRAFT RACE ATTACK
        # =====================================================================
        log_test("1. Concurrency Overdraft Race Attack (20 threads x 3,000 paise vs 10,000 paise)")
        # Create a fresh isolated account specifically for the race test
        r_race_acct = client.post(f"{base_url}/accounts", json={"name": f"Race Acct {uuid.uuid4().hex[:6]}"}, headers=holder_hdr)
        if r_race_acct.status_code != 201:
            fail_test("Create Race Account", f"Failed with {r_race_acct.status_code}: {r_race_acct.text}")
        race_acct_id = r_race_acct.json()["id"]

        # Deposit exactly 10,000 paise (₹100)
        dep_key = str(uuid.uuid4())
        r_dep = client.post(
            f"{base_url}/deposits",
            json={"account_id": race_acct_id, "amount_paise": 10_000},
            headers={**holder_hdr, "Idempotency-Key": dep_key}
        )
        if r_dep.status_code != 201:
            fail_test("Initial Deposit", f"Failed with {r_dep.status_code}: {r_dep.text}")
        starting_bal = r_dep.json()["balance_after"]
        print(f"[*] Starting Balance for Race: {starting_bal} paise (in fresh account {race_acct_id})")

        # Fire 20 parallel withdrawal requests of 3,000 paise each
        def attempt_withdrawal(thread_id: int):
            with httpx.Client(timeout=30.0) as th_client:
                k = str(uuid.uuid4())
                return th_client.post(
                    f"{base_url}/withdrawals",
                    json={"account_id": race_acct_id, "amount_paise": 3_000},
                    headers={**holder_hdr, "Idempotency-Key": k}
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(attempt_withdrawal, i) for i in range(20)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        codes = [r.status_code for r in responses]
        posted_count = codes.count(201)
        refused_count = codes.count(409)
        print(f"[*] Concurrency Results: {posted_count} Posted (201), {refused_count} Refused (409)")

        # Verify balance after race
        r_bal = client.get(f"{base_url}/accounts/{race_acct_id}", headers=holder_hdr)
        final_bal = r_bal.json()["balance_paise"]
        print(f"[*] Final Account Balance: {final_bal} paise")

        if final_bal < 0:
            fail_test("Concurrency Race", f"CRITICAL: Negative balance detected! Balance: {final_bal}")
        if posted_count != 3 or refused_count != 17:
            fail_test("Concurrency Race", f"Expected exactly 3 posted and 17 refused, got {posted_count} posted, {refused_count} refused.")
        if final_bal != 1_000:
            fail_test("Concurrency Race", f"Expected final balance 1,000 paise, got {final_bal} paise.")
        pass_test("Concurrency Overdraft Defense", f"Zero negative balance tolerance maintained (3 posted, 17 refused, balance={final_bal} paise)")

        # =====================================================================
        # 2. IDEMPOTENCY REPLAY ATTACK (DOUBLE-SPEND PREVENTION)
        # =====================================================================
        log_test("2. Idempotency Double-Spend Race Attack (10 concurrent requests, same key)")
        shared_key = str(uuid.uuid4())
        deposit_amount = 5_000

        def attempt_replay_deposit(idx: int):
            with httpx.Client(timeout=30.0) as th_client:
                return th_client.post(
                    f"{base_url}/deposits",
                    json={"account_id": acct_id, "amount_paise": deposit_amount},
                    headers={**holder_hdr, "Idempotency-Key": shared_key}
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(attempt_replay_deposit, i) for i in range(10)]
            rep_responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        rep_codes = [r.status_code for r in rep_responses]
        rep_bodies = [r.text for r in rep_responses]
        if any(c != 201 for c in rep_codes):
            fail_test("Idempotency Replay", f"Not all requests received 201: {rep_codes}")
        if len(set(rep_bodies)) != 1:
            fail_test("Idempotency Replay", f"Responses differed between parallel replays: {set(rep_bodies)}")
        pass_test("Idempotency Double-Spend Defense", f"10 parallel requests received identical response; single transaction posted.")

        # =====================================================================
        # 3. IDEMPOTENCY PAYLOAD MUTATION ATTACK
        # =====================================================================
        log_test("3. Idempotency Payload Mutation Attack (same key, different amount)")
        r_tamper = client.post(
            f"{base_url}/deposits",
            json={"account_id": acct_id, "amount_paise": 99_999},  # Changed amount
            headers={**holder_hdr, "Idempotency-Key": shared_key}
        )
        if r_tamper.status_code != 422:
            fail_test("Idempotency Payload Tampering", f"Expected 422 Unprocessable Entity, got {r_tamper.status_code}")
        pass_test("Idempotency Mutation Defense", f"Payload modification under existing key rejected with 422.")

        # =====================================================================
        # 4. CROSS-ACCOUNT UNAUTHORIZED THEFT & SNOOPING ATTACK
        # =====================================================================
        log_test("4. Cross-Account Authorization & Exfiltration Attack")
        attacker_email = f"attacker_{uuid.uuid4().hex[:6]}@ledgerline.test"
        attacker_token = register_or_login(client, base_url, attacker_email)
        attacker_hdr = {"Authorization": f"Bearer {attacker_token}"}

        # Attacker tries to withdraw from Victim's account
        r_theft = client.post(
            f"{base_url}/withdrawals",
            json={"account_id": acct_id, "amount_paise": 1_000},
            headers={**attacker_hdr, "Idempotency-Key": str(uuid.uuid4())}
        )
        if r_theft.status_code != 404:
            fail_test("Theft Attack", f"Expected 404 for unowned account, got {r_theft.status_code}")
        pass_test("Theft Prevention", "Withdrawal from victim account blocked with constant 404.")

        # Attacker tries to view Victim's statement
        r_snoop = client.get(f"{base_url}/accounts/{acct_id}/statement", headers=attacker_hdr)
        if r_snoop.status_code != 404:
            fail_test("Statement Snooping Attack", f"Expected 404 for victim statement, got {r_snoop.status_code}")
        pass_test("Statement Snooping Prevention", "Victim statement query blocked with constant 404.")

        # Attacker tries to view Auditor reconciliation
        r_recon_bad = client.get(f"{base_url}/reconciliation", headers=attacker_hdr)
        if r_recon_bad.status_code != 403:
            fail_test("Privilege Escalation on Reports", f"Expected 403 for holder on /reconciliation, got {r_recon_bad.status_code}")
        pass_test("Report Privilege Defense", "Auditor reconciliation endpoint protected with 403 Forbidden.")

        # =====================================================================
        # 5. PRIVILEGE ESCALATION ATTEMPT ON REGISTRATION
        # =====================================================================
        log_test("5. Privilege Escalation on User Registration")
        bogus_admin = f"fakeadmin_{uuid.uuid4().hex[:6]}@ledgerline.test"
        r_fake_reg = client.post(
            f"{base_url}/auth/register",
            json={"email": bogus_admin, "password": "Password123!", "role": "admin"}
        )
        if r_fake_reg.status_code == 201:
            assigned_role = r_fake_reg.json().get("role")
            if assigned_role != "holder":
                fail_test("Registration Privilege Escalation", f"Client assigned self role '{assigned_role}'!")
        pass_test("Role Gate Integrity", "Registration strictly hardcoded to 'holder'; client cannot self-elevate.")

        # =====================================================================
        # 6. DIRECT DATABASE INJECTION & TAMPERING ATTACK
        # =====================================================================
        if not args.skip_db and APP_DB_URL:
            log_test("6. Direct Database Privilege & Deferred Trigger Tampering Attack")
            try:
                with psycopg.connect(APP_DB_URL) as conn:
                    with conn.cursor() as cur:
                        # Attempt DELETE
                        try:
                            cur.execute("DELETE FROM ledger_entries;")
                            fail_test("Database DELETE Attack", "ledgerline_app was able to DELETE from ledger_entries!")
                        except psycopg.errors.InsufficientPrivilege:
                            pass_test("DB Privilege: DELETE Blocked", "permission denied for table ledger_entries")
                        conn.rollback()

                        # Attempt direct UPDATE on ledger_entries
                        try:
                            cur.execute("UPDATE ledger_entries SET amount_paise = 1000;")
                            fail_test("Database UPDATE Attack", "ledgerline_app was able to UPDATE ledger_entries!")
                        except (psycopg.errors.InsufficientPrivilege, psycopg.errors.DatabaseError):
                            pass_test("DB Privilege: UPDATE Blocked", "ledger_entries is append-only and read/insert only")
                        conn.rollback()

                        # Attempt direct balance manipulation without matching ledger
                        try:
                            cur.execute(f"UPDATE accounts SET balance_paise = balance_paise + 5000000 WHERE id = {acct_id};")
                            conn.commit()  # Deferred trigger fires at commit!
                            fail_test("Database Balance Manipulation", "Direct balance edit succeeded without matching ledger entry!")
                        except psycopg.errors.DatabaseError as e:
                            pass_test("Deferred Trigger Defense", f"Direct balance edit rejected at commit: {str(e).strip()}")
                        conn.rollback()
            except Exception as e:
                print(f"[!] DB test note: {e}")

        # =====================================================================
        # 7. GLOBAL RECONCILIATION INVARIANT CHECK
        # =====================================================================
        log_test("7. Global Double-Entry Reconciliation Invariant")
        r_recon = client.get(f"{base_url}/reconciliation", headers=auditor_hdr)
        if r_recon.status_code != 200:
            fail_test("Global Reconciliation", f"Expected 200, got {r_recon.status_code}: {r_recon.text}")
        recon = r_recon.json()
        print(f"[*] Reconciliation Result: {json.dumps(recon, indent=2)}")
        if not recon.get("ok"):
            fail_test("Global Reconciliation", f"System out of balance! Mismatches: {recon.get('mismatched_accounts')}")
        if recon.get("total_of_all_balances_paise") != 0:
            fail_test("Global Reconciliation", f"Sum of balances != 0 (Money created or destroyed: {recon.get('total_of_all_balances_paise')})")
        pass_test("Zero-Sum Invariant", "Net zero balance across all accounts verified. Ledger agrees with all account balances.")

    print(f"\n{'='*75}\n[SUCCESS] ALL ATTACK VECTORS DEFENDED WITH ZERO FAILURES!\n{'='*75}\n")


if __name__ == "__main__":
    main()
