# scripts/build_country_aliases.py
"""
Build a comprehensive country alias map from ISO + curated extras.

Outputs:
  src/aml/config/country_aliases.json
  (and merges src/aml/config/country_aliases_overrides.json if present)

Requires: pip install pycountry unidecode
"""
from __future__ import annotations
import json, re
from pathlib import Path
from typing import Dict, List
import pycountry  # type: ignore
from unidecode import unidecode  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "aml" / "config" / "country_aliases.json"
OVR = ROOT / "src" / "aml" / "config" / "country_aliases_overrides.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

def norm(s: str) -> str:
    s = unidecode(s or "")
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9 /&'().-]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s

def dedup_keep_order(seq: List[str]) -> List[str]:
    seen, out = set(), []
    for x in seq:
        if not x: 
            continue
        if x not in seen:
            seen.add(x); out.append(x)
    return out

def main() -> None:
    data: Dict[str, Dict[str, object]] = {}
    # Build from ISO
    for c in list(pycountry.countries):
        alpha2 = getattr(c, "alpha_2", None)
        alpha3 = getattr(c, "alpha_3", None)
        name = getattr(c, "name", None)
        official = getattr(c, "official_name", None)
        common = getattr(c, "common_name", None)

        # Canonical (prefer common_name > name)
        canonical = norm(common or name or "")
        if not canonical:
            continue

        aliases = [
            norm(name or ""),
            norm(official or ""),
            norm(common or ""),
            norm(alpha2 or ""),
            norm(alpha3 or ""),
        ]

        # Add common demonyms/abbrevs for frequent countries
        extras: Dict[str, List[str]] = {
            "united states": ["usa", "u.s.a.", "us", "u.s."],
            "united kingdom": ["uk", "u.k.", "great britain", "gb", "gbr"],
            "united arab emirates": ["uae", "u.a.e."],
            "russia": ["russian federation", "rf"],
            "czechia": ["czech republic"],
            "north macedonia": ["macedonia"],
            "eswatini": ["swaziland"],
            "myanmar": ["burma"],
            "cote d'ivoire": ["ivory coast", "cote d’ivoire", "cote d ivoire"],
            "congo, the democratic republic of the": ["drc", "dr congo", "democratic republic of congo"],
            "korea, republic of": ["south korea", "rok"],
            "korea, democratic people's republic of": ["north korea", "dprk"],
            "holy see": ["vatican", "vatican city"],
            "china": ["prc", "people's republic of china"],
            "hong kong": ["hong kong sar"],
            "macao": ["macau", "macau sar", "macao sar"],
            "taiwan, province of china": ["taiwan", "roc", "republic of china"],
        }
        if canonical in extras:
            aliases.extend([norm(x) for x in extras[canonical]])

        aliases = dedup_keep_order([a for a in aliases if a])

        data[canonical] = {
            "alpha2": alpha2,
            "alpha3": alpha3,
            "aliases": aliases,
        }

    # Merge optional overrides
    if OVR.exists():
        with OVR.open("r", encoding="utf-8") as f:
            overrides = json.load(f)
        for canon, obj in overrides.items():
            canon_n = norm(canon)
            base = data.setdefault(canon_n, {"alpha2": None, "alpha3": None, "aliases": []})
            base["alpha2"] = base.get("alpha2") or obj.get("alpha2")
            base["alpha3"] = base.get("alpha3") or obj.get("alpha3")
            base["aliases"] = dedup_keep_order(
                [norm(x) for x in (list(base.get("aliases", [])) + list(obj.get("aliases", [])))]
            )

    # Write
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {OUT} with {len(data)} canonical countries")

if __name__ == "__main__":
    main()
