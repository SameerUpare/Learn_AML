# AML Name Screening – Minimal Upgrade Path (Phase 1.5)

Production-lean, low-FPR **name screening** with hybrid retrieval (SQLite FTS5 + optional FAISS), classic text features (Levenshtein, Jaro–Winkler, token overlap), light context (DOB, country, ID tails), and optional multilingual embeddings.  
**Transaction Monitoring is on hold** (see Roadmap).

## Repo layout
src/
aml/
sanctions/
preprocess.py
normalize_sanctions.py
load_kb.py
features_text.py
features_context.py
features_embed.py
screen.py
screening/
sqlite_vec.py
scripts/
add_context_indexes.py
backfill_name_vectors_sqlite.py
build_country_aliases.py
build_faiss_index.py
migrate_add_name_vec.py

bash
Copy code

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Normalize sources (place UK/UN raw files under data/external/sanctions/raw/)
python -m aml.sanctions.normalize_sanctions --base data/external/sanctions

# Build/refresh SQLite KB with FTS5
python -m aml.sanctions.load_kb --base data/external/sanctions

# Smoke test
python -c "from aml.sanctions.screen import screen; print(screen('Mohammad Ali', k=5))"
How it works
Candidate generation: SQLite FTS5 (aliases + normalized). Optional FAISS ANN if vectors exist.

Text features: Levenshtein / Jaro–Winkler / token overlap (see features_text.py).

Context features: DOB, country aliases, soft ID-tail (see features_context.py).

Embeddings (optional): sentence-transformers → cosine sim (see features_embed.py).

Decision: thresholds in screen.py via NameMatchConfig.

Config / Env
AML_EMB_MODEL – HF model id for embeddings (default: multilingual MiniLM).

AML_COUNTRY_ALIASES – optional JSON to extend country mappings.

SANCTIONS_DATA_DIR – override base path for raw/normalized data (CLI --base typically used instead).

Large files
entities.csv is tracked with Git LFS. After cloning:

bash
Copy code
git lfs install && git lfs pull
Roadmap
See ROADMAP.md for next steps (namescreening items) and parked Transaction Monitoring.
