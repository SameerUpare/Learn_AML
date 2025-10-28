
# ROADMAP

## Milestones
### M1 — Baseline pipeline (3–5 days)
- ✅ Repo scaffold & setup
- ✅ Data schema & config
- ✅ Join (transactions ⨯ lexisnexis)
- ✅ Isolation Forest baseline
- ✅ Export flagged transactions + simple charts

### M1.5 — Explainability & Reporting (2–3 days)
- SHAP (or simple contribution breakdown)
- Top drivers per flag (per transaction & per customer)
- Notebook to CSV/PDF summary

### M2 — Enrichment & Peer Groups (3–5 days)
- Peer group logic (by segment / country / MCC / channel)
- Country risk lookups
- Threshold tuning & calibration checklist

### M3 — Graph & Case Views (stretch)
- Simple network features (degree, transitivity, shortest paths to high-risk nodes)
- Minimal “investigator view” notebook (context block for a flagged customer)

## Data Contracts
- **transactions.csv** and **lexisnexis.csv** must have `customer_id` (or map provided).
- Dates must be ISO format; currencies normalized.

## Deliverables
- `/data/processed/flagged_transactions.csv`
- `/reports/phase1_summary.pdf` (optional, from notebooks)
- Plots: anomaly score distribution; customers by count of flags.
