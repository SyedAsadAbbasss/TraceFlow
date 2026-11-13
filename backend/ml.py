"""Layer 3 (the "AI" layer): IsolationForest on account behaviour.

Trained offline on calm synthetic traffic by scripts/train.py; the API only loads the saved model.
It adds evidence (30 points + a plain-language reason) but cannot raise an alert on its own.
"""
import math
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from . import rules

MODEL_PATH = Path(__file__).resolve().parent / "models" / "iforest.joblib"  # tests monkeypatch this
WINDOW_H = 72  # behaviour is measured over the last 3 days
MIN_TX = 3     # too little history = no opinion
POINTS = 30


def features(conn, acc, ts, last_id=2**62):
    """5 numbers describing the account's last 3 days, or None if it has too little history."""
    rows = conn.execute(
        "SELECT from_account f, to_account t, amount, ts FROM transactions "
        "WHERE (from_account=?1 OR to_account=?1) AND ts>?2 AND ts<=?3 AND id<=?4 ORDER BY ts",
        (acc, rules.ago(ts, WINDOW_H), ts, last_id)).fetchall()
    if len(rows) < MIN_TX:
        return None
    sent = [r["amount"] for r in rows if r["f"] == acc]
    received = sum(r["amount"] for r in rows if r["t"] == acc)
    times = [datetime.strptime(r["ts"], rules.FMT) for r in rows]
    return [
        sum(sent) / len(sent) if sent else 0,                                         # average amount sent
        max(sum(1 for u in times if 0 <= (u - t).total_seconds() < 3600) for t in times),  # most transfers in any 1 hour
        len({r["t"] if r["f"] == acc else r["f"] for r in rows}),                      # different counterparties
        sum(1 for t in times if t.hour < 5) / len(times),                              # share of activity 00:00-05:00
        math.log((received + 1) / (sum(sent) + 1)),                                    # money in vs money out
    ]


def train(conn, path):
    """Fit on every account's features at the end of the data; returns how many accounts were used."""
    end = conn.execute("SELECT MAX(ts) FROM transactions").fetchone()[0]
    X = np.array([f for (a,) in conn.execute("SELECT id FROM accounts").fetchall() if (f := features(conn, a, end))])
    model = IsolationForest(n_estimators=100, random_state=0).fit(X)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "median": np.median(X, axis=0), "std": X.std(axis=0) + 1e-9,
                 # flag the most unusual ~10%: loose on purpose, because this layer can only add evidence, never alert alone
                 "threshold": float(np.percentile(model.decision_function(X), 10))},
                path)
    return len(X)


@lru_cache(maxsize=4)
def _load(path):
    return joblib.load(path) if Path(path).exists() else None


def _say(i, v, typical):
    """One plain-language sentence for feature i with value v (typical = median of normal accounts)."""
    if i == 0:
        return f"its average transfer is {rules.inr(v)}, {v / max(typical, 1):.0f}× the typical account's {rules.inr(typical)}"
    if i == 1:
        return f"it made {v:.0f} transfers within one hour, vs {typical:.0f} for a typical account"
    if i == 2:
        return f"it deals with {v:.0f} different accounts, vs {typical:.0f} for a typical account"
    if i == 3:
        return f"{v:.0%} of its activity is between 00:00 and 05:00, vs {typical:.0%} typical"
    return f"it sends {math.exp(-v):.1f}× more money than it receives" if v < 0 else f"it receives {math.exp(v):.1f}× more money than it sends"


def check(conn, tx):
    """[(pattern, points, reason)] if the sender's behaviour is unusual compared with normal accounts."""
    bundle = _load(MODEL_PATH)
    f = bundle and features(conn, tx["from_account"], tx["ts"], tx["id"])
    if not f:
        return []
    x = np.array(f)
    if bundle["model"].decision_function([x])[0] >= bundle["threshold"]:
        return []
    z = (x - bundle["median"]) / bundle["std"]
    z[:4] = np.maximum(z[:4], 0)  # for the first four, only "unusually high" is interesting; flow can be off either way
    top = [i for i in np.argsort(-np.abs(z))[:2]]
    return [("ai_anomaly", POINTS, "Unusual behaviour for this account (AI): " + "; ".join(_say(i, x[i], bundle["median"][i]) for i in top))]
