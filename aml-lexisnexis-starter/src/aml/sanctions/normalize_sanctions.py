#!/usr/bin/env python3
"""
normalize_sanctions.py — one-shot, dependency-light normalizer for UK (CSV) & UN (XML)
"""
from __future__ import annotations
from aml.sanctions.preprocess import normalize_unicode, norm_for_matching  # ← ADDED

import argparse
import csv
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# ------------------------------- paths & base ------------------------------- #
BASE_DATA = Path(os.getenv("SANCTIONS_DATA_DIR", "./local-data")).resolve()
RAW_UK = BASE_DATA / "raw" / "uk"
RAW_UN = BASE_DATA / "raw" / "un"
NORMALIZED = BASE_DATA / "normalized"
for p in (RAW_UK, RAW_UN, NORMALIZED):
    p.mkdir(parents=True, exist_ok=True)

# ----------------------------- normalization utils ------------------------- #

def norm(t):  # ← REPLACED to use shared preprocessor
    return normalize_unicode(t, "NFKC").strip() if t else ""

def join_nonempty(parts: Iterable[str], sep: str = " ") -> str:
    return sep.join([norm(p) for p in parts if norm(p)])

# ------------------------------- schema record ----------------------------- #

@dataclass
class Record:
    source: str
    source_id: Optional[str] = None
    entity_type: Optional[str] = None
    primary_name: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    programs: List[str] = field(default_factory=list)
    list_date: Optional[str] = None
    last_updated: Optional[str] = None
    dob: List[str] = field(default_factory=list)
    nationalities: List[str] = field(default_factory=list)
    addresses: List[str] = field(default_factory=list)
    ids: List[str] = field(default_factory=list)
    remarks: Optional[str] = None
    source_uri: Optional[str] = None
    normalized_name: Optional[str] = None  # ← FIXED (removed stray invalid line)

    def finalize(self) -> None:
        self.primary_name = norm(self.primary_name)
        self.aliases = [norm(a) for a in self.aliases if norm(a)]
        self.programs = [norm(p) for p in self.programs if norm(p)]
        self.dob = [norm(d) for d in self.dob if norm(d)]
        self.nationalities = [norm(n) for n in self.nationalities if norm(n)]
        self.addresses = [norm(a) for a in self.addresses if norm(a)]
        self.ids = [norm(i) for i in self.ids if norm(i)]
        self.remarks = norm(self.remarks)
        self.entity_type = norm(self.entity_type)
        self.source_id = norm(self.source_id)
        self.source_uri = norm(self.source_uri)
        self.list_date = norm(self.list_date) or None
        self.last_updated = norm(self.last_updated) or None
        self.normalized_name = norm_for_matching(self.primary_name or "")  # ← REPLACED

# ------------------------------ UK CSV parser ------------------------------- #

UK_MUST_HAVE = {"name", "group", "regime"}

def find_header_row(rows: List[List[str]]) -> Optional[int]:
    up_to = min(100, len(rows))
    for i in range(up_to):
        low = [c.strip().lower() for c in rows[i]]
        hay = " ".join(low)
        if sum(x in hay for x in UK_MUST_HAVE) >= 2:
            return i
    return None

