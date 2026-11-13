# TraceFlow: AI Fraud Detection & Anti-Money Laundering

Hackathon project. Read this whole file before doing anything. It is the single source of truth for this repo.

## Hackathon details

- Duration: [3 hours]
- Team size: [1]
- Repo: https://github.com/SyedAsadAbbasss/traceflow (empty at start, no README yet)
- OS: Windows, PowerShell, VS Code. Python 3.12 installed. **No Docker, no PostgreSQL.**

## Problem statement (summary)

"Intelligent Financial Fraud Detection and Anti-Money Laundering System". Build a working prototype that:
- detects fraudulent transactions with AI/ML
- finds anomalies: unusual amounts, frequencies and account behaviour
- finds AML patterns: transaction splitting, circular money movement, unusual transfers
- assigns risk scores and generates real-time alerts
- explains WHY something was flagged (explainable AI)
- shows everything on an interactive dashboard

Only synthetic, anonymised or public data is allowed. We must explain the methodology, the limitations and responsible-AI considerations.

## Our angle (how we win)

Most teams will train one classifier on a Kaggle fraud dataset and report accuracy. We focus on:
1. **AML on a transaction graph:** cycles, fan-in/fan-out, structuring
2. **Plain-language explanations** for every alert
3. **A live demo:** click "Inject laundering ring" and watch it get caught within seconds
4. **A one-click Suspicious Activity Report (SAR) PDF**

## Working rules for Claude Code

- Do ONE phase at a time. At the end of each phase: run the tests, show me how to run and check it, then STOP and wait for me.
- Shortest working code. Reuse what exists. No abstractions with one implementation, no config for values that never change.
- Do not add dependencies beyond the stack below without asking me first.
- Never commit `data/`, `.venv/`, `*.db` or anything over 10 MB.
- Explain things to me in short points, each stating the cause ("X happens because Y").
- If a step needs me (Kaggle login, installing Node, approving something), stop and tell me exactly what to do.
- Commit at the end of each phase with a clear message, after I confirm it works.

## Stack (fixed)

- **Backend:** FastAPI + uvicorn + Python's built-in `sqlite3` (raw SQL, no ORM). The database is one file, `traceflow.db`. Enable `PRAGMA journal_mode=WAL` at startup. Store `reasons` as JSON text (`json.dumps` / `json.loads`).
- **Analytics/ML:** pandas, scikit-learn (IsolationForest), networkx. Phase 4 only: lightgbm, shap.
- **PDF:** reportlab.
- **Frontend:** React via Vite, react-router-dom, recharts (charts), react-force-graph-2d (money-flow graph). Vite dev server proxies `/api` to `http://localhost:8000`, so no CORS setup is needed.
- **"Real-time":** a replay script POSTs transactions to the API every few hundred ms, and the dashboard polls every 2–3 s. NO Kafka, NO WebSockets, NO auth.
- **Tests:** pytest.
- **Currency:** INR (₹). All data synthetic.

## Folder structure

```
traceflow/
├── CLAUDE.md
├── README.md              # written in Phase 6
├── .gitignore
├── requirements.txt
├── backend/
│   ├── app.py             # FastAPI routes
│   ├── db.py              # connection, schema init, small query helpers
│   ├── schema.sql
│   ├── rules.py           # Layer 1: rule-based checks
│   ├── graph.py           # Layer 2: graph AML (networkx)
│   ├── ml.py              # Layers 3 & 4 (Phase 4)
│   ├── score.py           # combines layers into one risk score + reasons
│   ├── sar.py             # SAR PDF (reportlab)
│   └── tests/
├── scripts/
│   ├── generate.py        # synthetic normal traffic + laundering-ring injection
│   ├── replay.py          # streams transactions into the API
│   └── evaluate.py        # PR-AUC / recall report (Phase 4)
├── frontend/              # Vite React app
└── data/                  # Kaggle CSVs, gitignored
```

## Data

