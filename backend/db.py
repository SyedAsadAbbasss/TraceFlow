import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATH = HERE.parent / "traceflow.db"  # tests monkeypatch this


def connect():
    """New connection; creates the tables if missing (schema is IF NOT EXISTS)."""
    c = sqlite3.connect(PATH, timeout=10, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    c.executescript((HERE / "schema.sql").read_text(encoding="utf-8"))
    return c
