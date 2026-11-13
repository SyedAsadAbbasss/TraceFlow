"""Synthetic INR traffic: ~200 accounts of normal behaviour + injected laundering patterns.
Seeded, so runs are repeatable. History ends yesterday so live demo traffic ("now") comes after it.
Run `python scripts/generate.py` for a summary.
"""
import random
from datetime import datetime, timedelta

FMT = "%Y-%m-%dT%H:%M:%S"
FIRST = "Aarav Vivaan Aditya Ishaan Kabir Rohan Arjun Neha Priya Ananya Diya Kavya Meera Riya Sana Imran Farah Karan Pooja Sneha".split()
LAST = "Sharma Verma Iyer Nair Khan Patel Reddy Gupta Singh Das Mehta Joshi Rao Bose Kapoor Malik".split()
SHOPS = ["Kirana", "Chai Point", "Fresh Mart", "Fuel Stop", "Pharmacy", "Bookstore", "Metro Recharge"]


def _tx(f, t, amount, ts, channel):
    return dict(from_account=f, to_account=t, amount=round(amount, 2), channel=channel, ts=ts.strftime(FMT))


def normal(rng, people, merchants, employers, start, days):
    txs = []
    for i, p in enumerate(people):  # salary day 1, 15 min apart per employer (a payroll run isn't a burst)
        salary = rng.choice([*range(25, 45), *range(50, 91)]) * 1000  # skips ₹45k–₹50k: that's structuring territory
        txs.append(_tx(employers[i % len(employers)], p, salary,
                       start + timedelta(hours=6, minutes=15 * (i // len(employers))), "NEFT"))
        txs.append(_tx(p, rng.choice(merchants), rng.uniform(800, 4000),
                       start + timedelta(days=1, hours=rng.uniform(8, 22)), "NEFT"))  # monthly bill
    for d in range(days):
        for p in people:
            for _ in range(rng.choice([0, 1, 1, 2, 3])):
                ts = start + timedelta(days=d, hours=rng.uniform(8, 22))
                if rng.random() < 0.8:  # shop
                    txs.append(_tx(p, rng.choice(merchants), min(rng.lognormvariate(6, 0.8), 8000),
                                   ts, rng.choice(["UPI", "UPI", "CARD"])))
                else:  # friend
                    friend = rng.choice([x for x in people if x != p])
                    txs.append(_tx(p, friend, min(rng.lognormvariate(6.5, 0.8), 8000), ts, rng.choice(["UPI", "IMPS"])))
    return txs


def structuring(rng, src, dests, start):
    """5 transfers just under ₹50k spread over ~8 hours."""
    return [_tx(src, d, rng.uniform(45_000, 49_900), start + timedelta(hours=2 * i + rng.random()), "IMPS")
            for i, d in enumerate(dests[:5])]


def pass_through(rng, sources, mule, dests, start):
    """₹3L arrives in two chunks, ~92% leaves again within 3 hours."""
    ins = [_tx(s, mule, 150_000, start + timedelta(minutes=20 * i), "NEFT") for i, s in enumerate(sources[:2])]
    outs = [_tx(mule, d, 69_000, start + timedelta(hours=1 + 0.6 * i), "IMPS") for i, d in enumerate(dests[:4])]
    return ins + outs


def generate(seed=42, days=3, n=200, inject=True):
    rng = random.Random(seed)
    ids = [f"AC{i:04d}" for i in range(1, n + 1)]
    merchants, employers, people = ids[:20], ids[20:30], ids[30:]
    names = {i: f"{rng.choice(SHOPS)} {i[-4:]}" for i in merchants}
    names |= {i: f"{rng.choice(LAST)} Industries Pvt Ltd" for i in employers}
    names |= {i: f"{rng.choice(FIRST)} {rng.choice(LAST)}" for i in people}
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    txs = normal(rng, people, merchants, employers, start, days)
    if inject:
        bad = rng.sample(people, 14)
        last_day = start + timedelta(days=days - 1)
        txs += structuring(rng, bad[0], bad[1:6], last_day + timedelta(hours=10))
        txs += pass_through(rng, bad[6:8], bad[8], bad[9:13], last_day + timedelta(hours=12))
    txs.sort(key=lambda t: t["ts"])
    for t in txs:
        t["from_name"], t["to_name"] = names[t["from_account"]], names[t["to_account"]]
    return txs


if __name__ == "__main__":
    txs = generate()
    print(f"{len(txs)} transactions, {txs[0]['ts']} .. {txs[-1]['ts']}")
    assert len(txs) > 500 and generate() == txs, "generator must be repeatable"
