# iso20022_preprocess_audit.py — read ISO20022 XML from inbox, audit preprocessing, and screen()
from __future__ import annotations
import csv
from pathlib import Path
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# Preprocess steps (your shared module)
from aml.sanctions.preprocess import (
    normalize_unicode,
    strip_diacritics,
    casefold_text,
    collapse_punct_ws,
    norm_for_matching,
)

# Screener (uses your SQLite KB built by load_kb.py)
from aml.sanctions.screen import screen

# NEW: similarity features (fallback if screen() doesn't return them)
from aml.sanctions.features_text import (
    levenshtein_norm,
    jaro_winkler,
    token_overlap,
)

INBOX = Path(r".\data\external\iso20022\inbox").resolve()
OUTDIR = Path(r".\data\external\iso20022\reports").resolve()
OUTDIR.mkdir(parents=True, exist_ok=True)
RUN_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUTCSV = OUTDIR / f"preprocess_audit_with_screen.{RUN_TS}.csv"

# ---- human-readable names ----------------------------------------------------
MSG_TYPE_FULL = {
    "pacs.008": "FI-to-Customer Credit Transfer",
    "pacs.009": "Financial Institution Credit Transfer",
    "pain.001": "Customer Credit Transfer Initiation",
    "camt.053": "Bank-to-Customer Statement",
    "camt.054": "Bank-to-Customer Debit/Credit Notification",
}

ROLE_FULL = {
    "InitgPty": "Initiating Party",
    "Dbtr": "Debtor",
    "UltmtDbtr": "Ultimate Debtor",
    "Cdtr": "Creditor",
    "UltmtCdtr": "Ultimate Creditor",
    "DbtrAgt": "Debtor Agent",
    "CdtrAgt": "Creditor Agent",
    "StmtAcctOwnr": "Statement Account Owner",
    "NtfctnAcctOwnr": "Notification Account Owner",
    "NtryDbtr": "Entry Debtor",
    "NtryCdtr": "Entry Creditor",
    "InstgAgt": "Instructing Agent",
    "InstdAgt": "Instructed Agent",
}

# --- helpers -----------------------------------------------------------------
def localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag

def ns_of(tag: str) -> str | None:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else None

def msg_type(root: ET.Element) -> str:
    ns = ns_of(root.tag)
    if ns:
        last = ns.split(":")[-1]
        for key in ("pacs.008", "pacs.009", "pain.001", "camt.053", "camt.054"):
            if last.startswith(key):
                return key
    for child in list(root):
        ln = localname(child.tag)
        if ln == "FIToFICstmrCdtTrf": return "pacs.008"
        if ln == "FinInstnCdtTrf":    return "pacs.009"
        if ln == "CstmrCdtTrfInitn":  return "pain.001"
        if ln == "BkToCstmrStmt":     return "camt.053"
        if ln == "BkToCstmrDbtCdtNtfctn": return "camt.054"
    return localname(root.tag)

def path(ns: str, *segments: str) -> str:
    return ".//" + "/".join(f"{{{ns}}}{seg}" for seg in segments)

def extract_pairs(root: ET.Element, mtype: str) -> list[tuple[str, str]]:
    ns = ns_of(root.tag) or ""
    pairs: list[tuple[str, str]] = []

    common = {
        "InitgPty":   ["InitgPty", "Nm"],
        "Dbtr":       ["Dbtr", "Nm"],
        "UltmtDbtr":  ["UltmtDbtr", "Nm"],
        "Cdtr":       ["Cdtr", "Nm"],
        "UltmtCdtr":  ["UltmtCdtr", "Nm"],
        "DbtrAgt":    ["DbtrAgt", "FinInstnId", "Nm"],
        "CdtrAgt":    ["CdtrAgt", "FinInstnId", "Nm"],
    }
    if mtype.startswith("camt.053"):
        common["StmtAcctOwnr"] = ["Stmt", "Acct", "Ownr", "Nm"]
    if mtype.startswith("camt.054"):
        common["NtfctnAcctOwnr"] = ["Ntfctn", "Acct", "Ownr", "Nm"]

    # Common roles
    for role, segs in common.items():
        for node in root.findall(path(ns, *segs)):
            val = (node.text or "").strip()
            if val:
                pairs.append((role, val))

    # camt per-entry parties
    if mtype.startswith(("camt.053", "camt.054")):
        for node in root.findall(path(ns, "Ntry")):
            for r, sub in (("NtryDbtr", ["NtryDtls", "TxDtls", "RltdPties", "Dbtr", "Nm"]),
                           ("NtryCdtr", ["NtryDtls", "TxDtls", "RltdPties", "Cdtr", "Nm"])):  # noqa: E501
                for nm in node.findall("./" + "/".join(f"{{{ns}}}{s}" for s in sub)):
                    val = (nm.text or "").strip()
                    if val:
                        pairs.append((r, val))

    # pacs.009 agents
    if mtype.startswith("pacs.009"):
        for role, segs in (("InstgAgt", ["InstgAgt", "FinInstnId", "Nm"]),
                           ("InstdAgt", ["InstdAgt", "FinInstnId", "Nm"])):
            for node in root.findall(path(ns, *segs)):
                val = (node.text or "").strip()
                if val:
                    pairs.append((role, val))

    # de-duplicate
    seen = set()
    out: list[tuple[str, str]] = []
    for role, name in pairs:
        key = (role, name)
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out

