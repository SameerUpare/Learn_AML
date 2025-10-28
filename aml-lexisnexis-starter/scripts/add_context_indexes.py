# scripts/add_context_indexes.py
import sqlite3, pathlib

DB = pathlib.Path("data/external/sanctions/kb.sqlite")  # adjust if needed
sql = """
CREATE INDEX IF NOT EXISTS idx_entities_dob            ON entities(dob);
CREATE INDEX IF NOT EXISTS idx_entities_nationalities  ON entities(nationalities);
CREATE INDEX IF NOT EXISTS idx_entities_ids            ON entities(ids);
CREATE INDEX IF NOT EXISTS idx_entities_address        ON entities(address);
"""

con = sqlite3.connect(DB)
try:
    con.executescript(sql)
    # sanity: list indexes on 'entities'
    rows = con.execute("PRAGMA index_list('entities');").fetchall()
    print("Indexes on entities:", rows)
finally:
    con.close()
