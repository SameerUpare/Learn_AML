import numpy as np
import sqlite3

def np_to_blob(a: np.ndarray) -> bytes:
    a = np.asarray(a, dtype=np.float32)
    return a.tobytes()

def blob_to_np(b: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32, count=dim)

def upsert_vector(conn: sqlite3.Connection, entity_id: str, model: str, vec: np.ndarray):
    conn.execute(
        "INSERT OR REPLACE INTO sanction_vectors(entity_id, model_name, dim, vec, updated_at)"
        " VALUES(?,?,?,?,datetime('now'))",
        (entity_id, model, vec.shape[0], np_to_blob(vec)),
    )
    conn.commit()
