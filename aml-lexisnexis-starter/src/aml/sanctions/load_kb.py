
import json, sqlite3, pathlib

BASE = pathlib.Path(r".\data\external\sanctions").resolve()
NORM = BASE / "normalized"
DB   = BASE / "kb.sqlite"
DB.parent.mkdir(parents=True, exist_ok=True)

con = sqlite3.connect(DB)
con.execute("PRAGMA journal_mode=WAL;")

con.execute("""
CREATE TABLE IF NOT EXISTS entities (
  entity_id INTEGER PRIMARY KEY,
  source TEXT, source_id TEXT, entity_type TEXT,
  primary_name TEXT, aliases TEXT, programs TEXT,
  list_date TEXT, last_updated TEXT,
  dob TEXT, nationalities TEXT, addresses TEXT, ids TEXT, remarks TEXT,
  source_uri TEXT, normalized_name TEXT
);
""")

# Full-text index over names (primary + aliases + normalized_name)
con.execute("""
CREATE VIRTUAL TABLE IF NOT EXISTS entity_fts
USING fts5(primary_name, aliases, normalized_name, content='entities', content_rowid='entity_id');
""")

def as_pipe(v):
  if isinstance(v, list): return "|".join([str(x) for x in v])
  return v or ""

# Load the newest UK + UN jsonl (if present), otherwise load all
files = sorted(NORM.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)

rowids = []
for jf in files:
  with jf.open(encoding="utf-8") as f:
    for line in f:
      r = json.loads(line)
      cur = con.execute("""
        INSERT INTO entities
        (source, source_id, entity_type, primary_name, aliases, programs,
         list_date, last_updated, dob, nationalities, addresses, ids, remarks,
         source_uri, normalized_name)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
      """, (
        r.get("source"), r.get("source_id"), r.get("entity_type"),
        r.get("primary_name"), as_pipe(r.get("aliases", [])), as_pipe(r.get("programs", [])),
        r.get("list_date"), r.get("last_updated"),
        as_pipe(r.get("dob", [])), as_pipe(r.get("nationalities", [])), as_pipe(r.get("addresses", [])),
        as_pipe(r.get("ids", [])), r.get("remarks"), r.get("source_uri"),
        r.get("normalized_name"),
      ))
      rowids.append(cur.lastrowid)

# Populate FTS rows
con.executemany(
  "INSERT INTO entity_fts(rowid, primary_name, aliases, normalized_name) VALUES (?,?,?,?)",
  [(rid,
    con.execute("SELECT primary_name FROM entities WHERE entity_id=?", (rid,)).fetchone()[0],
    con.execute("SELECT aliases FROM entities WHERE entity_id=?", (rid,)).fetchone()[0],
    con.execute("SELECT normalized_name FROM entities WHERE entity_id=?", (rid,)).fetchone()[0],
  ) for rid in rowids]
)

con.commit()
print(f"Loaded {len(rowids)} records into {DB}")
