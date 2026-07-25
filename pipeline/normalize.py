"""Name normalization and id helpers for discovery dedupe."""

from __future__ import annotations

import hashlib
import re

_SUFFIXES = re.compile(
    r"\b(llc|l\.l\.c\.|inc|incorporated|ltd|limited|lp|l\.p\.|llp|"
    r"corp|corporation|co|company|plc|sa|ag|nv|bv|gmbh)\b\.?",
    re.I,
)
_NON_ALNUM = re.compile(r"[^a-z0-9\s]+")
_WS = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    s = name.strip().lower()
    s = _SUFFIXES.sub(" ", s)
    s = _NON_ALNUM.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    return s


def candidate_id_for(name_normalized: str) -> str:
    if not name_normalized:
        name_normalized = "unknown"
    digest = hashlib.sha1(name_normalized.encode("utf-8")).hexdigest()[:10]
    slug = name_normalized.replace(" ", "-")[:48].strip("-")
    return f"{slug}-{digest}"


def looks_like_org_name(name: str) -> bool:
    """Heuristic filter for RSS/title extraction."""
    n = name.strip()
    if len(n) < 4 or len(n) > 120:
        return False
    if n.lower() in {"family office", "family offices", "the family office"}:
        return False
    # Prefer names with Capital letters or FO keywords
    words = n.split()
    if len(words) < 2:
        return False
    return True
