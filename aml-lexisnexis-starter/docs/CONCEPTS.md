# Project Concepts Overview

This document summarizes the key concepts implemented so far across Software Engineering, Python, AI/ML, and AML in this repository.

## Architecture & Code Flow
- Entry points (CLI): `scripts/show_top_flags.py` (end-to-end scoring), `scripts/make_synthetic_data.py` (data generation)
  - Why it matters: clear, reproducible commands to run core workflows.
  - How we use it: one command to generate data; one to score/export results.
- Core modules under `src/aml/`:
  - `data_ingest.py` → load CSV/XML, normalize columns, map schemas, join transactions↔lexisnexis
    - Why it matters: consistent inputs prevent downstream errors and mismatches.
    - How we use it: normalize headers, map non-standard files, coerce join keys.
  - `feature_engineering.py` → time features, per-customer z-score, rolling means, flag encoding
    - Why it matters: transforms raw data into predictive signals for models.
    - How we use it: derive `hour/dow`, `amt_z_by_customer`, and rolling trends.
  - `models/isolation_forest.py` → train Isolation Forest, compute `anomaly_score`
    - Why it matters: unsupervised detection finds anomalies without labels.
    - How we use it: fit on numeric features and emit a continuous risk score.
  - `evaluation.py` → efficient top-k (`nlargest`) selection for memory safety
    - Why it matters: avoids full sorts that can exhaust memory on big data.
    - How we use it: pick top-k anomalies directly by `anomaly_score`.
  - `visualize.py` → histogram plotting helper
    - Why it matters: quick visual inspection of score distributions.
    - How we use it: produce a PNG chart for analyst review.
  - `config.py` → canonical column names (`C`) and XML paths (`X`)
    - Why it matters: central schema config avoids hard-coded strings everywhere.
    - How we use it: reference `C`/`X` across modules for consistency.

High-level flow (show_top_flags):
1) Load sources → 2) Join on `customer_id` → 3) Feature engineering → 4) Isolation Forest scoring → 5) Select top-k → 6) Save CSVs/plots

## Software Engineering
- Modular architecture: code under `src/aml/` by concern; entry scripts in `scripts/`.
  - Why it matters: easier maintenance, testing, and ownership per module.
  - How we use it: ingestion/features/models/eval/viz are cleanly separated.
- Separation of concerns:
  - `data_ingest.py`: CSV/XML loading, column normalization, streaming joins.
    - Why it matters: I/O logic stays decoupled from modeling logic.
    - How we use it: supports messy headers and large files with chunking.
  - `feature_engineering.py`: deterministic raw→feature transformations.
    - Why it matters: reproducible, explainable feature sets for models.
    - How we use it: compute calendar, z-score, and rolling features.
  - `models/isolation_forest.py`: model training and scoring.
    - Why it matters: isolates the ML algorithm from the rest of the pipeline.
    - How we use it: defines features and returns an `anomaly_score`.
  - `evaluation.py`, `visualize.py`: reporting utilities.
    - Why it matters: standard outputs speed up triage and validation.
    - How we use it: produce top lists and quick charts.
- Configuration: centralized field names and XPaths via `src/aml/config.py` (`C`, `X`).
  - Why it matters: single source of truth for schemas and XML structure.
  - How we use it: all modules refer to `C`/`X` instead of literals.
- Scalability: chunked CSV reads; `stream_left_join_to_csv` to keep RAM low.
  - Why it matters: prevents crashes and enables larger-than-RAM datasets.
  - How we use it: process transactions in chunks; keep LN in memory.
- Reproducibility: seeds, `requirements.txt`, deterministic features.
  - Why it matters: consistent results across runs and environments.
  - How we use it: seed RNGs and lock dependencies.
- CLI tooling: `scripts/show_top_flags.py` (end-to-end); `scripts/make_synthetic_data.py` (data generator).
  - Why it matters: simple commands for common workflows.
  - How we use it: run E2E scoring and synthetic data creation from terminal.

## Python Practices
- Pandas workflows: `groupby().transform(...)`, rolling windows, datetime parsing, safe numeric casting.
  - Why it matters: robust transformations on heterogeneous tabular data.
  - How we use it: compute per-customer stats and rolling aggregates safely.
