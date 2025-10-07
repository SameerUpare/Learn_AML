
import pandas as pd

def top_flags(df_scored: pd.DataFrame, k: int = 100):
    cols = [c for c in df_scored.columns if c not in {"description"}]
    if "anomaly_score" in df_scored.columns:
        # Efficient top-k without full sort to reduce memory
        topk = df_scored.nlargest(k, columns=["anomaly_score"])  # uses partial sort
        return topk[cols]
    return df_scored[cols].head(k)
