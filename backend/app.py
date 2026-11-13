import json
import random
from datetime import datetime, timezone
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from scripts.generate import ring  # the generator owns the synthetic patterns; run uvicorn from the repo root

from . import db, graph, rules, sar, score

app = FastAPI(title="TraceFlow")


def get_db():
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


class TxIn(BaseModel):
    from_account: str = Field(min_length=1, max_length=64)
    to_account: str = Field(min_length=1, max_length=64)
    amount: float = Field(gt=0, allow_inf_nan=False)
    channel: Literal["UPI", "IMPS", "NEFT", "CARD", "WALLET"]
    ts: datetime | None = None  # defaults to now; naive times are treated as UTC
    from_name: str | None = None
    to_name: str | None = None

    @model_validator(mode="after")
    def accounts_differ(self):
        if self.from_account == self.to_account:
            raise ValueError("from_account and to_account must differ")
        return self


class StatusIn(BaseModel):
    status: Literal["reviewed", "dismissed"]


def _json_row(r):
    d = dict(r)
    d["reasons"] = json.loads(d["reasons"])
    return d


@app.post("/api/transactions", status_code=201)
def add_transaction(t: TxIn, conn=Depends(get_db)):
    ts = t.ts or datetime.now(timezone.utc)
    if ts.tzinfo:
        ts = ts.astimezone(timezone.utc)
    p = t.model_dump()
    p["ts"] = ts.strftime(rules.FMT)
    return score.ingest(conn, p)


@app.get("/api/alerts")
def list_alerts(level: Literal["low", "medium", "high"] | None = None,
                status: Literal["open", "reviewed", "dismissed"] | None = None,
                limit: int = Query(200, ge=1, le=1000), conn=Depends(get_db)):
    sql, args = "SELECT a.*, c.name AS account_name FROM alerts a LEFT JOIN accounts c ON c.id=a.account_id WHERE 1=1", []
    for col, val in (("level", level), ("status", status)):
        if val:
            sql += f" AND a.{col}=?"
            args.append(val)
    return [_json_row(r) for r in conn.execute(sql + " ORDER BY a.id DESC LIMIT ?", (*args, limit))]


@app.get("/api/alerts/{alert_id}")
def get_alert(alert_id: int, conn=Depends(get_db)):
    r = conn.execute("SELECT a.*, c.name AS account_name FROM alerts a LEFT JOIN accounts c ON c.id=a.account_id WHERE a.id=?",
                     (alert_id,)).fetchone()
    if not r:
        raise HTTPException(404, "alert not found")
    d = _json_row(r)
    end = conn.execute("SELECT ts FROM transactions WHERE id=?", (d["transaction_id"],)).fetchone()["ts"]
    d["transactions"] = [_json_row(t) for t in conn.execute(
        "SELECT * FROM transactions WHERE (from_account=?1 OR to_account=?1) AND ts>?2 AND ts<=?3 ORDER BY ts DESC LIMIT 100",
        (d["account_id"], rules.ago(end, 24), end))]
    return d


@app.get("/api/alerts/{alert_id}/sar.pdf")
def sar_pdf(alert_id: int, conn=Depends(get_db)):
    alert = get_alert(alert_id, conn)  # 404 if the alert does not exist
    account = conn.execute("SELECT * FROM accounts WHERE id=?", (alert["account_id"],)).fetchone()
    return Response(sar.build(alert, dict(account)), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="SAR-{alert_id}.pdf"'})


@app.patch("/api/alerts/{alert_id}")
def set_status(alert_id: int, body: StatusIn, conn=Depends(get_db)):
    with conn:
        if conn.execute("UPDATE alerts SET status=? WHERE id=?", (body.status, alert_id)).rowcount == 0:
            raise HTTPException(404, "alert not found")
    return {"id": alert_id, "status": body.status}


@app.get("/api/graph")
def get_graph(account_id: str, hours: int = Query(graph.WINDOW_H, ge=1, le=720), conn=Depends(get_db)):
    end = conn.execute("SELECT MAX(ts) FROM transactions WHERE from_account=?1 OR to_account=?1", (account_id,)).fetchone()[0]
    if not end:
        raise HTTPException(404, "account not found")
    return graph.view(conn, account_id, end, hours)  # window ends at the account's latest transaction


@app.post("/api/demo/inject-ring")
def inject_ring(conn=Depends(get_db)):
    """Laundering ring (cycle + structuring), sent through the normal ingest path with timestamps ending now."""
    n = conn.execute("SELECT COUNT(*) FROM accounts WHERE id LIKE 'RG%-S'").fetchone()[0]
    tag = f"RG{n + 1:02d}-"
    txs = ring(random.Random(n), tag, datetime.now(timezone.utc).replace(tzinfo=None))
    ids = sorted({a for t in txs for a in score.ingest(conn, t)["alert_ids"]})
    alerts = conn.execute(f"SELECT id, account_id, pattern, level, score FROM alerts WHERE id IN ({','.join('?' * len(ids))})", ids)
    return {"ring": tag, "transactions": len(txs), "alerts": [dict(a) for a in alerts]}


@app.post("/api/demo/reset")
def reset_demo(conn=Depends(get_db)):
    with conn:
        for table in ("alerts", "transactions", "accounts"):
            conn.execute(f"DELETE FROM {table}")
    return {"ok": True}


@app.get("/api/stats")
def stats(conn=Depends(get_db)):
    one = lambda sql: conn.execute(sql).fetchone()[0]
    open_by_level = dict(conn.execute("SELECT level, COUNT(*) FROM alerts WHERE status='open' GROUP BY level").fetchall())
    hourly = conn.execute("SELECT substr(created_at,1,13) AS hour, COUNT(*) AS n FROM alerts "
                          "GROUP BY hour ORDER BY hour DESC LIMIT 24").fetchall()
    return {
        "transactions": one("SELECT COUNT(*) FROM transactions"),
        "open_alerts": {l: open_by_level.get(l, 0) for l in ("low", "medium", "high")},
        "amount_at_risk": one("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE risk_score>=40"),
        "alerts_over_time": [dict(r) for r in reversed(hourly)],
    }


# The React dashboard (built with `npm run build` in frontend/). Mounted last so the /api routes above win.
DIST = db.HERE.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")
else:
    @app.get("/", include_in_schema=False)
    def frontend_missing():
        return PlainTextResponse("Dashboard not built. Run: cd frontend; npm install; npm run build", status_code=503)
