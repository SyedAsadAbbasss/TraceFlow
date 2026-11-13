"""Layer 2: graph AML on a sliding window of significant transfers.

Only transfers >= SIGNIFICANT count: without that floor, everyday small payments make merchants
look like fan-in mules. Thresholds are tunable assumptions, not regulatory values.
Known false positive: a big payroll run (>= 8 salaries in a day) looks like fan-out.
"""
import networkx as nx

from .rules import ago, inr

SIGNIFICANT = 10_000
WINDOW_H = 48
FAN = 8  # distinct counterparties within 24 h


def window_graph(conn, end, hours=WINDOW_H):
    """DiGraph of accounts; edge = latest significant transfer between the pair in the window."""
    G = nx.DiGraph()
    for r in conn.execute("SELECT from_account, to_account, amount, ts FROM transactions "
                          "WHERE amount>=? AND ts>? AND ts<=? ORDER BY id", (SIGNIFICANT, ago(end, hours), end)):
        G.add_edge(r["from_account"], r["to_account"], amount=r["amount"], ts=r["ts"])
    return G


def cycles_through(G, f, t):
    """Cycles of 3-6 accounts using edge f->t: a path t->...->f of 3-6 accounts. Bounded, never the whole graph."""
    if f not in G or t not in G:
        return []
    return [p for p in nx.all_simple_paths(G, t, f, cutoff=5) if len(p) >= 3]  # ponytail: fine for sparse windows


def check(conn, tx):
    """Hits for the transfer just inserted: (pattern, points, reason). fan_in belongs to the receiver."""
    if tx["amount"] < SIGNIFICANT:
        return []
    f, t, ts, hits = tx["from_account"], tx["to_account"], tx["ts"], []
    G = window_graph(conn, ts)
    cycles = cycles_through(G, f, t)
    if cycles:
        best = min(cycles, key=len)
        path = [f] + best  # f -> t -> ... -> f
        hop = min(G[a][b]["amount"] for a, b in zip(path, path[1:]))
        extra = f"; {len(cycles)} loops pass through this transfer" if len(cycles) > 1 else ""
        hits.append(("cycle", 60, f"Money returned to its origin: {' → '.join(path)} ({len(best)} accounts, "
                                  f"at least {inr(hop)} per hop within {WINDOW_H} hours{extra})"))
    since = ago(ts, 24)
    n, total = conn.execute("SELECT COUNT(DISTINCT from_account), SUM(amount) FROM transactions "
                            "WHERE to_account=? AND amount>=? AND ts>? AND ts<=?", (t, SIGNIFICANT, since, ts)).fetchone()
    if n >= FAN:
        hits.append(("fan_in", 50, f"{n} different accounts sent money to this account within 24 hours (total {inr(total)})"))
    n, total = conn.execute("SELECT COUNT(DISTINCT to_account), SUM(amount) FROM transactions "
                            "WHERE from_account=? AND amount>=? AND ts>? AND ts<=?", (f, SIGNIFICANT, since, ts)).fetchone()
    if n >= FAN:
        hits.append(("fan_out", 50, f"This account sent money to {n} different accounts within 24 hours (total {inr(total)})"))
    return hits


def view(conn, account_id, end, hours):
    """Nodes/edges within 3 hops of account_id; accounts and edges on a 3-6 account cycle are marked in_cycle."""
    G = window_graph(conn, end, hours)
    G.add_node(account_id)
    ego = nx.ego_graph(G, account_id, radius=3, undirected=True)
    cycles = [c for c in nx.simple_cycles(ego, length_bound=6) if len(c) >= 3]
    cycle_edges = {(c[i], c[(i + 1) % len(c)]) for c in cycles for i in range(len(c))}
    cycle_nodes = {a for c in cycles for a in c}
    ids = list(ego.nodes)
    marks = ",".join("?" * len(ids))
    names = dict(conn.execute(f"SELECT id, name FROM accounts WHERE id IN ({marks})", ids).fetchall())
    flagged = {r[0] for r in conn.execute(f"SELECT DISTINCT account_id FROM alerts WHERE status!='dismissed' "
                                          f"AND account_id IN ({marks})", ids)}
    return {
        "account_id": account_id,
        "min_amount": SIGNIFICANT,
        "nodes": [{"id": a, "name": names.get(a, a), "focus": a == account_id, "flagged": a in flagged,
                   "in_cycle": a in cycle_nodes} for a in ids],
        "edges": [{"from": u, "to": v, "amount": d["amount"], "in_cycle": (u, v) in cycle_edges}
                  for u, v, d in ego.edges(data=True)],
        "cycles": cycles,
    }