def normalize_uk_csv(in_csv: Path, out_jsonl: Path) -> int:
    with in_csv.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        print(f"[UK] No rows in {in_csv}")
        return 0

    hdr_idx = find_header_row(rows)
    if hdr_idx is None:
        print(f"[UK] Could not detect header in {in_csv}; writing nothing.")
        return 0

    headers = rows[hdr_idx]
    idx = {h: i for i, h in enumerate(headers)}

    def get(row: List[str], key: str) -> str:
        i = idx.get(key)
        return row[i] if (i is not None and i < len(row)) else ""

    count = 0
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("w", encoding="utf-8") as out:
        for row in rows[hdr_idx + 1 :]:
            if not any(row):
                continue
            primary = join_nonempty([get(row, f"Name {k}") for k in ["1","2","3","4","5","6"]]) or norm(get(row, "Name 1"))
            aliases = []
            for k in ["Name 2","Name 3","Name 4","Name 5","Name 6","Name Non-Latin Script"]:
                v = norm(get(row, k))
                if v:
                    aliases.append(v)
            address = join_nonempty([
                get(row, "Address 1"), get(row, "Address 2"), get(row, "Address 3"),
                get(row, "Address 4"), get(row, "Address 5"), get(row, "Address 6"),
                get(row, "Post/Zip Code"), get(row, "Country")
            ], sep=", ")
            ids: List[str] = []
            pnum = norm(get(row, "Passport Number"))
            nid  = norm(get(row, "National Identification Number"))
            if pnum: ids.append(pnum)
            if nid: ids.append(nid)

            rec = Record(
                source="UK-OFSI",
                source_id=norm(get(row, "Group ID")),
                entity_type=norm(get(row, "Group Type")) or norm(get(row, "Type")) or None,
                primary_name=primary,
                aliases=aliases,
                programs=[norm(get(row, "Regime"))] if norm(get(row, "Regime")) else [],
                list_date=norm(get(row, "Listed On")) or None,
                last_updated=norm(get(row, "Last Updated")) or None,
                dob=[norm(get(row, "DOB"))] if norm(get(row, "DOB")) else [],
                nationalities=[norm(get(row, "Nationality"))] if norm(get(row, "Nationality")) else [],
                addresses=[address] if address else [],
                ids=ids,
                remarks=norm(get(row, "Other Information")) or None,
            )
            rec.finalize()
            if rec.primary_name:
                out.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")
                count += 1
    print(f"[UK] Wrote {count} records → {out_jsonl}")
    return count

# ------------------------------ UN XML parser ------------------------------- #

def t(el: ET.Element, tag: str) -> str:
    x = el.find(tag)
    return norm(x.text) if x is not None and x.text else ""

def ts(parent: ET.Element, path: str) -> List[str]:
    vals: List[str] = []
    for x in parent.findall(path):
        if x.text:
            vals.append(norm(x.text))
    return [v for v in vals if v]

def parse_un_individual(ind: ET.Element) -> Record:
    name = " ".join(filter(None, [t(ind, "FIRST_NAME"), t(ind, "SECOND_NAME"), t(ind, "THIRD_NAME"), t(ind, "FOURTH_NAME")])) or t(ind, "NAME")
    aliases: List[str] = []
    aka_list = ind.find("AKA_LIST")
    if aka_list is not None:
        for aka in aka_list.findall("AKA"):
            alias = t(aka, "ALIAS_NAME")
            if alias:
                aliases.append(alias)

    programs: List[str] = []
    des = ind.find("DESIGNATION")
    if des is not None and des.text:
        programs.append(norm(des.text))
    programs += ts(ind, "LIST_TYPE")

    dobs: List[str] = []
    for dob in ind.findall("INDIVIDUAL_DATE_OF_BIRTH"):
        d = t(dob, "DATE")
        if d:
            dobs.append(d)
        dobs += ts(dob, "YEAR")
    if not dobs:
        dobs = ts(ind, "DATE_OF_BIRTH")

    nats: List[str] = []
    for n in ind.findall("INDIVIDUAL_NATIONALITY"):
        nats += ts(n, "NATIONALITY")

    addrs: List[str] = []
    adrlist = ind.find("INDIVIDUAL_ADDRESS_LIST")
    if adrlist is not None:
        for adr in adrlist.findall("INDIVIDUAL_ADDRESS"):
            parts = []
            for tag in ["STREET", "CITY", "STATE_PROVINCE", "ZIP_CODE", "COUNTRY"]:
                v = t(adr, tag)
                if v:
                    parts.append(v)
            if parts:
                addrs.append(", ".join(parts))

    ids: List[str] = []
    for doc in ind.findall("INDIVIDUAL_DOCUMENT"):
        num = t(doc, "NUMBER")
        if num:
            ids.append(num)

    last_updated = t(ind, "LAST_DAY_UPDATED") or t(ind, "LAST_UPDATE")
    remarks = t(ind, "COMMENTS1")

    rec = Record(
        source="UN-SECURITY-COUNCIL",
        source_id=t(ind, "DATAID") or t(ind, "REFERENCE_NUMBER"),
        entity_type="person",
        primary_name=name,
        aliases=aliases,
        programs=[p for p in programs if p],
        list_date=None,
        last_updated=last_updated or None,
        dob=[d for d in dobs if d],
        nationalities=[n for n in nats if n],
        addresses=[a for a in addrs if a],
        ids=[i for i in ids if i],
        remarks=remarks or None,
    )
    rec.finalize()
    return rec

