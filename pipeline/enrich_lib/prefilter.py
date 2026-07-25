"""Drop obvious non-entity discovery noise."""

from __future__ import annotations

import re
from typing import Any

_BAD_EXACT = {
    "home",
    "login",
    "subscribe",
    "family office",
    "family offices",
    "single family office",
    "single-family office",
    "multi family office",
    "multi-family office",
    "multi family offices",
    "largest single family office",
    "private equity",
    "notable investments",
    "1 notable investments",
    "investments",
    "about",
    "contact",
    "careers",
}

_BAD_PREFIX = re.compile(
    r"^(?:\d+\s+)?(?:notable|related|see also|references|external links)\b",
    re.I,
)

# Category / list-title crumbs with no proper noun entity
_GENERIC_FO = re.compile(
    r"^(?:the\s+)?(?:largest|top|best|leading|biggest)?\s*"
    r"(?:single[-\s]?family|multi[-\s]?family|family)\s+offices?\s*$",
    re.I,
)


def is_junk_name(name: str) -> bool:
    n = (name or "").strip()
    if not n or len(n) < 4:
        return True
    low = n.lower()
    if low in _BAD_EXACT:
        return True
    if _BAD_PREFIX.match(low):
        return True
    if _GENERIC_FO.match(n):
        return True
    tokens = re.findall(r"[A-Za-z0-9]+", n)
    if len(tokens) < 2 and "family" not in low:
        return True
    # Pure navigation / table crumbs
    if low.startswith(("http://", "https://", "www.")):
        return True
    return False


def prefilter(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for c in candidates:
        name = c.get("name") or ""
        if is_junk_name(name):
            dropped.append({**c, "drop_reason": "junk_name"})
        else:
            kept.append(c)
    return kept, dropped
