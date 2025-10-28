# src/aml/sanctions/screen.py  (only the changes vs your last working file)
from __future__ import annotations

import sqlite3, os
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple, Optional

import numpy as np

from aml.sanctions.preprocess import norm_for_matching
from aml.sanctions.features_text import levenshtein_norm, jaro_winkler, token_overlap
from aml.sanctions.features_context import (
    dob_match as ctx_dob_match, country_match as ctx_country_match, id_soft_match as ctx_id_soft_match
)
from aml.sanctions.features_embed import encode_name, cosine_sim

# --- helpers for schema variance remain as you added earlier (_has_column, _address_select_expr) ---

@dataclass
class NameMatchConfig:
    # Text
    w_jw: float = 0.45
    w_lev: float = 0.20
    w_tok: float = 0.10
    # Embedding cosine (new)
    w_embed: float = 0.25
    # Context
    w_ctx_dob: float = 0.05
    w_ctx_country: float = 0.03
    w_ctx_id_soft: float = 0.07

    block_threshold: float = 0.93
    clear_threshold: float = 0.70

def _read_vec(blob: bytes) -> np.ndarray:
    if blob is None:
        return None
    v = np.frombuffer(blob, dtype=np.float32)
    return v.reshape(1, -1)

def name_text_features(qn: str, pnorm: str) -> Dict[str, float]:
    q = norm_for_matching(qn); p = norm_for_matching(pnorm)
    return {"lev": levenshtein_norm(q, p), "jw": jaro_winkler(q, p), "tok": token_overlap(q, p)}

def _fts_query(qn_raw: str, name_raw: str) -> str:
    return f'normalized_name:"{qn_raw}" OR primary_name:"{name_raw}"'

def _faiss_candidates(q_vec: np.ndarray, index_path: Optional[str], ids_path: Optional[str], topk: int = 50) -> List[int]:
    if not index_path or not ids_path:
        return []
    try:
        import faiss  # type: ignore
        import numpy as np
        import os
        if not (os.path.exists(index_path) and os.path.exists(ids_path)):
            return []
        index = faiss.read_index(index_path)
        ids = np.load(ids_path)  # shape (N,)
        D, I = index.search(q_vec.astype("float32"), topk)  # (1, K)
        idxs = I[0]
        return [int(ids[i]) for i in idxs if i >= 0]
    except Exception:
        return []

def screen(
    name: str,
    k: int = 10,
    db_path: str = "data/external/sanctions/kb.sqlite",
    context: Optional[Dict[str, Any]] = None,
    cfg: NameMatchConfig | None = None,
    # optional FAISS inputs
    faiss_index_path: Optional[str] = None,
    faiss_ids_path: Optional[str] = None,
) -> Dict[str, Any]:
    cfg = cfg or NameMatchConfig()
    q_norm = norm_for_matching(name)
    q_vec = encode_name(q_norm)  # (1, D), L2-normalized

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        # 1) FTS5 candidates
        addr_expr = _address_select_expr(con)
        sql = f"""
            SELECT e.entity_id, e.primary_name, e.normalized_name, e.entity_type, e.programs, e.source,
                   e.dob, e.nationalities, e.ids, {addr_expr}, e.name_vec
              FROM entity_fts
              JOIN entities e ON e.entity_id = entity_fts.rowid
             WHERE entity_fts MATCH ?
             LIMIT 50
        """
        fts_rows = con.execute(sql, (_fts_query(q_norm, name),)).fetchall()

        # 2) (optional) FAISS candidates for recall
        faiss_eids = set(_faiss_candidates(q_vec, faiss_index_path, faiss_ids_path, topk=50))

        # 3) If FAISS brought extra entity_ids not in FTS – fetch them
        existing_ids = {r["entity_id"] for r in fts_rows}
        missing = list(faiss_eids - existing_ids)
        faiss_rows = []
        if missing:
            qmarks = ",".join("?" for _ in missing)
            faiss_rows = con.execute(f"""
                SELECT e.entity_id, e.primary_name, e.normalized_name, e.entity_type, e.programs, e.source,
                       e.dob, e.nationalities, e.ids, {addr_expr}, e.name_vec
                  FROM entities e
                 WHERE e.entity_id IN ({qmarks})
            """, missing).fetchall()

        rows = list(fts_rows) + list(faiss_rows)
    finally:
        con.close()

    # De-dupe by entity_id (keep first occurrence)
    seen = set(); uniq_rows = []
    for r in rows:
        eid = r["entity_id"]
        if eid in seen: continue
        seen.add(eid); uniq_rows.append(r)

    scored = []
    for r in uniq_rows:
        pname = r["primary_name"]
        pnorm_eff = r["normalized_name"] or norm_for_matching(pname or "")
        text_feats = name_text_features(q_norm, pnorm_eff)
        text_score = cfg.w_jw*text_feats["jw"] + cfg.w_lev*text_feats["lev"] + cfg.w_tok*text_feats["tok"]

        # Embedding cosine (if entity has a vector)
        embed_cos = 0.0
        p_blob = r["name_vec"]
        if p_blob:
            p_vec = _read_vec(p_blob)  # (1, D)
            embed_cos = float((p_vec @ q_vec.T).ravel()[0])  # both L2-normalized

        # Context features
        ctx_feats = {"ctx_dob":0,"ctx_country":0,"ctx_id_soft":0}
        try:
            ctx_feats["ctx_dob"] = ctx_dob_match((context or {}).get("dob"), r["dob"])
            ctx_feats["ctx_country"] = ctx_country_match((context or {}).get("country"), r["nationalities"], r["address"])
            ctx_feats["ctx_id_soft"] = ctx_id_soft_match((context or {}).get("id_number"), r["ids"])
        except Exception:
            pass

        ctx_bonus = cfg.w_ctx_dob*ctx_feats["ctx_dob"] + cfg.w_ctx_country*ctx_feats["ctx_country"] + cfg.w_ctx_id_soft*ctx_feats["ctx_id_soft"]

        final = text_score + cfg.w_embed*max(0.0, embed_cos) + ctx_bonus
        final = max(0.0, min(1.0, final))  # clamp

        scored.append((
            final, text_score, embed_cos, ctx_bonus, text_feats, ctx_feats, r
        ))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = []
    for final, text_score, embed_cos, ctx_bonus, text_feats, ctx_feats, r in scored[:k]:
        feats = {**{k: round(v,6) for k,v in text_feats.items()}, "embed_cos": round(embed_cos,6)}
        top.append({
            "entity_id": r["entity_id"],
            "primary_name": r["primary_name"],
            "score": round(final, 6),
            "text_score": round(text_score, 6),
            "context_bonus": round(ctx_bonus, 6),
            "features": feats,
            "context_features": ctx_feats,
            "entity_type": r["entity_type"],
            "programs": r["programs"],
            "source": r["source"],
            "dob": r["dob"],
            "nationalities": r["nationalities"],
            "ids": r["ids"],
            "address": r["address"],
        })

    decision = "review"
    if top:
        best = top[0]["score"]
        if best >= cfg.block_threshold: decision = "block"
        elif best <= cfg.clear_threshold: decision = "clear"

    return {"query": name, "context_used": context, "decision": decision, "top_hits": top}
