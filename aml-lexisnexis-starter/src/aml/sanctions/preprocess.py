# src/aml/sanctions/preprocess.py
from __future__ import annotations
import re
import unicodedata


# Zero-width chars (add more if you meet them in wild data)
_ZW = dict.fromkeys([
    0x200B,  # ZERO WIDTH SPACE
    0x200C,  # ZERO WIDTH NON-JOINER
    0x200D,  # ZERO WIDTH JOINER
    0x2060,  # WORD JOINER
    0xFEFF,  # ZERO WIDTH NO-BREAK SPACE (BOM)
], None)

# Combining mark class (used after NFKD decomposition)
_COMBINING_MARK = re.compile(r"[\u0300-\u036f]")

# ASCII punctuation + some Unicode hyphen-like, slashes, brackets → space
# (Curly quotes are normalized in a separate step before this regex.)
_PUNCT_TO_SPACE = re.compile(
    r"[-_'`,.;:(){}\[\]/\\]+"            # ASCII set
    r"|[\u2010-\u2015\u2212\u00B7]+"     # hyphen/horizontal bars, minus, middle dot
)

_WS_COLLAPSE = re.compile(r"\s+")

# ---------------------------------------------------------------------------
# Helpers for extra-clean normalization of inputs that may contain literal
# backslash-u escapes and “fancy” punctuation/space characters.
# ---------------------------------------------------------------------------

# Literal \uXXXX sequences we want to strip if they appear in the source text
# (XML literals won't be auto-decoded like Python string literals).
_LITERAL_U_ESCAPES = [
    r"\u200b", r"\u200B",  # ZERO WIDTH SPACE
    r"\u200c", r"\u200C",  # ZWNJ
    r"\u200d", r"\u200D",  # ZWJ
    r"\ufeff", r"\uFEFF",  # BOM
]

def _strip_literal_u_escapes(t: str) -> str:
    for pat in _LITERAL_U_ESCAPES:
        t = t.replace(pat, "")
    return t

# Map “fancy” punctuation and space characters to plain ASCII equivalents
_FANCY_MAP = {
    "\u2018": "'",  # ‘
    "\u2019": "'",  # ’
    "\u201C": '"',  # “
    "\u201D": '"',  # ”
    "\u00A0": " ",  # NO-BREAK SPACE
    "\u3000": " ",  # IDEOGRAPHIC SPACE
    "\u2003": " ",  # EM SPACE
    "\u2002": " ",  # EN SPACE
}

def _normalize_fancy_punct_spaces(t: str) -> str:
    return t.translate(str.maketrans(_FANCY_MAP))

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def normalize_unicode(text: str | None, form: str = "NFKC") -> str:
    """Unicode normalize + remove zero-width chars."""
    if not text:
        return ""
    t = unicodedata.normalize(form, str(text))
    t = t.translate(_ZW)
    return t

def strip_diacritics(text: str) -> str:
    """Remove diacritics by decomposing to NFKD, dropping combining marks, recompose to NFC."""
    d = unicodedata.normalize("NFKD", text)
    d = _COMBINING_MARK.sub("", d)
    return unicodedata.normalize("NFC", d)

def casefold_text(text: str) -> str:
    """Aggressive lowercase for cross-locale matching."""
    return text.casefold()

def collapse_punct_ws(text: str) -> str:
    """Replace chosen punctuation with spaces, collapse whitespace, trim."""
    t = _PUNCT_TO_SPACE.sub(" ", text)
    t = _WS_COLLAPSE.sub(" ", t).strip()
    return t

def norm_for_matching(text: str | None) -> str:
    """
    Opinionated pipeline used by screening & KB:
      1) Unicode NFKC (plus remove zero-widths)
      2) Strip literal \\uXXXX escapes (e.g., \\u200B) if present as text
      3) Normalize fancy quotes/apostrophes & space chars to ASCII
      4) Strip diacritics (Latin etc.)
      5) Casefold
      6) Collapse selected punctuation to spaces
      7) Collapse whitespace
    """
    if not text:
        return ""
    t = normalize_unicode(text, "NFKC")
    t = _strip_literal_u_escapes(t)
    t = _normalize_fancy_punct_spaces(t)
    t = strip_diacritics(t)
    t = casefold_text(t)
    t = collapse_punct_ws(t)
    return t
