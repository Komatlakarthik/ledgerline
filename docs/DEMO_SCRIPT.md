# 5-Minute Video Demo Script: LedgerLine 💸

This script outlines the exact sequence, narrative points, and commands to present in your **5-minute evaluation video**.

---

## ⏱️ Video Timing Breakdown

| Timestamp | Section | Key Demonstration |
|---|---|---|
| **0:00 - 0:30** | **1. Core Invariant** | Explain integer paise arithmetic, net-zero double-entry balance conservation against `EXTERNAL`, and zero negative-balance tolerance. |
| **0:30 - 2:00** | **2. Money Operations & Statements** | Log in as Holder; execute a deposit (+₹50), transfer (₹20), and an overdraft attempt (₹10,000,000); fetch statement showing posted entries and committed `REFUSED` row with `balance_seen`. |
| **2:00 - 3:00** | **3. Strict Idempotency & Replay** | Replay a deposit request with identical `Idempotency-Key` showing exact cached response; mutate amount under same key showing immediate `422 Unprocessable Entity`. |
| **3:00 - 4:00** | **4. High Concurrency Race Attack** | Run `scripts/attack.py` (Test 1) showing 20 concurrent threads racing to withdraw ₹30 against ₹100; exactly 3 post, 17 refused, zero negative balance. |
| **4:00 - 5:00** | **5. Tamper Resistance & Reconciliation** | Attempt `DELETE FROM ledger_entries` failing via database privilege and trigger; log in as Auditor and call `/reconciliation` proving global balance sum is strictly zero. |

---

## 🎬 Section-by-Section Talking Points & Terminal Commands

### 1. The Core Invariant (0:00 - 0:30)
* **What to say:**
  > "Hello, my name is Karthik. This is LedgerLine, a provable double-entry ledger engine built with FastAPI and raw SQL on PostgreSQL. 
  > In financial systems, integrity is non-negotiable. LedgerLine guarantees three fundamental invariants:
  > First, all currency calculations use 64-bit integer paise to eliminate floating-point rounding errors.
  > Second, every deposit and withdrawal is double-entry against a system `EXTERNAL` account, ensuring the sum of all balances across the system is strictly zero at all times.
  > Third, user balances have absolute zero negative-balance tolerance, enforced both in code and by PostgreSQL check constraints."

---

### 2. Money Operations & Statements (0:30 - 2:00)
* **What to show (Swagger UI or Curl):**
  Open `https://ledgerline-api-2kf3.onrender.com/docs` or terminal.
1. **Login as Holder:**
   - `POST /auth/login` with `holder@ledgerline.test` / `DemoPassword123!`
2. **Execute Deposit:**
   - `POST /deposits` -> `{"account_id": <id>, "amount_paise": 5000}` with `Idempotency-Key: dep-1`
   - Point out: Status `201 Created`, balance increases by ₹50.
3. **Execute Overdraft Withdrawal:**
   - `POST /withdrawals` -> `{"account_id": <id>, "amount_paise": 1000000000}` with `Idempotency-Key: wd-overdraw`
   - Point out: Status `409 Conflict`, `{"status": "refused", "reason": "insufficient_funds"}`.
4. **Fetch Statement:**
   - `GET /accounts/{id}/statement`
   - Point out:
     > "Notice how our refusal didn't roll back into oblivion—it committed permanently as a REFUSED transaction row. The holder can see the exact timestamp, the reason 'insufficient_funds', and the balance seen at that exact instant."

---

### 3. Strict Idempotency & Replay Defense (2:00 - 3:00)
* **What to show:**
1. **Replay Same Key:**
   - Resend the exact same request `POST /deposits` with `Idempotency-Key: dep-1`.
   - Point out:
     > "When a network drop causes a client retry, LedgerLine resolves the existing idempotency key atomically. It returns the exact same 201 response and transaction ID without double-crediting the account."
2. **Mutate Payload on Existing Key:**
   - Send `POST /deposits` with `Idempotency-Key: dep-1` but change amount to `99999`.
   - Point out:
     > "If an attacker or buggy client modifies the payload under an existing key, our SHA-256 request fingerprint detects the mutation and immediately rejects it with 422 Unprocessable Entity."

---

### 4. High-Concurrency Race Attack (3:00 - 4:00)
* **What to show:**
  Run `scripts/attack.py` in your terminal:
  ```bash
  python scripts/attack.py --url https://ledgerline-api-2kf3.onrender.com
  ```
* **What to say while it runs:**
  > "Here we run our adversarial penetration suite against the live Render deployment. 
  > In Test 1, we seed an account with ₹100 (10,000 paise) and fire 20 concurrent threads trying to withdraw ₹30 (3,000 paise) each. Total requested is ₹600.
  > Under `SELECT ... FOR UPDATE` with row-lock ordering, race conditions are mathematically eliminated: exactly 3 withdrawals succeed (9,000 paise), 17 are refused with 409 Conflict, and the final balance is exactly ₹10 (1,000 paise). Zero negative balance."

---

### 5. Tamper Resistance & Double-Entry Reconciliation (4:00 - 5:00)
* **What to show:**
1. **Direct Database Tampering:**
   - Show Test 6 in `attack.py` or terminal executing `DELETE FROM ledger_entries;` as `ledgerline_app`:
   - Point out:
     > "Even if an attacker gains SQL execution via application compromise, our least-privilege DB role `ledgerline_app` has zero DELETE, UPDATE, or TRUNCATE permissions on ledger tables. Furthermore, our append-only triggers and deferred balance-matching trigger block any unbacked balance edits at commit."
2. **Global Reconciliation Invariant:**
   - Log in as `auditor@ledgerline.test`.
   - Call `GET /reconciliation`.
   - Show the JSON response:
     ```json
     {
       "ok": true,
       "total_of_all_balances_paise": 0,
       "mismatched_accounts": []
     }
     ```
   - Conclude:
     > "The auditor endpoint proves that the entire system balances out to absolute zero (`total_of_all_balances_paise: 0`), and every account balance matches its ledger sum. 
     > LedgerLine is fully tested, fully deployed on Render, and ready for production evaluation. Thank you!"
