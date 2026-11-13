# How TraceFlow works

TraceFlow watches a stream of bank transfers (all fake, in ₹), gives each one a **risk score from 0 to 100**, and explains **why** in plain English. Score 40+ becomes an alert. A human reviews it; the system never blocks anyone.

## The files

- `backend/app.py` – the web server (FastAPI). It receives transfers and serves the alerts, the graph data and the dashboard page.
- `backend/db.py` and `backend/schema.sql` – the database. One SQLite file (`traceflow.db`) with 3 tables: accounts, transactions, alerts.
- `backend/rules.py` – **Layer 1, rules.** Structuring (many transfers just under ₹50,000), velocity (too many in an hour), pass-through (money in, then out fast), amount spike (far above normal).
- `backend/graph.py` – **Layer 2, graph.** Finds money loops (money returning to its starting account through 3–6 accounts), fan-in (many senders → one account) and fan-out. Also builds the graph for the dashboard.
- `backend/ml.py` – **Layer 3, the AI.** An IsolationForest model learns what a normal account looks like (average amount, transfers per hour, number of counterparties, night-time share, money in vs out). An account that looks very different gets +30 points and a plain-English reason. It only adds evidence; it never raises an alert alone.
- `scripts/train.py` – trains that model on calm fake traffic and saves it in `backend/models/`. The server only loads it.
- `backend/score.py` – adds up the points from all layers, saves the score and reasons, and creates alerts (one per strong pattern, no duplicates).
- `backend/static/index.html` – the dashboard: alert list, reasons, money-flow graph, two demo buttons.
- `scripts/generate.py` – makes fake normal traffic (about 1,000 transfers) and the laundering ring used in the demo.
- `scripts/replay.py` – sends the fake transfers to the server one by one, so traffic looks live.
- `backend/tests/test_core.py` – automatic checks (run `python -m pytest`).
- `CLAUDE.md` – the project plan and rules. `requirements.txt` – the Python packages.

Not built yet: the SAR PDF and the README.

## Demo steps

1. Start the server: `.\.venv\Scripts\python.exe -m uvicorn backend.app:app`
2. In a second terminal: `.\.venv\Scripts\python.exe scripts/replay.py --calm --delay 0.3` (normal traffic, no alerts).
3. Open `http://localhost:8000`. The alert list is empty: traffic looks calm.
4. Click **Inject laundering ring**. Two HIGH alerts appear within a second: *cycle* and *structuring*.
5. Read the reasons in section 2, then look at section 3: the red diamonds and arrows are the money loop.
6. Click **Mark reviewed** to show a human makes the decision. Click **Reset demo** to start again.

## Limits (say these to the judges)

All data is fake. Thresholds are our assumptions, not real regulations. A big payroll run can look like fan-out. Humans decide; alerts are for review only.
