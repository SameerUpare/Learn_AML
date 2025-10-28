# scripts/make_synthetic_data.py
# Generate big synthetic transactions + LexisNexis data from local reference files.
# Usage (from project root with venv):
#   python scripts/make_synthetic_data.py --n-customers 50000 --n-transactions 500000
# Outputs:
#   data/raw/transactions.2.csv
#   data/raw/lexisnexis.2.xml
# Optional: --write-extensionless to also write "trasaction.2" and "lexisnexis.2"

import os, sys, argparse, random, csv
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW = os.path.join(ROOT, "data", "raw")

def parse_args():
    ap = argparse.ArgumentParser(description="Make synthetic AML datasets from local references.")
    ap.add_argument("--raw-dir", default=RAW, help="Path to raw data dir (default: data/raw)")
    ap.add_argument("--ref-txn", default="transactions.csv", help="Reference transactions CSV filename")
    ap.add_argument("--ref-ln", default="lexisnexis.xml", help="Reference LexisNexis XML or CSV filename")
    ap.add_argument("--out-txn", default="transactions.2.csv", help="Output transactions CSV")
    ap.add_argument("--out-ln", default="lexisnexis.2.xml", help="Output LexisNexis XML")
    ap.add_argument("--n-customers", type=int, default=50000, help="Number of synthetic customers")
    ap.add_argument("--n-transactions", type=int, default=500000, help="Number of synthetic transactions")
    ap.add_argument("--chunksize", type=int, default=250_000, help="Chunk size for scanning reference CSV")
    ap.add_argument("--seed", type=int, default=42, help="Random seed")
    ap.add_argument("--write-extensionless", action="store_true", help='Also write "trasaction.2" and "lexisnexis.2" duplicates')
    return ap.parse_args()

def _norm_cols(cols):
    return [str(c).replace("\ufeff", "").strip() for c in cols]

def infer_txn_stats(ref_txn_path, chunksize=250_000):
    """Scan transactions.csv in chunks and build simple distributions."""
    cat_counts = {k: {} for k in ["currency","channel","counterparty_country","mcc"]}
    amounts = []
    tmin, tmax = None, None

    use_cols = ["txn_id","customer_id","account_id","datetime","amount","currency","channel",
                "counterparty_id","counterparty_country","mcc","description"]

    for chunk in pd.read_csv(ref_txn_path, chunksize=chunksize, dtype=str):
        chunk.columns = _norm_cols(chunk.columns)
        # Cast amount
        if "amount" in chunk.columns:
            amt = pd.to_numeric(chunk["amount"], errors="coerce").dropna()
            if not amt.empty:
                # reservoir-like sampling to limit memory
                if len(amounts) < 1_000_000:
                    amounts.extend(amt.values.tolist()[: max(0, 1_000_000 - len(amounts))])
        # datetime range
        if "datetime" in chunk.columns:
            dt = pd.to_datetime(chunk["datetime"], errors="coerce")
            if dt.notna().any():
                cmin, cmax = dt.min(), dt.max()
                tmin = cmin if tmin is None or (pd.notna(cmin) and cmin < tmin) else tmin
                tmax = cmax if tmax is None or (pd.notna(cmax) and cmax > tmax) else tmax
        # categories
        for col in cat_counts:
            if col in chunk.columns:
                s = chunk[col].astype(str).str.strip()
                s = s.replace({"": "NA"})
                vc = s.value_counts()
                for k, v in vc.items():
                    cat_counts[col][k] = cat_counts[col].get(k, 0) + int(v)

    # Fallbacks
    if not amounts:
        amounts = [1000, 5000, 10000, 25000, 50000]
    if tmin is None or tmax is None:
        tmin, tmax = pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31")

    # normalize probabilities

    cat_probs = {}
    for col, cnts in cat_counts.items():
        if not cnts:
            # no data seen for this column — default to single NA with prob 1
            keys = ["NA"]
            probs = np.array([1.0])
        else:
            keys = list(cnts.keys())
            weights = np.array([cnts[k] for k in keys], dtype=float)
            total = weights.sum()
            if total <= 0:
                keys = ["NA"]
                probs = np.array([1.0])
            else:
                probs = weights / total
        cat_probs[col] = (keys, probs)
    return {
        "amounts": np.array(amounts, dtype=float),
        "tmin": pd.Timestamp(tmin),
        "tmax": pd.Timestamp(tmax),
        "cats": cat_probs,
        "use_cols": use_cols,
    }

