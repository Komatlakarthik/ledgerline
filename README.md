# LedgerLine 💸

> **Double-entry financial ledger engine with provable integrity, raw SQL concurrency control, and zero negative-balance tolerance.**

Built for the **Snovasys Fresher Hiring Challenge 2026 (VVIT)**.

* **Live Deployment:** [https://ledgerline-api-2kf3.onrender.com](https://ledgerline-api-2kf3.onrender.com)
* **API Documentation:** [docs/API.md](docs/API.md) | [Swagger UI](https://ledgerline-api-2kf3.onrender.com/docs)
* **Threat Model:** [THREATS.md](THREATS.md)
* **AI Deficiencies & Log:** [PROMPTS.md](PROMPTS.md)

---

## 🔑 Demo Credentials

Throwaway credentials pre-seeded on the live deployment:

| Role | Email | Password | Primary Capabilities |
|---|---|---|---|
| **Holder** | `holder@ledgerline.test` | `DemoPassword123!` | Create own accounts, deposit, withdraw, transfer, view statements |
| **Auditor** | `auditor@ledgerline.test` | `DemoPassword123!` | Read-only global reconciliation (`/reconciliation`), system audit logs |
| **Admin** | `admin@ledgerline.test` | `DemoPassword123!` | Create accounts for any user, system health monitoring |

---

## 🏛️ The Invariant

1. **Integer Arithmetic:** All amounts and balances are stored as 64-bit integer paise (`1 INR = 100 paise`), entirely eliminating IEEE 754 floating-point rounding errors.
2. **Double-Entry Conservation of Money:** Every external deposit and withdrawal posts offsetting debit/credit entries against the system `EXTERNAL` account (Account ID 1). Across the entire database, the sum of all balances strictly equals zero at all times:
   $$\sum_{\text{all accounts}} \text{balance\_paise} = 0$$
3. **Zero Negative-Balance Tolerance:** User accounts can never go below zero, strictly guarded at the schema level:
   ```sql
   CHECK (is_system OR balance_paise >= 0)
   ```
4. **Append-Only Immutability:** Financial ledger entries and transactions are strictly append-only. Triggers prevent all `UPDATE`, `DELETE`, and `TRUNCATE` operations.
5. **Deferred Balance Verification:** An unbacked balance edit is physically impossible. At transaction `COMMIT`, a `DEFERRABLE INITIALLY DEFERRED` constraint trigger verifies that `balance_paise` matches the newest `ledger_entries.balance_after`.

---

## 🚀 Clean-Clone Setup Guide

To run LedgerLine locally or against a clean PostgreSQL instance:

### 1. Clone & Virtual Environment
```bash
git clone https://github.com/Komatlakarthik/ledgerline.git
cd ledgerline
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# On Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
Create `.env` in the project root:
```env
# Database owner connection string (used for schema migrations and admin operations)
DATABASE_URL=postgresql://neondb_owner:<owner_pw>@<host>/neondb?sslmode=require

# Isolated database for running pytest test suites (must differ from production)
TEST_DATABASE_URL=postgresql://neondb_owner:<owner_pw>@<host>/ledgerline_test?sslmode=require

# Restricted application role connection strings (least-privilege runtime role)
APP_DATABASE_URL=postgresql://ledgerline_app:<app_pw>@<host>/neondb?sslmode=require
TEST_APP_DATABASE_URL=postgresql://ledgerline_app:<app_pw>@<host>/ledgerline_test?sslmode=require

# Security Secrets
JWT_SECRET=your-random-64-character-hex-secret
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### 3. Run Migrations in Order (001 to 004)
Run migrations using PostgreSQL owner credentials:
```bash
# 001: Initial schema (users, accounts, EXTERNAL system account)
psql $DATABASE_URL -f db/schema.sql

# 002: Double-entry ledger, append-only triggers, idempotency keys
psql $DATABASE_URL -f db/002_ledger.sql

# 003: Audit logs, clock_timestamp(), deferred balance matching trigger
psql $DATABASE_URL -f db/003_audit_and_guards.sql

# 004: Create restricted ledgerline_app role with least privilege
psql $DATABASE_URL -v app_pw="app_secret_K4rm0s_Ledger2026!" -f db/004_app_role.sql
```
*(Repeat the migration steps for `$TEST_DATABASE_URL` so tests run on a clean mirror schema)*

### 4. Seed Seed-Users
```bash
python scripts/seed.py
```

### 5. Run the API Server
```bash
uvicorn app.main:app --reload --port 8000
```
- Health Check: `http://127.0.0.1:8000/health`
- Readiness Check: `http://127.0.0.1:8000/ready`
- Swagger UI Docs: `http://127.0.0.1:8000/docs`

### 6. Run Test Suite & Adversarial Attack Script
```bash
# Run complete test suite (38 automated tests)
pytest -v

# Run adversarial penetration attack suite against running instance
python scripts/attack.py --url http://127.0.0.1:8000
```

---

## 📝 Project Write-up & Evaluation Answers

### 1. What I Built
I built **LedgerLine**, an auditable, high-concurrency double-entry ledger API written in FastAPI, `psycopg` (v3), and raw SQL running against PostgreSQL. The core money engine (`app/ledger.py`) enforces strict double-entry accounting with an external system account, absolute zero-sum balance conservation, row-level ordered lock acquisitions to eliminate deadlocks, and atomic idempotency key resolution. All access control is verified per-request against the database, with append-only audit logging and least-privilege DB role isolation.

### 2. What I Deliberately Did Not Build, and Why
I deliberately omitted overdraft lines of credit, pending holds, transfer reversals, multi-currency conversion, and blockchain/hash-chain trees. In financial accounting, overdraft facilities and multi-currency exchange introduce subjective credit risk, float, and exchange rate drift that blur mathematical balance conservation. Transfer reversals are implemented purely as opposing forward transactions rather than mutating historical entries. Cryptographic hash-chains were skipped because PostgreSQL append-only triggers combined with restricted DB role permissions (`GRANT SELECT, INSERT`) provide ironclad non-repudiation and tampering protection with lower latency and higher throughput. Furthermore, the frontend UI was kept minimal to focus entirely on API penetration resistance, data integrity, and raw SQL transaction boundaries.

### 3. My Integrity and Concurrency Model, in My Own Words
My integrity model guarantees that not a single paisa can be created, destroyed, or overdrafted under arbitrary concurrency. When a money request arrives:
1. It validates authorization first; unowned accounts return `404 Not Found` to prevent account ID snooping.
2. An idempotency record is inserted atomically using `INSERT ... ON CONFLICT DO NOTHING`. If a duplicate request arrives concurrently, it yields and waits for the winning transaction's committed response.
3. Account rows are locked using `SELECT ... FOR UPDATE` ordered strictly by ID (`ORDER BY id`). Numerical ordering eliminates cycles in the lock graph, making deadlocks mathematically impossible.
4. The balance check and balance debit occur under this exclusive row lock. If funds are insufficient, a `REFUSED` transaction row is committed with `balance_seen`, preserving an immutable audit trail and caching the refusal response for replays.
5. If sufficient, the debit and credit are posted as twin ledger entries with opposing signs summing to zero, and balances update atomically.
6. A deferred constraint trigger (`accounts_match_ledger`) runs right at `COMMIT`, guaranteeing that an application role cannot modify balances directly without matching ledger entries.

### 4. How I Used AI, and Where It Was Wrong
I used AI as a fast pair-programmer to generate initial scaffolds, boilerplate Pydantic schemas, and concurrency test suites. However, the AI made several critical architectural mistakes:
- It initially accepted a client-supplied `role` parameter during registration, creating a privilege escalation hole where users could register as `admin`. I removed this and hardcoded role `'holder'`.
- It suggested logging security violations inside the request transaction; when an exception was raised, FastAPI aborted and rolled back the transaction, silently erasing the audit log! I fixed this by implementing dedicated autocommit connections in `app/audit.py`.
- It used `now()` for statement timestamps, which records the start time of the transaction rather than lock execution time, causing timestamp inversions under high concurrency. I migrated to `clock_timestamp()`.
- Its idempotency response serialization returned in-memory Python dictionaries whose key order disagreed with PostgreSQL JSONB deserialization, causing false mismatch assertions. I refactored `_save()` to `UPDATE ... RETURNING response` to enforce canonical DB-normalized JSON output.

### 5. What Is Unfinished and What I Know Is Still Open
The core double-entry engine, RBAC, statement queries, audit trails, and concurrency protections are 100% complete and verified with 38 passing tests and 0 penetration failures. Two architectural trade-offs remain open as documented in `THREATS.md`:
- **Row 16 (Denial of Service via Audit Connection Saturation):** Because security denials write to `audit_logs` on an independent autocommit connection, an aggressive distributed flood of invalid account probes could saturate connection pooler slots. The recommended fix is edge rate-limiting (e.g., Cloudflare Turnstile or Redis token buckets).
- **Row 22 (Account ID Enumeration via Valid Transfer Probing):** A user can determine whether account ID `X` exists because transferring 1 paisa to an existing account returns `201 Created` while a nonexistent account returns `404 Not Found`. While personal holder identities are never revealed, full enumeration resistance would require opaque public identifiers or payment request tokens.
