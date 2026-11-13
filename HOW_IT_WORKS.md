# How TraceFlow works

TraceFlow watches a stream of bank transfers (all fake, in ₹), gives each one a **risk score from 0 to 100**, and explains **why** in plain English. Score 40+ becomes an alert. A human reviews it; the system never blocks anyone.

## Backend (Python)

- `backend/app.py` – the web server (FastAPI). Receives transfers, serves alerts, graph data and the PDF, and serves the built dashboard at `/`.
- `backend/db.py`, `backend/schema.sql` – one SQLite file (`traceflow.db`) with 3 tables: accounts, transactions, alerts.
- `backend/rules.py` – **Layer 1, rules:** structuring (many transfers just under ₹50,000), velocity, pass-through, amount spike.
- `backend/graph.py` – **Layer 2, graph:** money loops (money returning to its start through 3–6 accounts), fan-in, fan-out. Also builds the graph for the dashboard.
- `backend/ml.py` – **Layer 3, the AI:** an IsolationForest learns what a normal account looks like. A very different account gets +30 points and a plain-English reason. It never raises an alert alone.
- `scripts/train.py` – trains that model on calm fake traffic into `backend/models/`.
- `backend/score.py` – adds up the points, saves score and reasons, creates alerts (one per strong pattern, no duplicates).
- `backend/sar.py` – builds the one-page SAR (Suspicious Activity Report) PDF for an alert.
- `scripts/generate.py` makes fake traffic and the laundering ring. `scripts/replay.py` sends it to the server one transfer at a time.
- `backend/tests/test_core.py` – automatic checks (`python -m pytest`).

## Dashboard (React, in `frontend/`)

- `src/App.jsx` – the whole page. Asks the backend for fresh data every 2.5 seconds and hands it to the parts below.
- `src/TopBar.jsx` – title, "Live" dot, Inject and Reset buttons.
- `src/StatCards.jsx` – the four number cards and the alerts-over-time chart (recharts).
- `src/AlertList.jsx` – the alert cards (newest is selected automatically).
- `src/AlertDetail.jsx` – score, reasons with icons, related transfers, Mark reviewed / Dismiss / SAR PDF.
- `src/MoneyGraph.jsx` – the money-flow graph (react-force-graph-2d). Red = on a money loop.
- `src/lib.js` (backend calls, ₹ format, icon per reason), `src/LevelChip.jsx` (HIGH/MEDIUM/LOW label), `src/styles.css` (all styling, light and dark).
- `npm run build` turns this into `frontend/dist`, which FastAPI serves. `npm run dev` is for editing (port 5173, forwards `/api` to port 8000).

## Demo steps

1. One time: `cd frontend; npm install; npm run build; cd ..`
2. Start everything: `.\.venv\Scripts\python.exe -m uvicorn backend.app:app`
3. Second terminal: `.\.venv\Scripts\python.exe scripts/replay.py --calm --delay 0.3` (normal traffic).
4. Open `http://localhost:8000`: "All clear — no suspicious activity".
5. Click **Inject laundering ring**: two HIGH alerts (*circular money movement*, *structuring*) appear. Read the reasons; the red dots and arrows in the graph are the money loop.
6. Click **SAR report (PDF)**, then **Mark reviewed** (a human decides). **Reset demo** starts again.

## Limits (say these to the judges)

All data is fake. Thresholds are our assumptions, not real regulations. A big payroll run can look like fan-out. Humans decide; alerts are for review only.