def infer_ln_stats(ref_ln_path):
    """Scan LexisNexis XML (or CSV) and build simple distributions."""
    ext = os.path.splitext(ref_ln_path)[1].lower()
    pep_vals, sanc_vals, ams_vals, rr_vals, kyc_dates = [], [], [], [], []

    def coerce01(x):
        x = str(x).strip().lower()
        if x in {"1","y","yes","true"}: return 1
        return 0

    if ext == ".xml":
        # stream XML
        context = ET.iterparse(ref_ln_path, events=("end",))
        for event, elem in context:
            if elem.tag.lower().endswith("customer"):
                data = {child.tag: (child.text or "").strip() for child in elem}
                pep_vals.append(coerce01(data.get("pep_flag", 0)))
                sanc_vals.append(coerce01(data.get("sanctions_flag", 0)))
                try:
                    ams_vals.append(float(data.get("adverse_media_score", "0")))
                except:
                    pass
                try:
                    rr_vals.append(int(float(data.get("risk_rating", "0"))))
                except:
                    pass
                try:
                    kyc_dates.append(pd.to_datetime(data.get("kyc_last_review_date"), errors="coerce"))
                except:
                    pass
                elem.clear()
        del context
    else:
        # CSV
        for chunk in pd.read_csv(ref_ln_path, chunksize=200_000):
            chunk.columns = _norm_cols(chunk.columns)
            if "pep_flag" in chunk: pep_vals += [coerce01(v) for v in chunk["pep_flag"].values]
            if "sanctions_flag" in chunk: sanc_vals += [coerce01(v) for v in chunk["sanctions_flag"].values]
            if "adverse_media_score" in chunk:
                ams_vals += pd.to_numeric(chunk["adverse_media_score"], errors="coerce").dropna().tolist()
            if "risk_rating" in chunk:
                rr_vals += pd.to_numeric(chunk["risk_rating"], errors="coerce").dropna().astype(int).tolist()
            if "kyc_last_review_date" in chunk:
                kyc_dates += pd.to_datetime(chunk["kyc_last_review_date"], errors="coerce").dropna().tolist()

    # fallbacks
    if not pep_vals: pep_vals = [0,0,0,1]
    if not sanc_vals: sanc_vals = [0,0,1]
    if not ams_vals: ams_vals = [0,5,10,20,40]
    if not rr_vals: rr_vals = [1,2,3,4,5]
    kd = [d for d in kyc_dates if pd.notna(d)]
    kmin = min(kd) if kd else pd.Timestamp("2024-01-01")
    kmax = max(kd) if kd else pd.Timestamp("2025-12-31")

    # probabilities
    pep_p = np.mean(pep_vals)
    sanc_p = np.mean(sanc_vals)
    rr_keys, rr_counts = np.unique(rr_vals, return_counts=True)
    rr_probs = rr_counts / rr_counts.sum()

    return {
        "pep_p": float(pep_p),
        "sanc_p": float(sanc_p),
        "ams_vals": np.array(ams_vals, dtype=float),
        "rr_keys": rr_keys.tolist(),
        "rr_probs": rr_probs,
        "kyc_min": pd.Timestamp(kmin),
        "kyc_max": pd.Timestamp(kmax),
    }

def rand_date(start, end):
    delta = (end - start).total_seconds()
    r = random.random() * delta
    return start + timedelta(seconds=r)

def synthesize_lexisnexis(n_customers, ln_stats, out_xml_path):
    os.makedirs(os.path.dirname(out_xml_path), exist_ok=True)
    with open(out_xml_path, "w", encoding="utf-8", newline="") as f:
        f.write("<root>\n")
        for i in range(1, n_customers+1):
            cid = f"C{i:07d}"
            pep = 1 if random.random() < ln_stats["pep_p"] else 0
            sanc = 1 if random.random() < ln_stats["sanc_p"] else 0
            ams = float(np.random.choice(ln_stats["ams_vals"])) if ln_stats["ams_vals"].size else 0.0
            rr = int(np.random.choice(ln_stats["rr_keys"], p=ln_stats["rr_probs"]))
            kyc_dt = rand_date(ln_stats["kyc_min"].to_pydatetime(), ln_stats["kyc_max"].to_pydatetime()).date()
            f.write(
                "  <customer>\n"
                f"    <customer_id>{cid}</customer_id>\n"
                f"    <pep_flag>{pep}</pep_flag>\n"
                f"    <sanctions_flag>{sanc}</sanctions_flag>\n"
                f"    <adverse_media_score>{int(ams)}</adverse_media_score>\n"
                f"    <risk_rating>{rr}</risk_rating>\n"
                f"    <kyc_last_review_date>{kyc_dt}</kyc_last_review_date>\n"
                "  </customer>\n"
            )
        f.write("</root>\n")

