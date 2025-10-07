import pandas as pd
from .data_ingest import load_transactions, load_lexisnexis, join_txn_lexisnexis
from .models.isolation_forest import train_and_score
from .evaluation import top_flags

def run_pipeline(
    txn_path: str = None,
    ln_path: str = None,
    out_csv: str = "data/processed/flagged_transactions.csv",
    max_rows: int | None = None,
    random_state: int = 42,
):
    txn = load_transactions(txn_path)
    ln = load_lexisnexis(ln_path)
    if max_rows is not None and len(txn) > max_rows:
        txn = txn.sample(n=max_rows, random_state=random_state)
    joined = join_txn_lexisnexis(txn, ln)
    scored, meta = train_and_score(joined)
    flagged = top_flags(scored, k=200)
    flagged.to_csv(out_csv, index=False)
    return {"out_csv": out_csv, **meta}
