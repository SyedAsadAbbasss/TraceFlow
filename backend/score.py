"""Combine layers into one 0-100 risk score + reasons, store it, raise alerts."""
import json

from . import rules


def level(score):
    return "high" if score >= 70 else "medium" if score >= 40 else "low"


def ingest(conn, p):
    """p: from_account, to_account, amount, channel, ts (FMT string), optional from_name/to_name."""
    with conn:
        for acc, name in ((p["from_account"], p.get("from_name")), (p["to_account"], p.get("to_name"))):
            conn.execute("INSERT OR IGNORE INTO accounts(id, name, created_at) VALUES (?,?,?)",
                         (acc, name or acc, p["ts"]))
        cur = conn.execute("INSERT INTO transactions(from_account, to_account, amount, ts, channel) VALUES (?,?,?,?,?)",
                           (p["from_account"], p["to_account"], p["amount"], p["ts"], p["channel"]))
        tx = {**p, "id": cur.lastrowid}
        hits = rules.check(conn, tx)
        sc = min(100, sum(h[1] for h in hits))
        reasons = [h[2] for h in hits]
        conn.execute("UPDATE transactions SET risk_score=?, reasons=? WHERE id=?", (sc, json.dumps(reasons), tx["id"]))
        alert_id = _alert(conn, tx, max(hits, key=lambda h: h[1])[0], sc, reasons) if sc >= 40 else None
    return {**tx, "risk_score": sc, "level": level(sc), "reasons": reasons, "alert_id": alert_id}


def _alert(conn, tx, pattern, sc, reasons):
    """One alert per (account, pattern) per 24 h; a repeat refreshes it instead of duplicating."""
    row = conn.execute("SELECT id, score FROM alerts WHERE account_id=? AND pattern=? AND created_at>?",
                       (tx["from_account"], pattern, rules.ago(tx["ts"], 24))).fetchone()
    if row:
        if sc >= row["score"]:
            conn.execute("UPDATE alerts SET score=?, level=?, reasons=?, transaction_id=? WHERE id=?",
                         (sc, level(sc), json.dumps(reasons), tx["id"], row["id"]))
        return row["id"]
    return conn.execute(
        "INSERT INTO alerts(account_id, transaction_id, pattern, level, score, reasons, created_at) VALUES (?,?,?,?,?,?,?)",
        (tx["from_account"], tx["id"], pattern, level(sc), sc, json.dumps(reasons), tx["ts"])).lastrowid
