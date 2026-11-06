# PROMPTS.md — LedgerLine Development Record

As per the evaluation criteria, this file records chronological, dated entries detailing instructions given to AI tools, what the tool produced, where the tool was subtly or critically wrong (particularly regarding authorization, security, concurrency, and audit trails), and what architectural corrections were implemented.

---

### Entry 1 — 2026-11-06
- **Area:** Authentication, Role-Based Access Control (RBAC), and Account Initialization
- **Commit:** [c45dc81](https://github.com/Komatlakarthik/ledgerline/commit/c45dc81)
- **Prompt Asked:**
  > "Implement FastAPI authentication with Argon2 password hashing, JWT creation, and role-based access control for `admin`, `holder`, and `auditor`."
- **What the tool produced:**
  1. The AI generated a basic stateless role check that validated roles directly from the decoded JWT claims (`payload["role"]`) without querying the database.
  2. The AI used Pydantic `EmailStr` in the request schema without installing `email-validator` (or `pydantic[email]`), causing runtime `ImportError` on test collection.
  3. The registration endpoint inserted a record into the `users` table but failed to atomically initialize a primary account in the `accounts` table for `holder` accounts.
- **Why this was wrong & high-risk:**
  - In a financial system, trusting unverified role claims from JWTs without DB validation creates an authorization vulnerability if an account's role is downgraded or disabled while an active token remains valid.
  - Failing to initialize an account on holder signup leaves holders unable to receive or hold money, violating data integrity invariants.
  - The missing dependency broke automated test suites immediately.
- **What was fixed instead:**
  - Implemented `get_current_user` to decode the JWT and fetch the latest user record directly from PostgreSQL via parameterized SQL (`SELECT id, email, role, created_at FROM users WHERE id = %s`).
  - Created a composable dependency `require_role(*allowed_roles)` returning standard `403 Forbidden` responses when permissions are insufficient.
  - Added atomic account creation within the registration database transaction for users registered with the `holder` role (`INSERT INTO accounts (owner_id, name, is_system, balance_paise) VALUES (...)`).
  - Installed `pydantic[email]` (`email-validator`) and updated `requirements.txt`.
  - Added comprehensive automated test cases in `tests/test_auth.py` verifying holder isolation, duplicate registration rejection (409), and role enforcement across admin, auditor, and holder endpoints.
