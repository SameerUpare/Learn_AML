# scripts/backfill_name_vectors_sqlite.py
from __future__ import annotations
import sqlite3, argparse, pathlib, struct
import numpy as np

from aml.sanctions.preprocess import norm_for_matching
from aml.sanctions.features_embed import encode_names

DB_DEFAULT = "data/external/sanctions/kb.sqlite"

def np_to_blob(v: np.ndarray) -> bytes:
    # Store as raw float32 bytes; L2-normalized already.
    assert v.dtype == np.float32 and v.ndim == 2 and v.shape[0] == 1
    return v.tobytes()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_DEFAULT)
    ap.add_argument("--batch", type=int, default=512)
    ap.add_argument("--model", default=None, help="(optional) store model name in name_vec_model")
    args = ap.parse_args()

    db = pathlib.Path(args.db)
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row

    # Pick rows missing vectors
    rows = con.execute("""
        SELECT entity_id, primary_name, normalized_name
          FROM entities
         WHERE name_vec IS NULL
    """).fetchall()

    if not rows:
        print("No rows to backfill (name_vec already present).")
        con.close(); return 0

    print(f"Backfilling {len(rows)} entities...")
    B = args.batch
    for i in range(0, len(rows), B):
        chunk = rows[i:i+B]
        names = []
        for r in chunk:
            nm = r["normalized_name"] or r["primary_name"] or ""
            nm = norm_for_matching(nm)
            names.append(nm)
        vecs = encode_names(names)  # (N, D) float32 L2-normalized

        # Write
        with con:
            for r, vec in zip(chunk, vecs):
                con.execute(
                    "UPDATE entities SET name_vec=?, name_vec_model=COALESCE(?, name_vec_model) WHERE entity_id=?",
                    (vec.astype("float32").tobytes(), args.model, r["entity_id"])
                )
        print(f"  {min(i+B, len(rows))}/{len(rows)}")

    con.close()
    print("Done.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