def audit_row(
    file_name: str,
    mtype: str,
    role_code: str,
    original: str,
    decision: str,
    top_score: float | None,
    top_name: str | None,
    top_source: str | None,
    sim_feats: dict[str, float] | None,  # NEW
) -> dict[str, str]:
    s0 = original
    s1 = normalize_unicode(s0, "NFKC")
    s2 = strip_diacritics(s1)
    s3 = casefold_text(s2)
    s4 = collapse_punct_ws(s3)
    s5 = norm_for_matching(s0)  # final pipeline output used by screener

    # ---- expand to full names
    msg_type_full = MSG_TYPE_FULL.get(mtype, mtype)
    role_full = ROLE_FULL.get(role_code, role_code)

    # Similarity fields
    tok = "" if not sim_feats or sim_feats.get("tok") is None else f"{sim_feats['tok']:.3f}"
    jw  = "" if not sim_feats or sim_feats.get("jw")  is None else f"{sim_feats['jw']:.3f}"
    lev = "" if not sim_feats or sim_feats.get("lev") is None else f"{sim_feats['lev']:.3f}"

    return {
        "file": file_name,
        "msg_type": mtype,
        "msg_type_full": msg_type_full,
        "role": role_full,
        "original": s0,
        "step_nfkc": s1,
        "step_no_diacritics": s2,
        "step_casefold": s3,
        "step_punct_ws": s4,
        "final_match": s5,
        "decision": decision or "",
        "top_hit_score": "" if top_score is None else f"{top_score:.3f}",
        "top_hit_name": top_name or "",
        "top_hit_source": top_source or "",
        # NEW similarity outputs (top-hit vs query)
        "top_hit_token_overlap": tok,           # Jaccard token overlap
        "top_hit_jaro_winkler": jw,             # Jaro–Winkler similarity
        "top_hit_levenshtein_norm": lev,        # Levenshtein similarity (normalized)
    }

# --- main --------------------------------------------------------------------
def main() -> int:
    rows: list[dict[str, str]] = []
    if not INBOX.exists():
        print(f"[WARN] Inbox not found: {INBOX}")
        return 0

    # Cache screening results per final_match string to avoid repeated calls
    # value: (decision, top_score, top_name, top_source, sim_feats)
    screen_cache: dict[str, tuple[str, float | None, str | None, str | None, dict[str, float] | None]] = {}

    for xml_path in INBOX.glob("*.xml"):
        try:
            root = ET.parse(xml_path).getroot()
        except Exception as e:
            print(f"[WARN] Failed to parse {xml_path.name}: {e}")
            continue

        mtype = msg_type(root)
        pairs = extract_pairs(root, mtype)
        if not pairs:
            continue

        for role_code, name in pairs:
            final_key = norm_for_matching(name)

            # Lookup or call screen()
            if final_key not in screen_cache:
                try:
                    res = screen(name)  # uses your KB at data/external/sanctions/kb.sqlite
                    decision = res.get("decision")
                    top = (res.get("top_hits") or [])

                    if top:
                        top_score = top[0].get("score")
                        top_name = top[0].get("primary_name")
                        top_source = top[0].get("source")
                        # Prefer features returned by screen(); else compute
                        sim_feats = top[0].get("features")
                        if not sim_feats and top_name:
                            qn = norm_for_matching(name)
                            pn = norm_for_matching(top_name)
                            sim_feats = {
                                "tok": token_overlap(qn, pn),
                                "jw": jaro_winkler(qn, pn),
                                "lev": levenshtein_norm(qn, pn),
                            }
                    else:
                        top_score = None
                        top_name = None
                        top_source = None
                        sim_feats = None

                    screen_cache[final_key] = (decision, top_score, top_name, top_source, sim_feats)
                except Exception as e:
                    # On any error, record as review with no hit
                    screen_cache[final_key] = ("review", None, None, None, None)
                    print(f"[WARN] screen() failed for '{name}': {e}")

            decision, top_score, top_name, top_source, sim_feats = screen_cache[final_key]
            rows.append(
                audit_row(xml_path.name, mtype, role_code, name,
                          decision, top_score, top_name, top_source, sim_feats)
            )

    if not rows:
        print(f"No XML files or no names found under: {INBOX}")
        return 0

    # ---- header with new similarity fields
    fields = [
        "run_ts",                    # NEW: add run timestamp as the first column
        "file",
        "msg_type",
        "msg_type_full",
        "role",
        "original",
        "step_nfkc",
        "step_no_diacritics",
        "step_casefold",
        "step_punct_ws",
        "final_match",
        "decision",
        "top_hit_score",
        "top_hit_name",
        "top_hit_source",
        "top_hit_token_overlap",     # NEW
        "top_hit_jaro_winkler",      # NEW
        "top_hit_levenshtein_norm",  # NEW
    ]
    with OUTCSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            # Inject the run timestamp per row
            r = {"run_ts": RUN_TS, **r}
            w.writerow(r)

    print(f"Wrote audit → {OUTCSV}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
