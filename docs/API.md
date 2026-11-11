# LedgerLine API Reference

Complete endpoint specification for the LedgerLine financial ledger engine.

---

## Endpoint Summary

| Endpoint | Roles | Effect on money | Idempotency-Key | Notes |
|---|---|---|---|---|
| `POST /auth/register` | public | none | no | always creates a holder |
| `POST /auth/login` | public | none | no | returns bearer JWT token (1 hr expiry) |
| `POST /accounts` | holder (own), admin (any owner) | none | no | holders can only create accounts for themselves |
| `GET /accounts`, `GET /accounts/{id}` | holder (own), admin/auditor (all) | none | no | other holder's id => 404 |
| `GET /accounts/{id}/statement` | holder (own), admin/auditor | none | no | includes posted debits/credits & refused attempts |
| `POST /deposits` | holder (own account) | +amount, EXTERNAL -amount | required | 201 posted, 404 not yours |
| `POST /withdrawals` | holder (own account) | -amount, EXTERNAL +amount | required | 409 refused if insufficient funds |
| `POST /transfers` | holder (source must be own) | net zero | required | self-transfer rejected with 422 |
| `GET /reconciliation`, `GET /audit-logs` | admin, auditor | none | no | read-only audit & balance verification |
| `GET /health`, `GET /ready` | public | none | no | database connection & readiness diagnostics |

---

## Authentication & Authorization

All protected endpoints require an `Authorization: Bearer <token>` header obtained from `POST /auth/login`.

Roles:
- **`holder`**: Standard retail client. Can create/view own accounts, deposit, withdraw, transfer from own account, and fetch own statements. Blocked from administrative and auditor reporting.
- **`auditor`**: Compliance oversight. Read-only access to all accounts, global transaction reconciliation, system audit logs, and account statements. Strictly forbidden from initiating money movements.
- **`admin`**: System administrator. Can create accounts for any owner and view system health/audit data.

---

## Endpoint Details

### 1. `POST /auth/register`
* **Access**: Public
* **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }
  ```
* **Response (201 Created)**:
  ```json
  {
    "id": 12,
    "email": "user@example.com",
    "role": "holder"
  }
  ```
* **Security Note**: Submitting `"role": "admin"` in the request body is strictly ignored; registration hardcodes `'holder'` in SQL.

---

### 2. `POST /auth/login`
* **Access**: Public
* **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }
  ```
* **Response (200 OK)**:
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer"
  }
  ```

---

### 3. `POST /accounts`
* **Access**: `holder` (own account), `admin` (arbitrary owner)
* **Request Body**:
  ```json
  {
    "name": "Checking Account",
    "owner_id": null
  }
  ```
* **Response (201 Created)**:
  ```json
  {
    "id": 4,
    "owner_id": 12,
    "name": "Checking Account",
    "balance_paise": 0
  }
  ```

---

### 4. `GET /accounts` & `GET /accounts/{id}`
* **Access**: `holder` (sees own accounts), `admin` / `auditor` (sees all accounts)
* **Response (200 OK)**:
  ```json
  [
    {
      "id": 4,
      "owner_id": 12,
      "name": "Checking Account",
      "balance_paise": 50000
    }
  ]
  ```
* **Security Note**: Querying an account owned by another holder returns `404 Not Found` (identical to nonexistent accounts to avoid enumeration).

---

### 5. `POST /deposits`
* **Access**: `holder` (must own `account_id`)
* **Header**: `Idempotency-Key: <unique-uuid-string>`
* **Request Body**:
  ```json
  {
    "account_id": 4,
    "amount_paise": 5000
  }
  ```
* **Response (201 Created)**:
  ```json
  {
    "status": "posted",
    "transaction_id": 105,
    "amount_paise": 5000,
    "balance_after": 55000
  }
  ```
* **Ledger Effect**: Debits `EXTERNAL` account (-5000 paise), credits Account 4 (+5000 paise). Net ledger sum = 0.

---

### 6. `POST /withdrawals`
* **Access**: `holder` (must own `account_id`)
* **Header**: `Idempotency-Key: <unique-uuid-string>`
* **Request Body**:
  ```json
  {
    "account_id": 4,
    "amount_paise": 3000
  }
  ```
* **Response (201 Created - Sufficient Balance)**:
  ```json
  {
    "status": "posted",
    "transaction_id": 106,
    "amount_paise": 3000,
    "balance_after": 52000
  }
  ```
* **Response (409 Conflict - Insufficient Funds)**:
  ```json
  {
    "status": "refused",
    "reason": "insufficient_funds"
  }
  ```
* **Ledger Effect**:
  - *If posted*: Credits `EXTERNAL` (+3000 paise), debits Account 4 (-3000 paise).
  - *If refused*: Transaction row committed with status `REFUSED` and current `balance_seen`. Idempotency response stored. Zero ledger entries posted.

---

### 7. `POST /transfers`
* **Access**: `holder` (must own `from_account_id`)
* **Header**: `Idempotency-Key: <unique-uuid-string>`
* **Request Body**:
  ```json
  {
    "from_account_id": 4,
    "to_account_id": 8,
    "amount_paise": 2000
  }
  ```
* **Response (201 Created)**:
  ```json
  {
    "status": "posted",
    "transaction_id": 107,
    "amount_paise": 2000,
    "balance_after": 50000
  }
  ```
* **Error**: Self-transfers (`from_account_id == to_account_id`) are rejected with `422 Unprocessable Entity`.

---

### 8. `GET /accounts/{id}/statement`
* **Access**: `holder` (own account), `admin` / `auditor` (any account)
* **Query Params**: `limit` (default 50, max 200), `offset` (default 0)
* **Response (200 OK)**:
  ```json
  [
    {
      "created_at": "2026-11-11T14:15:30.123456+00:00",
      "txn_id": 105,
      "kind": "deposit",
      "status": "POSTED",
      "amount_paise": 5000,
      "balance_after": 55000,
      "reason": null,
      "initiated_by": 12
    },
    {
      "created_at": "2026-11-11T14:15:45.654321+00:00",
      "txn_id": 106,
      "kind": "withdrawal",
      "status": "REFUSED",
      "amount_paise": -1000000,
      "balance_after": 55000,
      "reason": "insufficient_funds",
      "initiated_by": 12
    }
  ]
  ```

---

### 9. `GET /reconciliation`
* **Access**: `admin`, `auditor`
* **Response (200 OK)**:
  ```json
  {
    "ok": true,
    "total_of_all_balances_paise": 0,
    "mismatched_accounts": []
  }
  ```
* **Description**: Verifies the double-entry invariant across the entire system. `ok` is `true` if and only if `SUM(balance_paise) == 0` and every single account's cached balance equals the sum of its ledger entries.

---

### 10. `GET /audit-logs`
* **Access**: `admin`, `auditor`
* **Query Params**: `limit` (default 50), `offset` (default 0)
* **Response (200 OK)**:
  ```json
  [
    {
      "id": 1,
      "user_id": 15,
      "action": "unauthorized_money_movement",
      "detail": {
        "kind": "withdrawal",
        "from_id": 4,
        "to_id": null,
        "amount_paise": 1000
      },
      "created_at": "2026-11-11T14:16:02.123456+00:00"
    }
  ]
  ```

---

### 11. `GET /health` & `GET /ready`
* **Access**: Public
* **Response (200 OK)**:
  ```json
  // GET /health
  { "status": "ok", "db": "connected" }

  // GET /ready
  { "status": "ready", "db": "ready" }
  ```
