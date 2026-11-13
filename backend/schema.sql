CREATE TABLE IF NOT EXISTS accounts (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  is_synthetic_bad INTEGER NOT NULL DEFAULT 0 CHECK (is_synthetic_bad IN (0,1))  -- ground truth for evaluation only, never used for scoring
);

CREATE TABLE IF NOT EXISTS transactions (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  from_account TEXT NOT NULL REFERENCES accounts(id),
  to_account   TEXT NOT NULL REFERENCES accounts(id),
  amount       REAL NOT NULL CHECK (amount > 0),
  ts           TEXT NOT NULL,
  channel      TEXT NOT NULL CHECK (channel IN ('UPI','IMPS','NEFT','CARD','WALLET')),
  risk_score   INTEGER NOT NULL DEFAULT 0 CHECK (risk_score BETWEEN 0 AND 100),
  reasons      TEXT NOT NULL DEFAULT '[]',  -- JSON list of strings
  CHECK (from_account <> to_account)
);
CREATE INDEX IF NOT EXISTS tx_from_ts ON transactions(from_account, ts);
CREATE INDEX IF NOT EXISTS tx_to_ts   ON transactions(to_account, ts);

CREATE TABLE IF NOT EXISTS alerts (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id     TEXT REFERENCES accounts(id),
  transaction_id INTEGER REFERENCES transactions(id),
  pattern        TEXT NOT NULL,
  level          TEXT NOT NULL CHECK (level IN ('low','medium','high')),
  score          INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
  reasons        TEXT NOT NULL,           -- JSON list of plain-language strings
  status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','reviewed','dismissed')),
  created_at     TEXT NOT NULL
);
