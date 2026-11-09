-- Day 2 fix: now() is the START time of a transaction, so statement order could
-- disagree with lock order. clock_timestamp() is taken at insert, under the lock.
ALTER TABLE transactions   ALTER COLUMN created_at SET DEFAULT clock_timestamp();
ALTER TABLE ledger_entries ALTER COLUMN created_at SET DEFAULT clock_timestamp();

CREATE TABLE audit_logs (
  id         BIGSERIAL PRIMARY KEY,
  user_id    BIGINT,                      -- no FK: must record even bogus ids
  action     TEXT NOT NULL,
  detail     JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER audit_logs_append_only BEFORE UPDATE OR DELETE ON audit_logs
  FOR EACH ROW EXECUTE FUNCTION forbid_change();
CREATE TRIGGER audit_logs_no_truncate BEFORE TRUNCATE ON audit_logs
  FOR EACH STATEMENT EXECUTE FUNCTION forbid_change();

-- A balance can only change if the newest ledger entry for that account agrees with it.
-- Checked at COMMIT, so even a compromised app role cannot edit balances directly.
CREATE FUNCTION check_balance_matches_ledger() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE last_bal BIGINT;
BEGIN
  SELECT balance_after INTO last_bal FROM ledger_entries
   WHERE account_id = NEW.id ORDER BY id DESC LIMIT 1;
  IF NEW.balance_paise <> COALESCE(last_bal, 0) THEN
    RAISE EXCEPTION 'account % balance % does not match ledger %',
      NEW.id, NEW.balance_paise, COALESCE(last_bal, 0);
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER accounts_match_ledger AFTER UPDATE OF balance_paise ON accounts
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_balance_matches_ledger();