def synthesize_transactions(n_txn, txn_stats, out_csv_path, customers, accounts_per_customer=(1,3)):
    os.makedirs(os.path.dirname(out_csv_path), exist_ok=True)
    # choose accounts per customer
    acct_map = {}
    for cid in customers:
        n_accts = random.randint(accounts_per_customer[0], accounts_per_customer[1])
        acct_map[cid] = [f"A{cid[1:]}_{j}" for j in range(1, n_accts+1)]

    # category choices
    def sampler(key):
        keys, probs = txn_stats["cats"].get(key, (["NA"], np.array([1.0])))
        return np.random.choice(keys, p=probs)

    with open(out_csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["txn_id","customer_id","account_id","datetime","amount","currency","channel",
                    "counterparty_id","counterparty_country","mcc","description"])
        for i in range(1, n_txn+1):
            cid = random.choice(customers)
            aid = random.choice(acct_map[cid])
            ts = rand_date(txn_stats["tmin"].to_pydatetime(), txn_stats["tmax"].to_pydatetime())
            amt = float(np.random.choice(txn_stats["amounts"]))
            curr = sampler("currency")
            chan = sampler("channel")
            ctry = sampler("counterparty_country")
            mcc = sampler("mcc")
            cp = f"CP{random.randint(100000, 999999)}"
            desc = "synthetic txn"
            w.writerow([f"T{i:012d}", cid, aid, ts.isoformat(timespec="seconds"), int(round(amt)), curr, chan, cp, ctry, mcc, desc])

def main():
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)

    ref_txn_path = os.path.join(args.raw_dir, args.ref_txn)
    ref_ln_path  = os.path.join(args.raw_dir, args.ref_ln)
    out_txn_path = os.path.join(args.raw_dir, args.out_txn)
    out_ln_path  = os.path.join(args.raw_dir, args.out_ln)

    if not os.path.exists(ref_txn_path):
        print(f"Reference transactions file not found: {ref_txn_path}", file=sys.stderr); sys.exit(1)
    if not os.path.exists(ref_ln_path):
        print(f"Reference LexisNexis file not found: {ref_ln_path}", file=sys.stderr); sys.exit(1)

    print("Scanning reference transactions (chunked)…")
    txn_stats = infer_txn_stats(ref_txn_path, chunksize=args.chunksize)
    print("Scanning reference LexisNexis (stream)…")
    ln_stats = infer_ln_stats(ref_ln_path)

    print(f"Synthesizing {args.n_customers:,} customers → {out_ln_path}")
    customers = [f"C{i:07d}" for i in range(1, args.n_customers+1)]
    synthesize_lexisnexis(args.n_customers, ln_stats, out_ln_path)

    print(f"Synthesizing {args.n_transactions:,} transactions → {out_txn_path}")
    synthesize_transactions(args.n_transactions, txn_stats, out_txn_path, customers)

    if args.write_extensionless:
        # Optional duplicates without extensions (note: loader expects .csv/.xml)
        extless_txn = os.path.join(args.raw_dir, "trasaction.2")      # spelling per request
        extless_ln  = os.path.join(args.raw_dir, "lexisnexis.2")
        try:
            with open(out_txn_path, "rb") as src, open(extless_txn, "wb") as dst: dst.write(src.read())
            with open(out_ln_path, "rb") as src, open(extless_ln, "wb") as dst: dst.write(src.read())
            print(f"Wrote extensionless duplicates: {extless_txn}, {extless_ln}")
        except Exception as e:
            print(f"Could not write extensionless duplicates: {e}", file=sys.stderr)

    print("Done.")

if __name__ == "__main__":
    main()
