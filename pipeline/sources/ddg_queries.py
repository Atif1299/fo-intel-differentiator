"""Class A — DuckDuckGo web discovery across fixed geo/query keys."""

from __future__ import annotations

import re
import time
from typing import Iterable

from pipeline.models import Candidate, utc_now_iso
from pipeline.normalize import candidate_id_for, normalize_name

# query_key -> (query string, geo_hint)
QUERIES: dict[str, tuple[str, str]] = {
    "sfo_ny": ('"single family office" "New York"', "New York, US"),
    "sfo_sf": ('"single family office" "San Francisco"', "San Francisco, US"),
    "sfo_chicago": ('"single family office" Chicago', "Chicago, US"),
    "sfo_miami": ('"single family office" Miami', "Miami, US"),
    "sfo_dallas": ('"single family office" Dallas', "Dallas, US"),
    "sfo_boston": ('"single family office" Boston', "Boston, US"),
    "fo_la": ('"family office" Los Angeles invest', "Los Angeles, US"),
    "fo_seattle": ('"family office" Seattle', "Seattle, US"),
    "fo_denver": ('"family office" Denver', "Denver, US"),
    "fo_atlanta": ('"family office" Atlanta', "Atlanta, US"),
    "fo_london": ('"family office" London', "London, UK"),
    "fo_invests": ('"family office" invests in OR commits to', ""),
    "fo_venture": ('"family office" venture capital portfolio', ""),
    "mfo_us": ('"multi-family office" United States', "US"),
    "sfo_texas": ('"single-family office" Texas', "Texas, US"),
    "extra_midwest": ('"family office" Minneapolis OR Detroit', "Midwest, US"),
    "extra_philly": ('"family office" Philadelphia', "Philadelphia, US"),
    "extra_phoenix": ('"family office" Phoenix', "Phoenix, US"),
}

_FO_NAME = re.compile(
    r"([A-Z][A-Za-z0-9&.\'\-]+(?:\s+[A-Z][A-Za-z0-9&.\'\-]+){0,6}\s+"
    r"(?:Family\s+Office|Capital|Partners|Holdings|Management|Investments|Wealth))",
    re.I,
)


def _extract_name(title: str, body: str) -> str | None:
    text = f"{title} {body}"
    m = _FO_NAME.search(text)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip(" -|:")
    # Fallback: title before dash/pipe
    head = re.split(r"\s+[|\-–—:]\s+", title, maxsplit=1)[0].strip()
    if "family office" in head.lower() or "capital" in head.lower():
        return head
    return None


def run(max_per_query: int = 8, pause_s: float = 0.8) -> list[Candidate]:
    ddgs_cm = None
    try:
        from ddgs import DDGS  # preferred package name

        ddgs_cm = DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS

            ddgs_cm = DDGS
        except ImportError as e:
            raise RuntimeError("Install ddgs or duckduckgo-search") from e

    out: list[Candidate] = []
    with ddgs_cm() as ddgs:
        for key, (query, geo) in QUERIES.items():
            source_id = f"ddg:{key}"
            try:
                results = list(ddgs.text(query, max_results=max_per_query))
            except Exception as exc:  # noqa: BLE001 — keep other adapters running
                print(f"[ddg] query {key} failed: {exc}")
                time.sleep(pause_s)
                continue
            for row in results:
                title = row.get("title") or ""
                body = row.get("body") or row.get("description") or ""
                href = row.get("href") or row.get("link") or row.get("url") or ""
                name = _extract_name(title, body)
                if not name:
                    continue
                nn = normalize_name(name)
                if len(nn) < 5:
                    continue
                out.append(
                    Candidate(
                        candidate_id=candidate_id_for(nn),
                        name=name,
                        name_normalized=nn,
                        website_hint=href or None,
                        geo_hint=geo or None,
                        snippet=(body or title)[:400],
                        discovery_source_class="A",
                        discovery_source_ids=[source_id],
                        discovery_urls=[href] if href else [],
                        discovered_at=utc_now_iso(),
                        raw={"query": query, "title": title},
                    )
                )
            time.sleep(pause_s)
    return out


def run_extra_batch(keys: Iterable[str] | None = None) -> list[Candidate]:
    """Rebalance batch — subset of queries with higher max_results."""
    subset = {k: QUERIES[k] for k in (keys or list(QUERIES)[-6:]) if k in QUERIES}
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return []
    out: list[Candidate] = []
    with DDGS() as ddgs:
        for key, (query, geo) in subset.items():
            source_id = f"ddg:{key}"
            try:
                results = list(ddgs.text(query, max_results=12))
            except Exception as exc:  # noqa: BLE001
                print(f"[ddg-extra] {key} failed: {exc}")
                continue
            for row in results:
                title = row.get("title") or ""
                body = row.get("body") or row.get("description") or ""
                href = row.get("href") or row.get("link") or row.get("url") or ""
                name = _extract_name(title, body)
                if not name:
                    continue
                nn = normalize_name(name)
                if len(nn) < 5:
                    continue
                out.append(
                    Candidate(
                        candidate_id=candidate_id_for(nn),
                        name=name,
                        name_normalized=nn,
                        website_hint=href or None,
                        geo_hint=geo or None,
                        snippet=(body or title)[:400],
                        discovery_source_class="A",
                        discovery_source_ids=[source_id],
                        discovery_urls=[href] if href else [],
                        discovered_at=utc_now_iso(),
                        raw={"query": query, "title": title, "extra": True},
                    )
                )
            time.sleep(0.8)
    return out
