
import pandas as pd

def top_flags(df_scored: pd.DataFrame, k: int = 100):
    cols = [c for c in df_scored.columns if c not in {"description"}]
    return df_scored[cols].head(k)
