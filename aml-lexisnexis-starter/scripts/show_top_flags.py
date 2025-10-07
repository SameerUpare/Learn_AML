# scripts/show_top_flags.py
# --- make 'src' importable when running the script directly ---
import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# -------------------------------------------------------------

import pandas as pd
pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 30)

from src.aml.data_ingest import load_transactions, load_lexisnexis, join_txn_lexisnexis
from src.aml.models.isolation_forest import train_and_score
from src.aml.evaluation import top_flags

# 1) Load + join (use your sample files or swap to big ones later)
txn = load_transactions('data/raw/transactions1.csv')
ln  = load_lexisnexis('data/raw/lexisnexis1.xml')
joined = join_txn_lexisnexis(txn, ln)

# 2) Score
scored, meta = train_and_score(joined)
print("FEATURES USED:", meta["features_used"])

# 3) Pick & format columns for view
cols = [
    "txn_id", "customer_id", "account_id", "datetime", "amount", "currency",
    "pep_flag", "sanctions_flag", "adverse_media_score", "risk_rating",
    "anomaly_score"
]
have = [c for c in cols if c in scored.columns]
view = scored[have].copy()

# numeric cleanup / rounding
for c in ("amount", "adverse_media_score", "risk_rating", "anomaly_score"):
    if c in view.columns:
        view[c] = pd.to_numeric(view[c], errors="coerce")
if "anomaly_score" in view.columns:
    view["anomaly_score"] = view["anomaly_score"].round(6)

# sort & preview
view = view.sort_values("anomaly_score", ascending=False)
top10 = view.head(10)
print(top10.to_string(index=False))

# ensure output dir
os.makedirs("data/processed", exist_ok=True)
top10.to_csv("data/processed/flagged_top10.csv", index=False)
view.to_csv("data/processed/flagged_all_scored.csv", index=False)
print("\nSaved: data/processed/flagged_top10.csv and data/processed/flagged_all_scored.csv")

# -------------------------------
# (2) QUICK THRESHOLD (95th pct)
# -------------------------------
import numpy as np
if "anomaly_score" in view.columns:
    thr = np.quantile(view["anomaly_score"].dropna(), 0.95)
    high = view[view["anomaly_score"] >= thr].copy()
    high.to_csv("data/processed/flagged_p95.csv", index=False)
    print(f"Threshold = {thr:.6f}  |  Saved: data/processed/flagged_p95.csv  |  Count: {len(high)}")

# -----------------------------------------
# (3) HISTOGRAM PNG (anomaly score dist.)
# -----------------------------------------
import matplotlib
# In headless environments, ensure a non-GUI backend:
# matplotlib.use("Agg")  # uncomment if you run this on a server/CI
import matplotlib.pyplot as plt

plt.figure()
view["anomaly_score"].hist(bins=30)
plt.title("Anomaly Score Distribution")
plt.xlabel("anomaly_score"); plt.ylabel("count")
plt.tight_layout()
plt.savefig("data/processed/anomaly_hist.png", dpi=150)
print("Saved: data/processed/anomaly_hist.png")
