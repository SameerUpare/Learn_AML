# scripts/build_faiss_index.py
from __future__ import annotations
import argparse, sqlite3, pathlib, json
import numpy as np

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/external/sanctions/kb.sqlite")
    ap.add_argument("--out-index", default="data/external/sanctions/faiss_name.index")
    ap.add_argument("--out-ids", default="data/external/sanctions/faiss_entity_ids.npy")
    args = ap.parse_args()

    import faiss  # type: ignore

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT entity_id, name_vec FROM entities WHERE name_vec IS NOT NULL").fetchall()
    con.close()

    if not rows:
        print("No vectors found; run backfill first.")
        return 1

    # Load blobs to matrix
    vecs = []
    ids = []
    for r in rows:
        blob = r["name_vec"]
        v = np.frombuffer(blob, dtype=np.float32)
        vecs.append(v)
        ids.append(r["entity_id"])
    X = np.vstack(vecs).astype("float32")
    d = X.shape[1]

    # IndexFlatIP because vectors are L2-normalized => cosine == dot
    index = faiss.IndexFlatIP(d)
    index.add(X)

    # Persist
    pathlib.Path(args.out_index).parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, args.out_index)
    np.save(args.out_ids, np.asarray(ids, dtype=np.int64))
    print(f"Wrote FAISS index: {args.out_index} with {len(ids)} vectors")
    print(f"Wrote ids map:     {args.out_ids}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
