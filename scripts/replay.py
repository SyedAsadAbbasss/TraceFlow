"""Stream generated transactions into the running API.
Usage: python scripts/replay.py [--delay 0.3] [--url http://localhost:8000] [--seed 42]
Replaying twice duplicates data: stop the API and delete traceflow.db first (a reset endpoint comes in phase 2).
"""
import argparse
import sys
import time

import httpx
from generate import generate

sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles choke on ₹
ap = argparse.ArgumentParser()
ap.add_argument("--delay", type=float, default=0.3)
ap.add_argument("--url", default="http://localhost:8000")
ap.add_argument("--seed", type=int, default=42)
a = ap.parse_args()

txs = generate(a.seed)
with httpx.Client(base_url=a.url, timeout=10) as client:
    for i, t in enumerate(txs, 1):
        r = client.post("/api/transactions", json=t)
        r.raise_for_status()
        j = r.json()
        if j["risk_score"] >= 40:
            print(f"[{i}/{len(txs)}] {j['level'].upper()} {j['risk_score']} {j['from_account']}: {'; '.join(j['reasons'])}")
        time.sleep(a.delay)
print(f"done: {len(txs)} transactions")
