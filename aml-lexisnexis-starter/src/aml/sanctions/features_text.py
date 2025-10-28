"""
Text similarity features for name screening.

Exposes:
- levenshtein_norm(a, b): normalized Levenshtein similarity in [0, 1]
- jaro_winkler(a, b): Jaro–Winkler similarity in [0, 1]
- token_overlap(a, b): Jaccard token overlap in [0, 1]
"""

from __future__ import annotations
from typing import Iterable, Tuple

# ----------------------------
# Utilities
# ----------------------------

def _normalize_pair(a: str | None, b: str | None) -> Tuple[str, str]:
    a = (a or "").strip().lower()
    b = (b or "").strip().lower()
    return a, b

# ----------------------------
# Levenshtein (normalized)
# ----------------------------

def levenshtein_norm(a: str | None, b: str | None) -> float:
    """
    Normalized Levenshtein similarity = 1 - dist/max(len(a), len(b)).
    Returns 1.0 if both strings are empty.
    """
    a, b = _normalize_pair(a, b)
    if not a and not b:
        return 1.0
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 0.0

    # DP with two rows (O(min(la, lb)) memory)
    if la < lb:
        a, b = b, a
        la, lb = lb, la

    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        ca = a[i - 1]
        for j in range(1, lb + 1):
            cb = b[j - 1]
            cost = 0 if ca == cb else 1
            curr[j] = min(
                prev[j] + 1,      # deletion
                curr[j - 1] + 1,  # insertion
                prev[j - 1] + cost,  # substitution
            )
        prev = curr

    dist = prev[lb]
    denom = max(la, lb)
    return max(0.0, 1.0 - dist / denom)

# ----------------------------
# Jaro–Winkler
# ----------------------------

def _jaro(a: str, b: str) -> float:
    # Implementation per standard definition
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 0.0

    match_distance = max(0, max(la, lb) // 2 - 1)

    a_matches = [False] * la
    b_matches = [False] * lb

    matches = 0
    transpositions = 0

    # Count matches
    for i in range(la):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, lb)
        for j in range(start, end):
            if b_matches[j]:
                continue
            if a[i] != b[j]:
                continue
            a_matches[i] = True
            b_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    # Count transpositions
    k = 0
    for i in range(la):
        if not a_matches[i]:
            continue
        while not b_matches[k]:
            k += 1
        if a[i] != b[k]:
            transpositions += 1
        k += 1

    transpositions //= 2

    return (
        (matches / la) +
        (matches / lb) +
        ((matches - transpositions) / matches)
    ) / 3.0


def jaro_winkler(a: str | None, b: str | None, p: float = 0.1, max_prefix: int = 4) -> float:
    """
    Jaro–Winkler similarity in [0, 1].
    p is the prefix scale (default 0.1), max_prefix typically 4.
    """
    a, b = _normalize_pair(a, b)
    if not a and not b:
        return 1.0
    j = _jaro(a, b)
    # Common prefix length up to max_prefix
    prefix = 0
    for ca, cb in zip(a, b):
        if ca == cb:
            prefix += 1
            if prefix == max_prefix:
                break
        else:
            break
    return j + prefix * p * (1.0 - j)

# ----------------------------
# Token overlap (Jaccard)
# ----------------------------

def _simple_tokens(s: str) -> Iterable[str]:
    # Split on whitespace after lowercasing (assumes upstream normalization)
    return [t for t in s.lower().split() if t]

def token_overlap(a: str | None, b: str | None) -> float:
    """
    Jaccard overlap of whitespace tokens, in [0, 1].
    """
    a, b = _normalize_pair(a, b)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    ta, tb = set(_simple_tokens(a)), set(_simple_tokens(b))
    if not ta and not tb:
        return 1.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


# ----------------------------
# Quick self-test (optional)
# ----------------------------
if __name__ == "__main__":
    q = "muhammad ali"
    k = "mohammad ali"
    print("lev:", round(levenshtein_norm(q, k), 4))
    print("jw :", round(jaro_winkler(q, k), 4))
    print("tok:", round(token_overlap(q, k), 4))
