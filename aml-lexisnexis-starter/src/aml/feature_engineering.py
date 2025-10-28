
import pandas as pd
import numpy as np
from .config import C

def add_basic_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # parse time
    out["_dt"] = pd.to_datetime(out[C.datetime], errors="coerce")
    out["hour"] = out["_dt"].dt.hour
    out["day"] = out["_dt"].dt.day
    out["month"] = out["_dt"].dt.month
    out["dow"] = out["_dt"].dt.dayofweek

    # velocity features by customer
    out = out.sort_values([C.customer_id, "_dt"])
    out["amt_z_by_customer"] = out.groupby(C.customer_id)[C.amount].transform(
        lambda s: (s - s.mean()) / (s.std(ddof=0) + 1e-6)
    )
    out["amt_rolling_mean_7"] = out.groupby(C.customer_id)[C.amount].transform(
        lambda s: s.rolling(7, min_periods=1).mean()
    )

    # simple risk flags numeric
    for flag in ["pep_flag", "sanctions_flag"]:
        if flag in out.columns:
            out[flag] = out[flag].map({True: 1, "True": 1, 1: 1, "Y": 1, "Yes": 1}).fillna(0).astype(int)

    return out
