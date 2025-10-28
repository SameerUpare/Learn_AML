
# AML Learning Project — LexisNexis + Transaction Anomaly Detection (Phase 1)

**Goal:** Learn ML/AI/NLP by building a realistic **AML anomaly detection** pipeline that links **LexisNexis (KYC/enrichment)** data with a **transaction dataset**, and flags unusual behavior with **explainable** outputs.

## 📦 Project Structure
```
.
├── data/
│   ├── raw/            # place source CSVs here (transactions.csv, lexisnexis.csv)
│   ├── processed/      # clean, joined, feature-rich datasets
│   └── external/       # any third-party lookups (country risk lists, MCC codes, etc.)
├── docs/
│   └── SETUP.md        # how to run the project
├── notebooks/          # exploratory notebooks (01, 02, ...)
├── src/aml/
│   ├── config.py
│   ├── data_ingest.py
│   ├── feature_engineering.py
│   ├── models/
│   │   └── isolation_forest.py
│   ├── evaluation.py
│   ├── visualize.py
│   └── utils.py
├── tests/
│   └── test_smoke.py
├── README.md
├── ROADMAP.md
├── requirements.txt
└── .gitignore
```

## 🧩 Phase 1 — What we will build
1. **Data linking**: Join transactions with LexisNexis KYC/enrichment by customer/account ID.
2. **Features**: velocity, peer-group deviation, geo/country, channel, counterparty risk, risk flags from LexisNexis.
3. **Model**: Unsupervised baseline — Isolation Forest (configurable).
4. **Explainability**: Top contributing features per flag (simple SHAP summary or rule contributions).
5. **Outputs**: CSV of flagged transactions with scores, and a simple notebook dashboard.

> **Note:** Use synthetic/sanitized data for learning. No real PII should be committed.

## 📂 Expected Input Files (CSV)
- `data/raw/transactions.csv`:  
  `txn_id, customer_id, account_id, datetime, amount, currency, channel, counterparty_id, counterparty_country, mcc, description`
- `data/raw/lexisnexis.csv`:  
  `customer_id, customer_name, dob, nationality, pep_flag, sanctions_flag, adverse_media_score, risk_rating, kyc_last_review_date`

(Columns are examples — adjust in `src/aml/config.py` if your dataset differs.)

## ▶️ Quickstart
```bash
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Put your CSVs in data/raw/, then run a smoke test:
python -c "from src.aml.data_ingest import validate_inputs; print(validate_inputs())"
```

## 🧪 First Notebook Plan
- `notebooks/01_data_link_and_eda.ipynb`: join, sanity checks, basic EDA.
- `notebooks/02_baseline_isolation_forest.ipynb`: train, score, export flagged csv.
- `notebooks/03_explainability.ipynb`: SHAP (or simpler feature deltas), flag reasons.
- `notebooks/04_reporting.ipynb`: top-10 customers/transactions, simple visuals.

## 🧭 Next Steps (Phase 1 → 1.5 → 2)
See **ROADMAP.md** for milestones, issue bundles, and stretch goals (graph, NLP, case pages).
