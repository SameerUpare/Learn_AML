
# Setup & Run

## 1) Environment
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2) Add Data
Place:
- `data/raw/transactions.csv`
- `data/raw/lexisnexis.csv`

## 3) Configure Columns
Adjust `src/aml/config.py` if your column names differ.

## 4) First Run (smoke)
```bash
python -c "from src.aml.data_ingest import validate_inputs; print(validate_inputs())"
```

## 5) Notebooks
Launch Jupyter and follow the notebook plan in README.
