# scripts/migrate_add_name_vec.py
from __future__ import annotations
import sqlite3, pathlib

DB = pathlib.Path("data/external/sanctions/kb.sqlite")

SQLS = [
    "ALTER TABLE entities ADD COLUMN name_vec BLOB;",
    "ALTER TABLE entities ADD COLUMN name_vec_model TEXT;",
]

con = sqlite3.connect(DB)
try:
    for stmt in SQLS:
        try:
            con.execute(stmt)
        except sqlite3.OperationalError as e:
            # Ignore "duplicate column name" and similar
            msg = str(e).lower()
            if "duplicate column name" in msg or "already exists" in msg:
                pass
            else:
                raise
    con.commit()
finally:
    con.close()

print("Ensured columns: name_vec (BLOB), name_vec_model (TEXT)")
