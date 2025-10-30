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

🧠 AML-LexisNexis-Starter
AI-Driven Name Screening, Sanctions Normalization, and ISO 20022 Audit Framework

⚙️ Setup & Run Guide
Step 1 — Initialize environment and folder structure
# From PowerShell (run inside VS Code terminal or as Admin)
cd D:\aml-lexisnexis-starter\aml-lexisnexis-starter
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = ".\src"

# Create expected folders
mkdir -Force data\raw\uk, data\raw\un | Out-Null
mkdir -Force data\processed\sanctions | Out-Null


Step 2 — Place source sanctions files
Copy your source files into:
data\raw\uk\ConList.csv
data\raw\un\consolidatedLegacyByPRN.xml

(Use your actual filenames.)
If you have OFAC (SDN) lists, put them under data\raw\ofac\.

Step 3 — Normalize raw sanctions lists
cd D:\aml-lexisnexis-starter\aml-lexisnexis-starter
$env:PYTHONPATH = ".\src"

python -m aml.sanctions.normalize_sanctions --uk "data/raw/uk/ConList.csv" --base "data"
python -m aml.sanctions.normalize_sanctions --un "data/raw/un/consolidatedLegacyByPRN.xml" --base "data"

✅ Normalized JSONL files will appear under:
data\normalized\
   ├─ uk_ofsi.normalized.<timestamp>.jsonl
   └─ un_sc.normalized.<timestamp>.jsonl

Move them where the loader expects:
mkdir -Force data\external\sanctions\normalized | Out-Null
Move-Item data\normalized\*.jsonl data\external\sanctions\normalized\


Step 4 — Build the Knowledge Base (KB)
# a) Start fresh to avoid duplicates
Remove-Item -Force data\external\sanctions\kb.sqlite -ErrorAction SilentlyContinue

# b) Ensure src/ is visible
$env:PYTHONPATH = ".\src"

# c) Build
python -m aml.sanctions.load_kb

You should see:
Loaded 20620 records into ...\data\external\sanctions\kb.sqlite


Step 5 — Prepare ISO 20022 test files
Ensure your test XMLs (pain.001, pacs.008, camt.053) exist in:
data\external\iso20022\inbox\

Example: pain_001_suspects.xml
contains Eric Badege, Innocent Kaina, and Sultani Makenga.

Step 6 — Inspect KB contents
$env:PYTHONPATH = ".\src"
python -c "import sqlite3, pandas as pd; \
con=sqlite3.connect(r'data/external/sanctions/kb.sqlite'); \
print(pd.read_sql_query('SELECT * FROM entities LIMIT 10;', con)); con.close()"

Use this output to identify sanctioned names for testing.

Step 7 — Run ISO 20022 Pre-Process + Audit
$env:PYTHONPATH = ".\src"
python -m aml.sanctions.iso20022_preprocess_audit

Output CSV:
data\external\iso20022\reports\
   preprocess_audit_with_screen.<timestamp>.csv


📊 Expected Output Columns
ColumnDescriptiontop_hit_scoreFinal similarity score (0–1)top_hit_nameBest-matched sanctioned entitytop_hit_sourceData source (UN, UK, OFAC, etc.)top_hit_token_overlapToken-level similaritytop_hit_jaro_winklerString proximity metrictop_hit_levenshtein_normNormalized edit distance
If these appear blank, see Troubleshooting #7.

🛠️ Troubleshooting
1️⃣ ModuleNotFoundError: No module named 'aml'
Set PYTHONPATH each session or install in editable mode.
$env:PYTHONPATH = ".\src"
pip install -e .


2️⃣ Loaded 0 records after load_kb
Move normalized JSONL files to:
data\external\sanctions\normalized\

Then rebuild KB.

3️⃣ no such table: entity_fts
Rebuild KB:
Remove-Item -Force data\external\sanctions\kb.sqlite -ErrorAction SilentlyContinue
$env:PYTHONPATH = ".\src"
python -m aml.sanctions.load_kb


4️⃣ no such column: e.name_vec
Use the schema-aware screen.py (vectors optional).
Or add columns manually if you plan to use embeddings:
ALTER TABLE entities ADD COLUMN name_vec BLOB;
ALTER TABLE entities ADD COLUMN name_vec_dim INTEGER;
ALTER TABLE entities ADD COLUMN name_vec_model TEXT;


