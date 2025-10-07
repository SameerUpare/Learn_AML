import os
import pandas as pd
from typing import Optional, List, Dict
from .config import C, X

RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "raw")

def _normalize_columns(df):
    df = df.copy()
    df.columns = [str(c).replace('\ufeff', '').strip() for c in df.columns]
    return df

def _resolve_key(df, desired_col_name: str) -> str:
    cols = list(df.columns)
    if desired_col_name in cols:
        return desired_col_name
    norm_map = {str(c).replace('\ufeff', '').strip().lower(): c for c in cols}
    probe = desired_col_name.replace('\ufeff', '').strip().lower()
    if probe in norm_map:
        return norm_map[probe]
    raise KeyError(f"Column '{desired_col_name}' not found; have: {cols}")

def _existing(*candidates):
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def _ext(path: str) -> str:
    return os.path.splitext(path)[1].lower()

def _map_transactions_schema_if_needed(df: pd.DataFrame) -> pd.DataFrame:
    """Map non-standard transactions headers into the canonical schema if detected.

    Supports headers like: Time, Date, Sender_account, Receiver_account, Amount,
    Payment_currency, Received_currency, Sender_bank_location, Receiver_bank_location,
    Payment_type, Is_laundering, Laundering_type
    """
    have = {c.lower(): c for c in df.columns}

    # If canonical keys already present, return as-is
    canonical = {C.customer_id, C.datetime, C.amount}
    if canonical.issubset(set(df.columns)):
        return df

    # Heuristic mapping
    mapped = df.copy()

    # customer_id: prefer Sender_account
    if "sender_account" in have and C.customer_id not in mapped.columns:
        mapped[C.customer_id] = mapped[have["sender_account"]]

    # datetime: combine Date + Time if present
    if C.datetime not in mapped.columns:
        if "date" in have and "time" in have:
            dcol, tcol = have["date"], have["time"]
            mapped[C.datetime] = (
                pd.to_datetime(mapped[dcol].astype(str).str.strip() + " " + mapped[tcol].astype(str).str.strip(),
                                errors="coerce")
                .dt.strftime("%Y-%m-%dT%H:%M:%S")
            )
        elif "date" in have:
            mapped[C.datetime] = pd.to_datetime(mapped[have["date"]], errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")

    # amount
    if C.amount not in mapped.columns and "amount" in have:
        mapped[C.amount] = pd.to_numeric(mapped[have["amount"]], errors="coerce")

    # currency
    if C.currency not in mapped.columns:
        for cand in ("payment_currency", "currency"):
            if cand in have:
                mapped[C.currency] = mapped[have[cand]]
                break

    # channel
    if C.channel not in mapped.columns and "payment_type" in have:
        mapped[C.channel] = mapped[have["payment_type"]]

    # txn_id: synthesize if missing
    if C.txn_id not in mapped.columns:
        mapped[C.txn_id] = [f"T{i:012d}" for i in range(1, len(mapped) + 1)]

    # account_id: prefer Sender_account
    if C.account_id not in mapped.columns and "sender_account" in have:
        mapped[C.account_id] = mapped[have["sender_account"]]

    return mapped

def load_table(path: str, *, xml_xpath: Optional[str] = None) -> pd.DataFrame:
    """
    Load a table from CSV or XML into a DataFrame.
    XML parsing tries pandas.read_xml first; if it fails, falls back to a minimal ElementTree parser.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input not found: {path}")

    ext = _ext(path)
    if ext == ".csv":
        # Normalize columns to handle BOMs/whitespace/case inconsistencies
        df = pd.read_csv(path)
        df = _normalize_columns(df)
        df = _map_transactions_schema_if_needed(df)
        return df

    if ext != ".xml":
        raise ValueError(f"Unsupported file type: {ext}. Use .csv or .xml")

    xpath = xml_xpath or ".//*"

    # 1) Try pandas.read_xml (best when lxml is installed)
    try:
        df = pd.read_xml(path, xpath=xpath)
        if df is not None and not df.empty:
            return df
    except Exception:
        pass

    # 2) Fallback: minimal XML parsing (ElementTree)
    import xml.etree.ElementTree as ET
    tree = ET.parse(path)
    root = tree.getroot()

    # choose last path segment as item tag
    item_tag = xpath.split('/')[-1] if '/' in xpath else xpath
    if item_tag in ('.', '*', './/*'):
        first = next(iter(root.iter()), None)
        if first is not None:
            item_tag = first.tag

    rows: List[Dict] = []
    for node in root.findall(f".//{item_tag}"):
        row = {}
        # attributes
        for k, v in node.attrib.items():
            row[k] = v
        # shallow child elements (text content only)
        for child in list(node):
            text = (child.text or '').strip()
            key = child.tag
            # avoid collisions if duplicate tags appear
            if key in row:
                i = 2
                while f"{key}_{i}" in row:
                    i += 1
                key = f"{key}_{i}"
            row[key] = text
        if row:
            rows.append(row)
    return pd.DataFrame(rows)

def load_transactions(path: Optional[str] = None) -> pd.DataFrame:
    p = path or _existing(
        os.path.join(RAW_DIR, "transactions.csv"),
        os.path.join(RAW_DIR, "transactions.xml")
    )
    if not p:
        raise FileNotFoundError("transactions.csv or transactions.xml not found in data/raw/")
    return load_table(p, xml_xpath=X.transactions_xpath)

def load_lexisnexis(path: Optional[str] = None) -> pd.DataFrame:
    p = path or _existing(
        os.path.join(RAW_DIR, "lexisnexis.csv"),
        os.path.join(RAW_DIR, "lexisnexis.xml")
    )
    if not p:
        raise FileNotFoundError("lexisnexis.csv or lexisnexis.xml not found in data/raw/")
    return load_table(p, xml_xpath=X.lexisnexis_xpath)

def validate_inputs(txn_path: Optional[str] = None, ln_path: Optional[str] = None):
    try:
        t = load_transactions(txn_path)
        l = load_lexisnexis(ln_path)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    needed_t = [C.txn_id, C.customer_id, C.datetime, C.amount]
    needed_l = [C.ln_customer_id]
    ok_cols = all(col in t.columns for col in needed_t) and all(col in l.columns for col in needed_l)
    return {
        "ok": ok_cols,
        "txn_columns": list(t.columns),
        "ln_columns": list(l.columns),
        "txn_rows": len(t),
        "ln_rows": len(l),
        "hints": "For XML, adjust X.transactions_xpath / X.lexisnexis_xpath in config.py to match row elements."
    }

def join_txn_lexisnexis(txn_df: pd.DataFrame, ln_df: pd.DataFrame) -> pd.DataFrame:
    # Ensure normalized columns and resolve actual key names present in dataframes
    txn_df = _normalize_columns(txn_df)
    txn_df = _map_transactions_schema_if_needed(txn_df)
    ln_df = _normalize_columns(ln_df)
    left_key = _resolve_key(txn_df, C.customer_id)
    right_key = _resolve_key(ln_df, C.ln_customer_id)

    # Coerce join keys to consistent dtype (strings) to avoid int/object merge errors
    txn_df[left_key] = txn_df[left_key].astype(str).str.strip()
    ln_df[right_key] = ln_df[right_key].astype(str).str.strip()

    return txn_df.merge(ln_df, left_on=left_key, right_on=right_key, how="left")

import pandas as pd
from .config import C

def stream_left_join_to_csv(
    txn_path: str,
    ln_path: str,
    out_path: str = "data/processed/joined_transactions.csv",
    chunksize: int = 200_000,
    ln_keep_cols: list[str] | None = None,
):
    """
    Stream left-join transactions (CSV, chunked) to LexisNexis (CSV or XML in memory).
    Writes the joined result incrementally to `out_path` to keep RAM low.
    """
    # Load LN once (CSV or XML via your existing loader)
    ln_df = load_lexisnexis(ln_path)
    ln_df = _normalize_columns(ln_df)
    ln_key = _resolve_key(ln_df, C.ln_customer_id)

    # Keep only needed LN columns (saves RAM)
    if ln_keep_cols:
        keep = {ln_key, *ln_keep_cols}
        ln_df = ln_df[[c for c in ln_df.columns if c in keep]]

    # Stream transactions in chunks (CSV only)
    first = True
    for chunk in pd.read_csv(txn_path, chunksize=chunksize):
        chunk = _normalize_columns(chunk)
        txn_key = _resolve_key(chunk, C.customer_id)
        merged = chunk.merge(ln_df, left_on=txn_key, right_on=ln_key, how="left")
        merged.to_csv(out_path, index=False, mode=("w" if first else "a"), header=first)
        first = False

    return {"out_csv": out_path, "chunksize": chunksize, "ln_cols": ln_df.columns.tolist()}
