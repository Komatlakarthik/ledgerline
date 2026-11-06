CREATE TYPE user_role AS ENUM ('admin', 'holder', 'auditor');

CREATE TABLE users (
  id            BIGSERIAL PRIMARY KEY,
  email         TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role          user_role NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE accounts (
  id            BIGSERIAL PRIMARY KEY,
  owner_id      BIGINT REFERENCES users(id),     -- NULL only for the system account
  name          TEXT NOT NULL,
  is_system     BOOLEAN NOT NULL DEFAULT false,
  balance_paise BIGINT NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (is_system OR balance_paise >= 0)        -- the floor, enforced by the DB itself
);

-- the EXTERNAL account stands in for the outside world (deposits/withdrawals)
INSERT INTO accounts (name, is_system) VALUES ('EXTERNAL', true);
