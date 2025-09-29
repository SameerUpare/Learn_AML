
import os
import pandas as pd
from .config import C

RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "raw")

TXN_PATH = os.path.join(RAW_DIR, "transactions.csv")
LN_PATH = os.path.join(RAW_DIR, "lexisnexis.csv")

def validate_inputs():
    missing = []
    for p in [TXN_PATH, LN_PATH]:
        if not os.path.exists(p):
            missing.append(p)
    if missing:
        return {"ok": False, "missing": missing}
    # light schema checks
    t = pd.read_csv(TXN_PATH, nrows=5)
    l = pd.read_csv(LN_PATH, nrows=5)
    needed_t = [C.txn_id, C.customer_id, C.datetime, C.amount]
    needed_l = [C.ln_customer_id]
    return {
        "ok": all(col in t.columns for col in needed_t) and all(col in l.columns for col in needed_l),
        "txn_columns": list(t.columns),
        "ln_columns": list(l.columns),
    }

def join_txn_lexisnexis(txn_df: pd.DataFrame, ln_df: pd.DataFrame) -> pd.DataFrame:
    return txn_df.merge(ln_df, left_on=C.customer_id, right_on=C.ln_customer_id, how="left")
