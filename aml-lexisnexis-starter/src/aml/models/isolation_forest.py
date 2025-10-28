
from sklearn.ensemble import IsolationForest
import pandas as pd
from ..feature_engineering import add_basic_features
from ..config import C

FEATURES = [
    C.amount, "hour", "dow", "amt_z_by_customer", "amt_rolling_mean_7",
    "pep_flag", "sanctions_flag", "adverse_media_score", "risk_rating"
]

def train_and_score(df: pd.DataFrame, random_state: int = 42):
    df_fe = add_basic_features(df)
    # Select numeric features safely and reduce memory footprint
    use_cols = [c for c in FEATURES if c in df_fe.columns]
    X = (
        df_fe[use_cols]
        .select_dtypes(include="number")
        .astype("float32")
        .fillna(0.0)
    )
    iso = IsolationForest(n_estimators=200, contamination="auto", random_state=random_state)
    iso.fit(X)
    scores = -iso.score_samples(X)  # higher = more anomalous
    # Write scores in-place to avoid copying large DataFrames
    df_fe.loc[:, "anomaly_score"] = pd.Series(scores, index=df_fe.index, dtype="float32")
    # Return unsorted to avoid expensive global sort on very large datasets; downstream will pick top-k efficiently
    return df_fe, {"features_used": use_cols}