- **Our own generator (`scripts/generate.py`)** is the primary demo data. It produces about 200 accounts with realistic normal behaviour (salary credits, bills, UPI payments to merchants and friends, varied amounts and times) and can inject labelled suspicious patterns: a structuring burst, a 3–6 account cycle, fan-in to a mule, fan-out from a mule, and a pass-through account. Seeded random, so demos are repeatable. The project does not depend on Kaggle to work.
- **IBM "Transactions for Anti Money Laundering"** (Kaggle, NeurIPS 2023, use only `HI-Small_Trans.csv` + `HI-Small_Patterns.txt`): used to validate the graph layer against labelled laundering patterns. The user downloads it into `data/`.
- **PaySim** (Kaggle, "Synthetic Financial Datasets For Fraud Detection"): used to train the Phase 4 classifier. The user downloads it into `data/`.

## Database schema (SQLite)

```sql
CREATE TABLE accounts (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,              -- synthetic name
  created_at  TEXT NOT NULL,              -- ISO timestamp
  is_synthetic_bad INTEGER NOT NULL DEFAULT 0 CHECK (is_synthetic_bad IN (0,1))  -- ground truth for evaluation only, never used for scoring
);

CREATE TABLE transactions (
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
CREATE INDEX tx_from_ts ON transactions(from_account, ts);
CREATE INDEX tx_to_ts   ON transactions(to_account, ts);

CREATE TABLE alerts (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id     TEXT REFERENCES accounts(id),
  transaction_id INTEGER REFERENCES transactions(id),
  pattern        TEXT NOT NULL,           -- e.g. 'structuring', 'cycle', 'fan_in'
  level          TEXT NOT NULL CHECK (level IN ('low','medium','high')),
  score          INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
  reasons        TEXT NOT NULL,           -- JSON list of plain-language strings
  status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','reviewed','dismissed')),
  created_at     TEXT NOT NULL
);
```

Do not create duplicate alerts for the same pattern on the same account within the same time window.

## Detection: 4 layers → 1 risk score (0–100)

### Layer 1: Rules (`rules.py`, Phase 1)
- **Structuring:** 3+ outgoing transfers between ₹45,000 and ₹49,999 from one account within 24 h.
- **Velocity:** transactions in the last hour > 5× the account's average hourly rate (with a minimum count so new accounts don't trigger on 2 transactions).
- **Pass-through:** an account receives large inflows and sends out ≥ 80% of them within 6 h.
- **New account + high value:** account younger than 7 days moving > ₹1,00,000.
- **Amount spike:** amount > 10× the account's median.

Each rule returns `(points, reason_string)`. Reasons must be specific, with real numbers: "6 transfers of ₹45k–₹50k in 9 hours", not "suspicious structuring".

### Layer 2: Graph AML (`graph.py`, Phase 2)
- Build a networkx DiGraph from transactions in a sliding window (default 48 h). Accounts are nodes; edges carry amount and timestamp.
- **Cycles:** money returning to its origin through 3–6 accounts. Use a bounded search (`nx.simple_cycles` with `length_bound`, or a depth-limited DFS from accounts touched by the new transaction only). Never enumerate every cycle in the whole graph.
- **Fan-in:** ≥ 8 distinct senders → one account within 24 h. **Fan-out:** one account → ≥ 8 distinct receivers within 24 h.
- Return the accounts involved, so the dashboard can highlight them.

### Layer 3: Anomaly detection (`ml.py`, Phase 4)
IsolationForest on per-account features: average amount, transactions per hour, unique counterparties, night-time ratio (00:00–05:00), inflow/outflow ratio. The top contributing features become reasons ("night-time activity 7× higher than typical accounts").

### Layer 4: Fraud classifier (`ml.py`, Phase 4)
LightGBM trained on PaySim. SHAP gives the top 3 features per prediction, turned into plain-language reasons. Report **PR-AUC and recall at the alert threshold, NOT accuracy**: fraud is < 1% of transactions, so accuracy is meaningless.

### Scoring (`score.py`)
- Score = capped sum of weighted points from all layers (0–100).
- Levels: low < 40 ≤ medium < 70 ≤ high.
- Every transaction stores its score and the full list of reasons. Every medium or high result creates an alert.

