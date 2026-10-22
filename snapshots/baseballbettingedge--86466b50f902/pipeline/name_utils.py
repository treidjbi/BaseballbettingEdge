"""
name_utils.py
Shared pitcher/batter name normalization used across all stat fetchers.

The pipeline sources names from three different APIs:
  - TheRundown  (odds)    — may use accented or unaccented forms
  - MLB Stats   (stats)   — returns full Unicode names with accents
  - FanGraphs   (SwStr%,  batter K%) — uses its own name formatting

Each API can represent the same player differently.  A single canonical
normalize() function strips Unicode combining characters (accents) and
lowercases, making all three sources comparable without altering the
original name stored in picks.

Usage pattern — building a normalized lookup from a data source:
    lookup = {normalize(name): value for name, value in source.items()}

Resolving a name from a different source:
    value = lookup.get(normalize(query_name))
"""
import unicodedata


def normalize(name: str) -> str:
    """
    Canonical name normalizer: NFKD decompose → strip combining chars → lowercase.

    "José Berríos"  → "jose berrios"
    "Shōta Imanaga" → "shota imanaga"
    "J.T. Ginn"     → "j.t. ginn"
    "  Michael King " → "michael king"
    """
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()
