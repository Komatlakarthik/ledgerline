CREATE ROLE ledgerline_app LOGIN PASSWORD :'app_pw';
GRANT USAGE ON SCHEMA public TO ledgerline_app;
GRANT SELECT, INSERT ON users, accounts TO ledgerline_app;
GRANT UPDATE (balance_paise) ON accounts TO ledgerline_app;       -- nothing else on accounts
GRANT UPDATE (password_hash) ON users TO ledgerline_app;
GRANT SELECT, INSERT ON transactions, ledger_entries, audit_logs, idempotency_keys TO ledgerline_app;
GRANT UPDATE (status_code, response) ON idempotency_keys TO ledgerline_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ledgerline_app;
-- deliberately NO delete, NO truncate, NO update on ledger/transactions/audit
