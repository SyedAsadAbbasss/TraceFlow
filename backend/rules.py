"""Layer 1: rule checks on the sender of a transaction.

Each rule returns (pattern, points, reason) or None. Thresholds are tunable
assumptions, not regulatory values. The transaction is already inserted
(has an id) when rules run, so "id <= tx.id" means "up to and including this one".
"""
from datetime import datetime, timedelta
from statistics import median

FMT = "%Y-%m-%dT%H:%M:%S"
LARGE = 100_000  # inflow considered "large" for pass-through


def inr(x):
    """₹ with Indian digit grouping: 1234567 -> ₹12,34,567."""
    s = str(round(x))
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    return "₹" + ",".join(([head] if head else []) + parts + [tail])


def ago(ts, hours):
    return (datetime.strptime(ts, FMT) - timedelta(hours=hours)).strftime(FMT)


def _one(conn, sql, *args):
    return conn.execute(sql, args).fetchone()[0]


def structuring(conn, tx):
    if not 45_000 <= tx["amount"] < 50_000:
        return
    rows = conn.execute(
        "SELECT ts, amount FROM transactions WHERE from_account=? AND amount>=45000 AND amount<50000 "
        "AND ts>? AND ts<=? AND id<=? ORDER BY ts",
        (tx["from_account"], ago(tx["ts"], 24), tx["ts"], tx["id"]),
    ).fetchall()
    if len(rows) < 3:
        return
    hours = (datetime.strptime(tx["ts"], FMT) - datetime.strptime(rows[0]["ts"], FMT)).total_seconds() / 3600
    total = sum(r["amount"] for r in rows)
    return ("structuring", 50,
            f"{len(rows)} transfers of ₹45k–₹50k in {hours:.1f} hours (total {inr(total)}), each just under ₹50,000")


def velocity(conn, tx):
    acc, ts = tx["from_account"], tx["ts"]
    n = _one(conn, "SELECT COUNT(*) FROM transactions WHERE from_account=? AND ts>? AND ts<=? AND id<=?",
             acc, ago(ts, 1), ts, tx["id"])
    if n < 6:  # minimum count so new accounts don't trigger on a couple of transactions
        return
    past = _one(conn, "SELECT COUNT(*) FROM transactions WHERE from_account=? AND ts>? AND ts<=?",
                acc, ago(ts, 169), ago(ts, 1))
    rate = past / 168  # average per hour over the previous 7 days
    if n > 5 * rate:
        return ("velocity", 25, f"{n} transactions in the last hour vs a usual {rate:.2f} per hour")


def pass_through(conn, tx):
    acc, ts, since = tx["from_account"], tx["ts"], ago(tx["ts"], 6)
    inflow = _one(conn, "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE to_account=? AND ts>? AND ts<=?",
                  acc, since, ts)
    if inflow < LARGE:
        return
    out = _one(conn, "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE from_account=? AND ts>? AND ts<=? AND id<=?",
               acc, since, ts, tx["id"])
    if out >= 0.8 * inflow:
        return ("pass_through", 45,
                f"{inr(out)} sent out within 6 hours of receiving {inr(inflow)} ({out / inflow:.0%})")


def amount_spike(conn, tx):
    if tx["amount"] < 25_000:  # ignore spikes on small absolute amounts
        return
    past = [r[0] for r in conn.execute(
        "SELECT amount FROM transactions WHERE from_account=? AND id<? ORDER BY id DESC LIMIT 50",
        (tx["from_account"], tx["id"]))]
    if len(past) < 5:  # no baseline yet
        return
    m = median(past)
    if tx["amount"] > 10 * m:
        return ("amount_spike", 30, f"{inr(tx['amount'])} is {tx['amount'] / m:.0f}× this account's usual {inr(m)}")


def check(conn, tx):
    return [h for h in (r(conn, tx) for r in (structuring, velocity, pass_through, amount_spike)) if h]
