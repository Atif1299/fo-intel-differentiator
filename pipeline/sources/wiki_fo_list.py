"""Class B — Wikipedia pages that list / mention family offices."""

from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from pipeline.models import Candidate, utc_now_iso
from pipeline.normalize import candidate_id_for, normalize_name

SOURCE_ID = "wiki:list_family_offices"
UA = "FO-Intel-Differentiator/0.1 (assessment; ranaatif1299@gmail.com)"

# Multiple wiki entry points so Class B is not a single HTML scrape of one table
PAGES = [
    "https://en.wikipedia.org/wiki/Family_office",
    "https://en.wikipedia.org/wiki/List_of_wealthiest_families",
    "https://en.wikipedia.org/wiki/Private_equity_firm",
]


def run() -> list[Candidate]:
    out: list[Candidate] = []
    seen: set[str] = set()
    headers = {"User-Agent": UA}
    with httpx.Client(timeout=30.0, headers=headers, follow_redirects=True) as client:
        for url in PAGES:
            try:
                r = client.get(url)
                r.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                print(f"[wiki] fetch failed {url}: {exc}")
                continue
            soup = BeautifulSoup(r.text, "lxml")
            for a in soup.select("a[href^='/wiki/']"):
                title = (a.get("title") or a.get_text() or "").strip()
                href = a.get("href") or ""
                if not title or ":" in href:  # skip File:, Category: etc. partially
                    if any(x in href for x in ("File:", "Category:", "Help:", "Wikipedia:", "Template:")):
                        continue
                if len(title) < 4:
                    continue
                # Keep org-like links near FO context or with Capital/Partners/etc.
                tl = title.lower()
                parent_text = (a.parent.get_text(" ", strip=True) if a.parent else "")[:200].lower()
                if "family office" not in parent_text and "family office" not in tl:
                    if not any(k in tl for k in ("capital", "partners", "holdings", "wealth", "family")):
                        continue
                if tl.startswith("list of") or tl in {"family office", "private equity"}:
                    continue
                nn = normalize_name(title)
                if nn in seen or len(nn) < 4:
                    continue
                seen.add(nn)
                full = "https://en.wikipedia.org" + href
                out.append(
                    Candidate(
                        candidate_id=candidate_id_for(nn),
                        name=title,
                        name_normalized=nn,
                        website_hint=full,
                        geo_hint=None,
                        snippet=parent_text[:400] if parent_text else title,
                        discovery_source_class="B",
                        discovery_source_ids=[SOURCE_ID],
                        discovery_urls=[url, full],
                        discovered_at=utc_now_iso(),
                        raw={"wiki_page": url},
                    )
                )
    return out
