from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
import random

from generate import generate, ring

from backend import app as appmod
from backend import db, ml, rules, score

T0 = datetime(2025, 3, 1, 9, 0)


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "PATH", tmp_path / "t.db")
    monkeypatch.setattr(ml, "MODEL_PATH", tmp_path / "none.joblib")  # AI layer off unless a test trains a model
    c = db.connect()
    yield c
    c.close()


def tx(conn, f, t, amount, hrs=0.0, channel="UPI"):
    ts = (T0 + timedelta(hours=hrs)).strftime(rules.FMT)
    return score.ingest(conn, dict(from_account=f, to_account=t, amount=amount, channel=channel, ts=ts))


def alert_patterns(conn):
    return [r[0] for r in conn.execute("SELECT pattern FROM alerts")]


def test_structuring_fires_once(conn):
    for i in range(5):
        r = tx(conn, "A", f"B{i}", 49_000, hrs=i)
    assert "5 transfers of ₹45k–₹50k in 4.0 hours" in r["reasons"][0]
    assert r["risk_score"] >= 40
    assert alert_patterns(conn) == ["structuring"]  # 3rd, 4th, 5th transfer share one alert


def test_normal_account_triggers_nothing(conn):
    tx(conn, "EMP", "P", 60_000, channel="NEFT")  # salary
    for i in range(10):  # bills / shopping over a day
        tx(conn, "P", f"M{i % 3}", 500 + i * 100, hrs=1 + i * 3)
    assert conn.execute("SELECT MAX(risk_score) FROM transactions").fetchone()[0] == 0


def test_pass_through_at_80_percent(conn):
    tx(conn, "S1", "MULE", 150_000, 0, "NEFT")
    tx(conn, "S2", "MULE", 150_000, 0.5, "NEFT")
    out = [tx(conn, "MULE", f"D{i}", 69_000, 1 + i * 0.5) for i in range(4)]
    assert [o["risk_score"] for o in out[:3]] == [0, 0, 0]  # 207k of 300k = 69%
    assert out[3]["reasons"] == ["₹2,76,000 sent out within 6 hours of receiving ₹3,00,000 (92%)"]
    assert rules.inr(12345678) == "₹1,23,45,678" and rules.inr(999) == "₹999"


def test_velocity_needs_minimum_count(conn):
    for i in range(7):  # baseline: 7 transactions over the previous 2 days
        tx(conn, "V", f"M{i}", 100, hrs=-48 + i * 6)
    quiet = [tx(conn, "V", "X", 100, hrs=0.1 * i) for i in range(5)]  # 5 in an hour: below the minimum
    assert all(q["risk_score"] == 0 for q in quiet)
    assert "6 transactions in the last hour" in tx(conn, "V", "X", 100, hrs=0.6)["reasons"][0]


def test_amount_spike(conn):
    for i in range(6):
        tx(conn, "U", f"M{i}", 400, hrs=i * 3)
    assert "100× this account's usual ₹400" in tx(conn, "U", "Z", 40_000, hrs=20)["reasons"][0]


def test_invalid_input_rejected(conn):
    c = TestClient(appmod.app)
    ok = dict(from_account="A", to_account="B", amount=100, channel="UPI")
    assert c.post("/api/transactions", json=ok).status_code == 201
    for bad in (dict(amount=0), dict(amount=-5), dict(amount="abc"), dict(channel="BTC"), dict(to_account="A")):
        assert c.post("/api/transactions", json=ok | bad).status_code == 422, bad


def test_alert_api_flow(conn):
    c = TestClient(appmod.app)
    for i in range(5):
        ts = (T0 + timedelta(hours=i)).isoformat()
        c.post("/api/transactions", json=dict(from_account="A", to_account=f"B{i}", amount=49_000, channel="IMPS", ts=ts))
    alerts = c.get("/api/alerts?level=medium").json()
    assert len(alerts) == 1 and alerts[0]["pattern"] == "structuring"
    aid = alerts[0]["id"]
    assert len(c.get(f"/api/alerts/{aid}").json()["transactions"]) == 5
    assert c.patch(f"/api/alerts/{aid}", json={"status": "dismissed"}).json()["status"] == "dismissed"
    assert c.get("/api/alerts?status=open").json() == []
    s = c.get("/api/stats").json()
    assert s["transactions"] == 5 and s["open_alerts"]["medium"] == 0 and s["amount_at_risk"] > 0
    assert c.get("/api/alerts/999").status_code == 404


