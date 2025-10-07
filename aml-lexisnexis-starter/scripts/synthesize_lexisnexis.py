# scripts/synthesize_lexisnexis.py
# Create a synthetic LexisNexis KYC dataset (XML and/or CSV).
# You can generate customer_ids from your transactions file for high join coverage.

import os, sys, argparse, random
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

def parse_args():
    ap = argparse.ArgumentParser("Synthesize LexisNexis KYC data")
    ap.add_argument("--from-transactions", default=None,
                    help="Optional path to transactions CSV to extract customer_ids from")
    ap.add_argument("--n-customers", type=int, default=10000,
                    help="Number of customers to generate (ignored if --from-transactions is provided)")
    ap.add_argument("--out-xml", default="data/raw/lexisnexis.synthetic.xml",
                    help="Output XML path")
    ap.add_argument("--out-csv", default=None,
                    help="Optional: also write CSV to this path")
    ap.add_argument("--seed", type=int, default=42, help="Random seed")

    # Distributions (tweak as needed)
    ap.add_argument("--pep-rate", type=float, default=0.08, help="Probability of PEP=1")
    ap.add_argument("--sanctions-rate", type=float, default=0.03, help="Probability of sanctions=1")
    ap.add_argument("--rr-dist", type=str, default="0.25,0.30,0.25,0.15,0.05",
                    help="Risk rating probs for 1..5 (comma-separated)")
    ap.add_argument("--ams-mean", type=float, default=15.0, help="Adverse media score mean")
    ap.add_argument("--ams-std", type=float, default=10.0, help="Adverse media score stddev")
    ap.add_argument("--kyc-min", type=str, default="2024-01-01", help="Min KYC date (YYYY-MM-DD)")
    ap.add_argument("--kyc-max", type=str, default="2025-12-31", help="Max KYC date (YYYY-MM-DD)")
    return ap.parse_args()

def rand_date(start_dt: datetime, end_dt: datetime) -> datetime:
    span = (end_dt - start_dt).total_seconds()
    return start_dt + timedelta(seconds=random.random() * span)

def get_customer_ids(args) -> list[str]:
    if args.from_transactions:
        # stream unique customer_ids from big CSV
        want = args.n_customers  # if user passes both, this is a cap
        seen = set()
        for chunk in pd.read_csv(args.from_transactions, usecols=["customer_id"], chunksize=500_000, dtype=str):
            for cid in chunk["customer_id"].dropna().astype(str).str.strip().values:
                if cid:
                    seen.add(cid)
                if want and len(seen) >= want:
                    break
            if want and len(seen) >= want:
                break
        if not seen:
            raise ValueError(f"No customer_id values found in {args.from_transactions}")
        return sorted(seen)
    # fallback: C0000001...C00XXXXX
    return [f"C{i:07d}" for i in range(1, args.n_customers + 1)]

def synthesize(args):
    random.seed(args.seed); np.random.seed(args.seed)

    # parse distributions
    rr_probs = np.array([float(x) for x in args.rr_dist.split(",")], dtype=float)
    if rr_probs.size != 5 or not np.isclose(rr_probs.sum(), 1.0):
        raise ValueError("--rr-dist must be 5 comma-separated probs that sum to 1.0")

    kyc_min = datetime.fromisoformat(args.kyc_min)
    kyc_max = datetime.fromisoformat(args.kyc_max)

    # choose ids
    customer_ids = get_customer_ids(args)

    # draw attributes
    pep = np.random.binomial(1, args.pep_rate, size=len(customer_ids)).astype(int)
    sanc = np.random.binomial(1, args.sanctions_rate, size=len(customer_ids)).astype(int)
    rr = np.random.choice([1,2,3,4,5], size=len(customer_ids), p=rr_probs).astype(int)
    ams = np.maximum(0, np.rint(np.random.normal(args.ams_mean, args.ams_std, size=len(customer_ids)))).astype(int)

    # dates
    kyc_dt = [rand_date(kyc_min, kyc_max).date().isoformat() for _ in customer_ids]

    df = pd.DataFrame({
        "customer_id": customer_ids,
        "pep_flag": pep,
        "sanctions_flag": sanc,
        "adverse_media_score": ams,
        "risk_rating": rr,
        "kyc_last_review_date": kyc_dt,
    })

    # write XML
    os.makedirs(os.path.dirname(args.out_xml), exist_ok=True)
    with open(args.out_xml, "w", encoding="utf-8") as f:
        f.write("<root>\n")
        for row in df.itertuples(index=False):
            f.write(
                "  <customer>\n"
                f"    <customer_id>{row.customer_id}</customer_id>\n"
                f"    <pep_flag>{int(row.pep_flag)}</pep_flag>\n"
                f"    <sanctions_flag>{int(row.sanctions_flag)}</sanctions_flag>\n"
                f"    <adverse_media_score>{int(row.adverse_media_score)}</adverse_media_score>\n"
                f"    <risk_rating>{int(row.risk_rating)}</risk_rating>\n"
                f"    <kyc_last_review_date>{row.kyc_last_review_date}</kyc_last_review_date>\n"
                "  </customer>\n"
            )
        f.write("</root>\n")

    # optional CSV output
    if args.out_csv:
        os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)
        df.to_csv(args.out_csv, index=False)

    print(f"Wrote {len(df):,} customers → {args.out_xml}" + (f" and {args.out_csv}" if args.out_csv else ""))
    return 0

if __name__ == "__main__":
    sys.exit(synthesize(parse_args()))