5️⃣ _address_select_expr is not defined
Add near top of screen.py:
def _address_select_expr():
    return "COALESCE(e.addresses, '')"


6️⃣ PowerShell heredoc / << errors
Use PowerShell here-strings (@' ... '@ | python -) or -c one-liners instead.

7️⃣ Empty top_hit_* columns


Confirm the name exists in KB (LIKE query).


Use comma delimiter when importing CSV in Excel.


If filtering is too strict, adjust screen() call:
res = screen(name, k=25)




8️⃣ Check names in KB
@'
import sqlite3
con = sqlite3.connect(r"data/external/sanctions/kb.sqlite")
for n in ["%Badege%","%Kaina%","%Makenga%"]:
    print(n, con.execute("SELECT primary_name, source FROM entities WHERE primary_name LIKE ? OR aliases LIKE ? LIMIT 10",(n,n)).fetchall())
con.close()
'@ | python -


9️⃣ Quick screener test
$env:PYTHONPATH = ".\src"
@'
from aml.sanctions.screen import screen
for q in ["Eric Badege","Innocent Kaina","Sultani Makenga"]:
    res = screen(q, k=25)
    print(f"\n=== {q} ===")
    print("decision:", res.get("decision"))
    for i,h in enumerate((res.get("top_hits") or [])[:5], start=1):
        print(f"{i}. {h.get('score')} | {h.get('primary_name')} | {h.get('source')}")
'@ | python -


🔟 Virtualenv activation fails
Recreate if needed:
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt


1️⃣1️⃣ Normalized file locations
Normalizer → data\normalized\
Loader → data\external\sanctions\normalized\
✅ Always move normalized files before load_kb.

1️⃣2️⃣ Seed test records
If your KB lacks certain names:
@'
{"source":"SEED","source_id":"S-1","entity_type":"person","primary_name":"Eric Badege","aliases":[],"programs":["DRC"],"normalized_name":"eric badege"}
{"source":"SEED","source_id":"S-2","entity_type":"person","primary_name":"Innocent Kaina","aliases":[],"programs":["DRC"],"normalized_name":"innocent kaina"}
{"source":"SEED","source_id":"S-3","entity_type":"person","primary_name":"Sultani Makenga","aliases":[],"programs":["DRC"],"normalized_name":"sultani makenga"}
'@ | Set-Content -Encoding UTF8 data\external\sanctions\normalized\seed_suspects.jsonl

Remove-Item -Force data\external\sanctions\kb.sqlite -ErrorAction SilentlyContinue
$env:PYTHONPATH = ".\src"
python -m aml.sanctions.load_kb


💡 FAQ
Q: Where should OFAC (US) files go?
→ Place them in data\raw\ofac\ and run
python -m aml.sanctions.normalize_sanctions --ofac "data/raw/ofac/sdn.csv" --base "data".

Q: How do I add embeddings later?


Add vector columns (see Troubleshooting #4).


Rebuild KB (load_kb).


screen.py automatically begins cosine scoring.



Q: How do I interpret the scores?
RangeMeaningAction≥ 0.93BlockDefinite sanction match0.70 – 0.93ReviewManual investigation required≤ 0.70ClearNo meaningful match
Text similarity (jw, lev, tok) + optional embedding cosine are combined using tunable weights from NameMatchConfig.

Q: How to check DB health?
python -c "import sqlite3; c=sqlite3.connect(r'data/external/sanctions/kb.sqlite'); \
print('Entities:', c.execute('SELECT COUNT(*) FROM entities').fetchone()[0]); \
print('FTS rows:', c.execute('SELECT COUNT(*) FROM entity_fts').fetchone()[0]); c.close()"


Q: What if Excel shows garbled data?
Always import via Data → From Text/CSV → Delimiter = Comma; never open CSVs directly by double-clicking.

✅ Everything working?
Try this quick validation loop:
$env:PYTHONPATH = ".\src"
python -m aml.sanctions.iso20022_preprocess_audit
python -c "import sqlite3; c=sqlite3.connect(r'data/external/sanctions/kb.sqlite'); \
print('Entities:', c.execute('SELECT COUNT(*) FROM entities').fetchone()[0]); c.close()"

If both the KB counts and the audit CSV look good → your pipeline is fully operational.

© 2025 AML LexisNexis Starter | Designed for rapid prototyping of sanctions screening workflows
