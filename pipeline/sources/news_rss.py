"""Class A — Google News RSS for family office headlines."""

from __future__ import annotations

import re
from urllib.parse import quote_plus

import feedparser
import httpx

from pipeline.models import Candidate, utc_now_iso
from pipeline.normalize import candidate_id_for, looks_like_org_name, normalize_name

SOURCE_ID = "rss:google_news_fo"
UA = "FO-Intel-Differentiator/0.1 (assessment; ranaatif1299@gmail.com)"

QUERIES = [
    "single family office",
    "family office investment",
    "family office commits",
    "multi-family office",
    "family office venture",
]

_NAME_PAT = re.compile(
    r"([A-Z][A-Za-z0-9&.\'\-]+(?:\s+[A-Z][A-Za-z0-9&.\'\-]+){1,6})",
)


def _extract_names(title: str) -> list[str]:
    names: list[str] = []
    # Pattern: "X Family Office" or "X's family office"
    for m in re.finditer(
        r"([A-Z][A-Za-z0-9&.\'\-]+(?:\s+[A-Z][A-Za-z0-9&.\'\-]+){0,5})\s+Family\s+Office",
        title,
    ):
        names.append(m.group(0).strip())
    if not names:
        # Leading proper noun phrase before verb-ish words
        m = _NAME_PAT.match(title)
        if m and looks_like_org_name(m.group(1)):
            names.append(m.group(1).strip())
    return names


def run() -> list[Candidate]:
    out: list[Candidate] = []
    seen: set[str] = set()
    headers = {"User-Agent": UA}
    with httpx.Client(timeout=30.0, headers=headers, follow_redirects=True) as client:
        for q in QUERIES:
            url = (
                "https://news.google.com/rss/search?q="
                + quote_plus(q)
                + "&hl=en-US&gl=US&ceid=US:en"
            )
            try:
                r = client.get(url)
                r.raise_for_status()
                feed = feedparser.parse(r.text)
            except Exception as exc:  # noqa: BLE001
                print(f"[rss] query failed {q}: {exc}")
                continue
            for entry in feed.entries[:25]:
                title = getattr(entry, "title", "") or ""
                link = getattr(entry, "link", "") or ""
                for name in _extract_names(title):
                    if not looks_like_org_name(name):
                        continue
                    nn = normalize_name(name)
                    if nn in seen or len(nn) < 5:
                        continue
                    seen.add(nn)
                    out.append(
                        Candidate(
                            candidate_id=candidate_id_for(nn),
                            name=name,
                            name_normalized=nn,
                            website_hint=None,
                            geo_hint=None,
                            snippet=title[:400],
                            discovery_source_class="A",
                            discovery_source_ids=[SOURCE_ID],
                            discovery_urls=[link] if link else [url],
                            discovered_at=utc_now_iso(),
                            raw={"rss_query": q, "title": title},
                        )
                    )
    return out