## API (`app.py`)

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/transactions` | Ingest one transaction, score it, create alerts. Validate input (amount > 0, known channel, accounts differ). |
| GET | `/api/alerts?level=&status=` | Alert feed, newest first |
| GET | `/api/alerts/{id}` | Alert detail with reasons and related transactions |
| PATCH | `/api/alerts/{id}` | Analyst sets status to reviewed/dismissed (human in the loop) |
| GET | `/api/accounts/{id}` | Account profile + recent transactions + risk history |
| GET | `/api/graph?account_id=&hours=` | Nodes/edges around an account for the graph view, with suspicious ones marked |
| GET | `/api/stats` | Totals: transactions processed, alerts by level, amount at risk, alerts over time |
| POST | `/api/demo/inject-ring` | Injects a laundering ring (structuring + cycle) through the normal ingest path |
| POST | `/api/demo/reset` | Clears transactions/alerts for a fresh demo |
| GET | `/api/alerts/{id}/sar.pdf` | Suspicious Activity Report PDF |

## Dashboard (frontend)

1. **Overview / live feed:** summary cards (transactions processed, open alerts by level, ₹ at risk), alerts-over-time chart, live alert list with low/medium/high colour chips. Polls every 2–3 s. Has an "Inject laundering ring" button and a "Reset demo" button.
2. **Alert detail:** score gauge, every reason as a readable list, related transactions table, SHAP top features (Phase 4+), buttons for Mark reviewed / Dismiss / Download SAR PDF.
3. **Money-flow graph:** force-directed graph around the flagged account; suspicious accounts and the cycle path highlighted in red; edges labelled with ₹ amounts; click a node to open that account.
4. **Account page:** profile, transaction history, risk over time.

Design: clean, professional, light and dark mode, readable on a laptop projector. Accessibility basics: real buttons, labels, and colour plus text for risk levels (never colour alone).

## Build phases

### Phase 0: Setup
1. Create `.venv`, then install `fastapi "uvicorn[standard]" pandas scikit-learn networkx reportlab pytest`, then write `requirements.txt`. (If PowerShell blocks `Activate.ps1`, tell me to run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.)
2. `.gitignore`: `.venv/ __pycache__/ *.pyc *.db *.db-wal *.db-shm data/ node_modules/ frontend/dist/ .env`
3. Create the folder structure (empty `data/`).
4. Check `node -v`. If Node is missing, tell me to install the LTS from nodejs.org.
5. Commit "Project setup" and push to `main`.
6. Tell me which Kaggle files to download into `data/` (needed from Phase 2 for validation and Phase 4 for training; not blocking Phase 1).

### Phase 1: Core backend + rules + synthetic stream
- `schema.sql`, `db.py` (creates `traceflow.db` from the schema if missing, WAL on), `rules.py`, `score.py` (rules only for now), ingest + alerts + stats endpoints.
- `scripts/generate.py` (normal traffic + structuring and pass-through injection) and `scripts/replay.py`.
- Tests: 5 transfers of ₹49k trigger structuring; a normal salary + bills account triggers nothing; pass-through fires at ≥ 80% outflow; invalid input is rejected.
- **Check:** start the API, run the replay script, and see alerts in `/api/alerts` and `/docs`.

### Phase 2: Graph AML + live demo injection
- `graph.py` (cycles, fan-in, fan-out), merged into `score.py`, plus the `/api/graph`, `/api/demo/inject-ring` and `/api/demo/reset` endpoints.
- If the IBM HI-Small files are in `data/`, add a small check that runs the graph layer on a sample and prints how many labelled patterns it catches.
- Tests: a 3-account and a 5-account cycle are detected; a long chain that never returns is not a cycle; 10 senders → 1 account triggers fan-in.
- **Check:** inject a ring during the replay and get a high alert within seconds.

### Phase 3: Dashboard
- Vite React app in `frontend/` with the proxy, router and the 4 screens above.
- **Check:** the full demo works end to end in the browser: calm feed → inject ring → high alert → reasons → graph highlights the cycle. **After this phase we have a demo-ready product.**

### Phase 4: ML layers
- `pip install lightgbm shap` (add both to requirements.txt).
- IsolationForest on account features; LightGBM on PaySim with SHAP; both merged into `score.py` with reasons. Save trained models to `backend/models/` (gitignored if > 10 MB). Train with a script; the API only loads the models.
- `scripts/evaluate.py` prints PR-AUC, precision and recall at the alert threshold, and a confusion matrix.
- Show SHAP top features on the alert detail page.
- **If the hackathon is under 24 hours:** skip LightGBM, keep IsolationForest only.

### Phase 5: SAR + polish
- SAR PDF: alert summary, account details, the reasons, related transactions, graph pattern description, an "analyst notes" area, and a disclaimer that it is generated from synthetic data for review.
- Polish: empty states, loading states, error messages, number formatting (₹1,00,000 Indian grouping), seed demo button.

### Phase 6: README + pitch material
- README: problem, solution, architecture diagram (Mermaid), the 4 detection layers, how to run (exact commands), screenshots, evaluation results, limitations, responsible-AI notes, tech stack.
- A short `DEMO.md` with the 3-minute demo script below.

## Demo script (3 minutes)

1. Normal traffic is flowing and the dashboard is calm.
2. Click **"Inject laundering ring"**: 5 accounts start splitting amounts and cycling money.
3. Within seconds, high-risk alerts appear. Open one: the reasons read out in plain language, and the graph highlights the cycle.
4. Download the SAR PDF. Line: "An analyst reviews this. The AI never blocks anyone on its own."

## Responsible AI & limitations (must appear in the README and the pitch)

- Trained and tested only on synthetic data; it needs real-world validation before any use.
- Thresholds are tunable assumptions, not regulatory values.
- Humans make the final decision; alerts are for review, not automatic blocking.
- No real customer data and no PII; all names and IDs are synthetic.
- Ground-truth labels (`is_synthetic_bad`) are used only for evaluation, never for scoring.

## HACKATHON MODE: ENDS 3:00 PM, SOLO (overrides everything above)

Hard deadline 3:00 PM. A working, pushed demo by 2:15 PM matters more than any feature.

### Cut
- NO Kaggle datasets, NO LightGBM, NO SHAP. Use only our synthetic generator.
- NO React/Vite/Node. The dashboard is ONE static file `backend/static/index.html` served by FastAPI, plain JS with fetch + polling. Load Chart.js and vis-network from cdnjs with pinned versions. No build step.
- NO account page.

### Keep
- Rules layer (structuring, velocity, pass-through, amount spike)
- Graph layer (cycles 3–6, fan-in, fan-out)
- IsolationForest on account features (the "AI" layer), with its top unusual features as plain-language reasons
- Alert feed, alert detail with reasons, money-flow graph with the cycle highlighted in red, "Inject laundering ring" and "Reset demo" buttons, review/dismiss buttons
- SAR PDF (reportlab) for an alert
- One test file with ~6–8 key cases

### Timeline (stop and check with me at each mark)
- 11:00–11:15 Phase 0: venv, packages (fastapi uvicorn pandas scikit-learn networkx reportlab pytest), .gitignore, folders, first commit + push
- 11:15–12:00 Schema + ingest API + rules + generator + replay script + tests
- 12:00–12:40 Graph layer + inject-ring + reset endpoints + tests. Commit + push.
- 12:40–1:40 Dashboard page (feed, detail, graph view, buttons). Commit + push. ← DEMO WORKS HERE
- 1:40–2:10 IsolationForest layer merged into the score + reasons. Commit + push.
- 2:10–2:30 SAR PDF + polish (₹ Indian number format, empty/loading states)
- 2:30–2:45 README: problem, approach (4 layers), architecture (Mermaid), how to run, limitations, responsible AI. Final commit + push.
- 2:45–3:00 BUFFER: rehearse the demo, no new features.

If any step runs 15+ minutes over, tell me and propose what to cut. After 2:30 PM, only fixes, no new features.