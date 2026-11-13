"""Train the AI layer on calm synthetic traffic and save backend/models/iforest.joblib.
Run from the repo root: python scripts/train.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from generate import generate

from backend import db, ml, score

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
    db.PATH = Path(tmp) / "train.db"            # throwaway database, not traceflow.db
    ml.MODEL_PATH = Path(tmp) / "none.joblib"   # no model yet while we ingest the training data
    conn = db.connect()
    for t in generate(inject=False):
        score.ingest(conn, t)
    n = ml.train(conn, Path(__file__).resolve().parent.parent / "backend" / "models" / "iforest.joblib")
    conn.close()
print(f"trained on {n} accounts")