def parse_un_entity(ent: ET.Element) -> Record:
    name = t(ent, "FIRST_NAME") or t(ent, "NAME")
    aliases: List[str] = []
    aka_list = ent.find("AKA_LIST")
    if aka_list is not None:
        for aka in aka_list.findall("AKA"):
            alias = t(aka, "ALIAS_NAME")
            if alias:
                aliases.append(alias)

    programs: List[str] = []
    des = ent.find("DESIGNATION")
    if des is not None and des.text:
        programs.append(norm(des.text))
    programs += ts(ent, "LIST_TYPE")

    addrs: List[str] = []
    adrlist = ent.find("ENTITY_ADDRESS_LIST")
    if adrlist is not None:
        for adr in adrlist.findall("ENTITY_ADDRESS"):
            parts = []
            for tag in ["STREET", "CITY", "STATE_PROVINCE", "ZIP_CODE", "COUNTRY"]:
                v = t(adr, tag)
                if v:
                    parts.append(v)
            if parts:
                addrs.append(", ".join(parts))

    ids: List[str] = []
    for doc in ent.findall("ENTITY_DOCUMENT"):
        num = t(doc, "NUMBER")
        if num:
            ids.append(num)

    last_updated = t(ent, "LAST_DAY_UPDATED") or t(ent, "LAST_UPDATE")
    remarks = t(ent, "COMMENTS1")

    rec = Record(
        source="UN-SECURITY-COUNCIL",
        source_id=t(ent, "DATAID") or t(ent, "REFERENCE_NUMBER"),
        entity_type="organization",
        primary_name=name,
        aliases=aliases,
        programs=[p for p in programs if p],
        list_date=None,
        last_updated=last_updated or None,
        dob=[],
        nationalities=[],
        addresses=[a for a in addrs if a],
        ids=[i for i in ids if i],
        remarks=remarks or None,
    )
    rec.finalize()
    return rec

def normalize_un_xml(in_xml: Path, out_jsonl: Path) -> int:
    root = ET.parse(in_xml).getroot()
    count = 0
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("w", encoding="utf-8") as out:
        for ind in root.findall(".//INDIVIDUALS/INDIVIDUAL"):
            rec = parse_un_individual(ind)
            if rec.primary_name:
                out.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")
                count += 1
        for ent in root.findall(".//ENTITIES/ENTITY"):
            rec = parse_un_entity(ent)
            if rec.primary_name:
                out.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")
                count += 1
    print(f"[UN] Wrote {count} records → {out_jsonl}")
    return count

# ------------------------------- file helpers ------------------------------- #

def latest_file(dir_path: Path, pattern: str) -> Optional[Path]:
    files = sorted(dir_path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None

# ---------------------------------- CLI ------------------------------------- #

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Normalize UK (CSV) and UN (XML) sanctions into JSONL")
    ap.add_argument("--uk", type=str, help="Path to a specific UK CSV file to normalize")
    ap.add_argument("--un", type=str, help="Path to a specific UN XML file to normalize")
    ap.add_argument("--base", type=str, help="Override SANCTIONS_DATA_DIR for this run")
    args = ap.parse_args(argv)

    base = Path(args.base).resolve() if args.base else BASE_DATA
    uk_in = Path(args.uk) if args.uk else latest_file(base / "raw" / "uk", "*.csv")
    un_in = Path(args.un) if args.un else latest_file(base / "raw" / "un", "*.xml")

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    if uk_in and uk_in.exists():
        uk_out = base / "normalized" / f"uk_ofsi.normalized.{ts}.jsonl"
        normalize_uk_csv(uk_in, uk_out)
    else:
        print("[UK] No input file found. Pass --uk <file.csv> or place a CSV under raw/uk/")

    if un_in and un_in.exists():
        un_out = base / "normalized" / f"un_sc.normalized.{ts}.jsonl"
        normalize_un_xml(un_in, un_out)
    else:
        print("[UN] No input file found. Pass --un <file.xml> or place an XML under raw/un/")

    print("Done.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
