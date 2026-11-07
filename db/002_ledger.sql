CREATE TABLE transactions (
  id               BIGSERIAL PRIMARY KEY,
  kind             TEXT NOT NULL CHECK (kind IN ('deposit','withdrawal','transfer')),
  status           TEXT NOT NULL CHECK (status IN ('POSTED','REFUSED')),
  from_account_id  BIGINT REFERENCES accounts(id),
  to_account_id    BIGINT REFERENCES accounts(id),
  amount_paise     BIGINT NOT NULL CHECK (amount_paise > 0 AND amount_paise <= 1000000000),
  reason           TEXT,
  balance_seen     BIGINT,
  initiated_by     BIGINT NOT NULL REFERENCES users(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (from_account_id IS DISTINCT FROM to_account_id),
  CHECK (status = 'POSTED' OR reason IS NOT NULL)
);
CREATE TABLE ledger_entries (
  id             BIGSERIAL PRIMARY KEY,
  txn_id         BIGINT NOT NULL REFERENCES transactions(id),
  account_id     BIGINT NOT NULL REFERENCES accounts(id),
  amount_paise   BIGINT NOT NULL CHECK (amount_paise <> 0),
  balance_after  BIGINT NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ledger_entries_account_idx ON ledger_entries (account_id, id);
CREATE INDEX transactions_from_idx ON transactions (from_account_id, id);
CREATE INDEX transactions_to_idx ON transactions (to_account_id, id);

CREATE TABLE idempotency_keys (
  user_id       BIGINT NOT NULL REFERENCES users(id),
  key           TEXT   NOT NULL,
  request_hash  TEXT   NOT NULL,
  status_code   INT,
  response      JSONB,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, key)
);

CREATE FUNCTION forbid_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION '% on % is not allowed: table is append-only', TG_OP, TG_TABLE_NAME; END $$;
CREATE TRIGGER ledger_entries_append_only BEFORE UPDATE OR DELETE ON ledger_entries FOR EACH ROW EXECUTE FUNCTION forbid_change();
CREATE TRIGGER transactions_append_only   BEFORE UPDATE OR DELETE ON transactions   FOR EACH ROW EXECUTE FUNCTION forbid_change();
CREATE TRIGGER ledger_entries_no_truncate BEFORE TRUNCATE ON ledger_entries FOR EACH STATEMENT EXECUTE FUNCTION forbid_change();
CREATE TRIGGER transactions_no_truncate   BEFORE TRUNCATE ON transactions   FOR EACH STATEMENT EXECUTE FUNCTION forbid_change();