@pytest.mark.parametrize("k", [3, 5])
def test_cycle_detected(conn, k):
    n = [f"N{i}" for i in range(k)]
    for i in range(k):
        r = tx(conn, n[i], n[(i + 1) % k], 20_000, hrs=i)
    assert f"({k} accounts" in r["reasons"][0] and r["risk_score"] >= 40
    assert alert_patterns(conn) == ["cycle"]


def test_chain_and_oversized_loop_are_not_cycles(conn):
    for i in range(6):  # A0 -> A1 -> ... -> A6, never returns
        tx(conn, f"A{i}", f"A{i + 1}", 20_000, hrs=i)
    for i in range(7):  # 7 accounts in a loop: beyond the 3-6 bound
        tx(conn, f"L{i}", f"L{(i + 1) % 7}", 20_000, hrs=10 + i)
    assert alert_patterns(conn) == []


def test_fan_in_and_fan_out(conn):
    for i in range(10):
        r = tx(conn, f"S{i}", "MULE", 15_000, hrs=i * 0.1)
    assert "10 different accounts sent money to this account" in " ".join(r["reasons"])
    assert conn.execute("SELECT account_id FROM alerts WHERE pattern='fan_in'").fetchone()[0] == "MULE"  # receiver is flagged
    for i in range(10):
        r = tx(conn, "BOSS", f"R{i}", 15_000, hrs=3 + i * 0.1)
    assert "sent money to 10 different accounts" in " ".join(r["reasons"])
    assert conn.execute("SELECT account_id FROM alerts WHERE pattern='fan_out'").fetchone()[0] == "BOSS"


def test_inject_ring_graph_and_reset(conn):
    c = TestClient(appmod.app)
    res = c.post("/api/demo/inject-ring").json()
    assert {(a["pattern"], a["level"]) for a in res["alerts"]} == {("cycle", "high"), ("structuring", "high")}
    g = c.get("/api/graph", params={"account_id": "RG01-S"}).json()
    assert {n["id"] for n in g["nodes"] if n["in_cycle"]} == {"RG01-S", "RG01-1", "RG01-2", "RG01-3", "RG01-4"}
    assert any(e["in_cycle"] for e in g["edges"]) and any(n["flagged"] for n in g["nodes"])
    assert c.post("/api/demo/inject-ring").json()["ring"] == "RG02-"  # a second click makes a fresh ring
    assert c.post("/api/demo/reset").status_code == 200
    assert c.get("/api/stats").json()["transactions"] == 0
    assert c.get("/api/graph", params={"account_id": "RG01-S"}).status_code == 404


def test_ai_layer_explains_unusual_account(conn, tmp_path, monkeypatch):
    for t in generate(inject=False):  # calm traffic defines what "normal" looks like
        score.ingest(conn, t)
    model = tmp_path / "m.joblib"
    assert ml.train(conn, model) > 100
    monkeypatch.setattr(ml, "MODEL_PATH", model)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    results = [score.ingest(conn, t) for t in ring(random.Random(0), "RG01-", now)]
    ai = [r for r in results for x in r["reasons"] if x.startswith("Unusual behaviour")]
    assert ai and "average transfer" in " ".join(ai[0]["reasons"])  # plain-language reason with real numbers
    assert not any(a == "ai_anomaly" for a in alert_patterns(conn))  # the AI layer never raises an alert on its own


def test_generated_traffic_is_calm_except_injected(conn):
    for t in generate():
        score.ingest(conn, t)
    assert set(alert_patterns(conn)) == {"structuring", "pass_through"}  # normal traffic raised nothing else
