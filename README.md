# LedgerLine 💸

> **Double-entry money movement engine with provable integrity, raw SQL concurrency control, and zero negative-balance tolerance.**

Built for the **Snovasys Fresher Hiring Challenge 2026**.

---

## 🏛️ System Architecture

- **Backend:** FastAPI (Python 3.12)
- **Database Driver:** `psycopg` (Version 3) with thread-safe `psycopg-pool` and **raw parameterized SQL** (no ORM magic, guaranteeing full auditability of transaction boundaries and row locks).
- **Database:** PostgreSQL on Neon (Serverless Postgres with Connection Pooling).
- **Security & Cryptography:** `argon2-cffi` (Argon2id password hashing), PyJWT (short-lived HMAC-SHA256 signed tokens).
- **Integrity Constraints:**
  - Discrete integer arithmetic (`balance_paise`, 1 INR = 100 paise) preventing IEEE 754 floating-point inaccuracies.
  - Server-side and database-enforced invariant: `CHECK (is_system OR balance_paise >= 0)`.
  - Zero-sum double-entry ledger balance conservation: all money origins and sinks balance against the `EXTERNAL` system account ($\sum \text{balances} = 0$).

---

## 🚀 Quickstart

### 1. Prerequisites
- Python 3.12+
- PostgreSQL connection string (e.g., Neon.tech)

### 2. Environment Setup
Create a `.env` file in the project root:
```env
DATABASE_URL=postgresql://user:password@ep-xyz.neon.tech/neondb?sslmode=require
JWT_SECRET=your-secure-random-secret
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### 3. Installation
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt
```

### 4. Database Migration
Apply the initial schema to PostgreSQL:
```powershell
# Using Python / psycopg
python -c "import psycopg, os; from dotenv import load_dotenv; load_dotenv(); conn = psycopg.connect(os.environ['DATABASE_URL']); cur = conn.cursor(); cur.execute(open('db/schema.sql').read()); conn.commit(); print('Schema loaded successfully!')"
```

### 5. Run the Server
```powershell
uvicorn app.main:app --reload --port 8000
```
- **Health Check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- **Interactive Swagger Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🧪 Running Tests
All integrity, concurrency, and security tests run against live PostgreSQL:
```powershell
pytest -v
```

---

## 🔒 Security & Evaluation Highlights
- **PROMPTS.md:** Detailed log tracking prompt iterations, AI deficiencies identified, and manual security corrections implemented.
- **Role-Based Access Control:** Strict separation of duties between `admin`, `holder`, and `auditor`.
