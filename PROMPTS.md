# PROMPTS.md: where AI was wrong and what I did

## Entry format
Date | Tool | What I asked | What it produced | What was wrong | What I did instead | Fix commit

| Date | Tool | What I asked | What it produced | What was wrong | What I did instead | Fix commit |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-11-06 | Antigravity AI | Implement FastAPI registration, login, and RBAC with Argon2 and JWT | Generated registration schema accepting a `role` field (`Literal['admin', 'holder', 'auditor'] = 'holder'`) | Privilege Escalation Vulnerability: allowing the client to specify their role in the registration payload permits any anonymous user to register directly as `admin` or `auditor`. Furthermore, JWT claims were initially trusted without per-request DB role verification. | Hardcoded `'holder'` role strictly in the SQL `INSERT` statement (`VALUES (%s, %s, 'holder')`) and removed `role` from request body so privilege escalation is physically impossible. Admin and auditor accounts are provisioned exclusively via `scripts/seed.py`. Added DB-queried role checks in `deps.py` on every authenticated request. | [9ac3402](https://github.com/Komatlakarthik/ledgerline/commit/9ac3402) |
