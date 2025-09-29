
import pandas as pd
from .data_ingest import join_txn_lexisnexis
from .models.isolation_forest import train_and_score
from .evaluation import top_flags

def run_pipeline(txn_csv: str, ln_csv: str, out_csv: str = "data/processed/flagged_transactions.csv"):
    txn = pd.read_csv(txn_csv)
    ln = pd.read_csv(ln_csv)
    joined = join_txn_lexisnexis(txn, ln)
    scored, meta = train_and_score(joined)
    flagged = top_flags(scored, k=200)
    flagged.to_csv(out_csv, index=False)
    return {"out_csv": out_csv, **meta}
