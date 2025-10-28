# scripts/show_top_flags.py
# --- make 'src' importable when running the script directly ---
import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# -------------------------------------------------------------

import os
import argparse
import pandas as pd
pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 30)

from src.aml.data_ingest import load_transactions, load_lexisnexis, join_txn_lexisnexis
from src.aml.models.isolation_forest import train_and_score
parser = argparse.ArgumentParser()
parser.add_argument("--max_rows", type=int, default=None)
args = parser.parse_args()
# 1) Load transactions
txn_path = 'data/raw/transactions.csv'
txn = load_transactions(txn_path)

# 1a) OPTIONALLY: join with LexisNexis enrichment if available
#    Un-comment the two lines below to enable LN merge.
# ln_path = 'data/raw/lexisnexis.synthetic.xml'
# ln = load_lexisnexis(ln_path)

# Build the training table 'joined'
# If LN is enabled above, do: joined = join_txn_lexisnexis(txn, ln)
joined = txn  # default: score transactions alone

# 2) Train + score
scored, meta = train_and_score(joined)
print("FEATURES USED:", meta.get("features_used"))

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
if "anomaly_score" in view.columns:
    view = view.sort_values("anomaly_score", ascending=False)
top10 = view.head(10)
print(top10.to_string(index=False))

# ensure output dirs
os.makedirs("data/processed", exist_ok=True)
os.makedirs("reports", exist_ok=True)
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
# In headless environments (e.g., CI), use a non-GUI backend:
# matplotlib.use("Agg")
import matplotlib.pyplot as plt

if "anomaly_score" in view.columns:
    plt.figure()
    view["anomaly_score"].hist(bins=30)
    plt.title("Anomaly Score Distribution")
    plt.xlabel("anomaly_score"); plt.ylabel("count")
    plt.tight_layout()
    plt.savefig("reports/anomaly_hist.png", dpi=150)
    print("Saved: reports/anomaly_hist.png")
