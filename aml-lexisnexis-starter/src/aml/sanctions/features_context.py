# src/aml/sanctions/features_context.py
from __future__ import annotations
import json, os, re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

try:
    from unidecode import unidecode  # optional but recommended
except Exception:
    unidecode = None  # fallback

# ----------------------------
# Normalization helpers
# ----------------------------
def _ascii_fold(s: str) -> str:
    if not s:
        return ""
    if unidecode:
        s = unidecode(s)
    return s

def _norm_space_lower(s: str) -> str:
    s = _ascii_fold(s).strip().lower()
    s = re.sub(r"[^a-z0-9 /&'().-]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s

def _norm_alnum_upper(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", s or "").upper()

def _split_pipes(s: Optional[str]) -> list[str]:
    if not s:
        return []
    return [part.strip() for part in str(s).split("|") if part.strip()]

def _try_parse_date(s: str) -> Optional[str]:
    fmts = ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%Y%m%d"]
    s = (s or "").strip()
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return None

# ----------------------------
# Country alias config loading
# ----------------------------
@lru_cache(maxsize=1)
def _load_country_aliases() -> dict:
    """
    Loads country_aliases.json and returns:
      {
        "canonical_lookup": { alias_str: canonical_name, ... },
        "canonical_meta":   { canonical_name: {"alpha2":..., "alpha3":..., "aliases":[...]} }
      }
    Search path:
      1) AML_COUNTRY_ALIASES env var (file path)
      2) src/aml/config/country_aliases.json (relative to this file)
    """
    env_path = os.getenv("AML_COUNTRY_ALIASES")
    if env_path and Path(env_path).exists():
        cfg_path = Path(env_path)
    else:
        cfg_path = Path(__file__).resolve().parents[1] / "config" / "country_aliases.json"

    if not cfg_path.exists():
        # Minimal built-ins so the function still works
        base = {
            "india": {"alpha2": "IN", "alpha3": "IND", "aliases": ["india", "in", "ind", "bharat"]},
            "united states": {"alpha2": "US", "alpha3": "USA", "aliases": ["united states", "us", "usa", "u.s.", "u.s.a."]},
            "united kingdom": {"alpha2": "GB", "alpha3": "GBR", "aliases": ["united kingdom", "uk", "u.k.", "great britain", "gbr", "gb"]},
        }
    else:
        with cfg_path.open("r", encoding="utf-8") as f:
            base = json.load(f)

    # Build reverse lookup
    canonical_lookup = {}
    for canon, meta in base.items():
        canon_n = _norm_space_lower(canon)
        canonical_lookup[canon_n] = canon_n
        for ali in meta.get("aliases", []):
            canonical_lookup[_norm_space_lower(ali)] = canon_n
        # Also map codes if present
        for code_k in ("alpha2", "alpha3"):
            code = meta.get(code_k)
            if code:
                canonical_lookup[_norm_space_lower(code)] = canon_n

    return {"canonical_lookup": canonical_lookup, "canonical_meta": base}

def _canon_country(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    lookups = _load_country_aliases()["canonical_lookup"]
    key = _norm_space_lower(s)
    return lookups.get(key)

def _field_contains_country(field_text: str, canonical_country: str) -> bool:
    if not field_text or not canonical_country:
        return False
    hay = _norm_space_lower(field_text)
    return canonical_country in hay

# ----------------------------
# Public context features
# ----------------------------
def dob_match(query_dob: Optional[str], entity_dob_field: Optional[str]) -> int:
    if not query_dob or not entity_dob_field:
        return 0
    q = _try_parse_date(query_dob)
    if not q:
        return 0
    for dob in _split_pipes(entity_dob_field):
        d = _try_parse_date(dob)
        if d and d == q:
            return 1
    return 0

def country_match(query_country: Optional[str],
                  nationalities_field: Optional[str],
                  address_field: Optional[str] = None) -> int:
    canon = _canon_country(query_country)
    if not canon:
        return 0
    for nat in _split_pipes(nationalities_field):
        if _canon_country(nat) == canon:
            return 1
    if address_field and _field_contains_country(address_field, canon):
        return 1
    return 0

def id_soft_match(query_id: Optional[str], entity_ids_field: Optional[str]) -> int:
    if not query_id or not entity_ids_field:
        return 0
    q = _norm_alnum_upper(query_id)
    if not q:
        return 0
    for L in (6, 5, 4):
        if len(q) >= L:
            tail = q[-L:]
            break
    else:
        return 0
    for eid in _split_pipes(entity_ids_field):
        ceid = _norm_alnum_upper(eid)
        if ceid and tail in ceid:
            return 1
    return 0

# ----------------------------
# Smoke test
# ----------------------------
if __name__ == "__main__":
    print("canon(IN) ->", _canon_country("IN"))
    print("canon(uk) ->", _canon_country("uk"))