- Defensive I/O: BOM/header cleanup, flexible column resolution, XML parsing with `read_xml` fallback to `ElementTree`.
  - Why it matters: real-world files are messy; loaders must be tolerant.
  - How we use it: normalize headers, resolve keys, and parse XML resiliently.
- Clear function boundaries and return payloads (e.g., `{"features_used": ...}`).
  - Why it matters: traceability and testability of pipeline steps.
  - How we use it: models report selected features along with outputs.
- `argparse`-based command-line interfaces.
  - Why it matters: parameterized, reproducible runs in different environments.
  - How we use it: pass sizes, seeds, and paths to scripts.

## AI/ML Concepts
- Unsupervised anomaly detection: Isolation Forest produces `anomaly_score` (higher = more anomalous).
  - Why it matters: detects unusual behavior without labeled fraud examples.
  - How we use it: fit on engineered features and score each transaction.
- Feature engineering for models:
  - Temporal: `hour`, `day`, `month`, `dow` from timestamps.
    - Why it matters: captures behavioral patterns tied to time.
    - How we use it: enrich rows with calendar-derived fields.
  - Customer-relative normalization: `amt_z_by_customer`.
    - Why it matters: flags deviations from each customer’s baseline.
    - How we use it: compute z-scores per customer group.
  - Velocity: `amt_rolling_mean_7` (recent trend).
    - Why it matters: highlights short-term spikes/drops.
    - How we use it: rolling mean over recent transactions per customer.
  - Risk: encoded `pep_flag`, `sanctions_flag`, plus `adverse_media_score`, `risk_rating` if present.
    - Why it matters: integrates external risk context into features.
    - How we use it: map common truthy values to 0/1 and include scores.
- Evaluation/reporting: rank by `anomaly_score`, export top-k, plot distribution.
  - Why it matters: turns model outputs into actionable investigative lists.
  - How we use it: select top-k via `nlargest` and plot a histogram.

Memory-aware changes:
- Avoid full DataFrame sorts on very large data; use `nlargest` (partial sort) for top-k.
  - Why it matters: reduces memory footprint and prevents allocation errors.
  - How we use it: keep results unsorted; pick top-k directly on scores.

## AML Concepts
- Customer baselining: “unusual for this customer” via per-customer z-scores.
  - Why it matters: reduces false positives from natural spend differences.
  - How we use it: compare amounts to each customer’s own distribution.
- Velocity/recency: rolling means to detect shifts/spikes.
  - Why it matters: finds bursty or sudden pattern changes.
  - How we use it: track recent moving averages per customer.
- Risk enrichment: PEP/sanctions flags and risk ratings.
  - Why it matters: augments behavioral signals with external risk.
  - How we use it: join LN data and encode risk indicators.
- Outputs: `flagged_top10.csv`, `flagged_all_scored.csv`, optional `flagged_p95.csv` for analyst triage.
  - Why it matters: provides immediate, reviewable artifacts.
  - How we use it: save CSVs and a histogram image in `data/processed/`.

## What’s Implemented Where
- `src/aml/data_ingest.py`: load CSV/XML, normalize, join; stream left-join to CSV.
- `src/aml/feature_engineering.py`: datetime parts; `amt_z_by_customer`; `amt_rolling_mean_7`; 0/1 risk flags.
- `src/aml/models/isolation_forest.py`: train and score Isolation Forest; add `anomaly_score`.
- `src/aml/evaluation.py`: `top_flags` convenience view.
- `src/aml/visualize.py`: histogram plot helper.
- `scripts/show_top_flags.py`: end-to-end run and outputs.
- `scripts/make_synthetic_data.py`: synthesize `transactions` and `lexisnexis` from reference stats.

## How It Flows
1. Load transactions and LexisNexis from `data/raw/`.
2. Join on `customer_id`.
3. Engineer features (time, customer-normalized, risk flags).
4. Score anomalies with Isolation Forest.
5. Export ranked outputs and plots.

## Next Steps (per ROADMAP)
- Add IQR/threshold rules; inter-arrival time; rolling counts/sums; structuring indicators.
- Peer groups, country risk lookups, calibration.
- Graph features and investigator views.

