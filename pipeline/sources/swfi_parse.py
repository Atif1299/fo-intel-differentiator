"""Class B — public ranking / directory-style HTML (SWFI + Folio / similar)."""

from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from pipeline.models import Candidate, utc_now_iso
from pipeline.normalize import candidate_id_for, normalize_name

SOURCE_ID = "swfi:fo_profiles"
UA = "FO-Intel-Differentiator/0.1 (assessment; ranaatif1299@gmail.com)"

# Distinct public pages (not one vendor dump). If a URL 404s, adapter skips.
URLS = [
    "https://www.swfinstitute.org/fund-manager-rankings/family-office",
    "https://www.swfinstitute.org/profile/family-office",
    "https://en.wikipedia.org/wiki/Cascade_Investment",  # known SFO page as structured seed
    "https://en.wikipedia.org/wiki/Bezos_Expeditions",
]


def _names_from_html(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    found: list[tuple[str, str]] = []
    # Tables and lists
    for sel in ("table tr td", "li", "h2", "h3", "a"):
        for el in soup.select(sel):
            text = el.get_text(" ", strip=True)
            if not text or len(text) > 100 or len(text) < 5:
                continue
            if not re.search(r"[A-Za-z]", text):
                continue
            # Avoid pure navigation
            if text.lower() in {"home", "login", "subscribe", "family office"}:
                continue
            href = ""
            if el.name == "a" and el.get("href"):
                href = el["href"]
                if href.startswith("/"):
                    # resolve roughly
                    from urllib.parse import urljoin

                    href = urljoin(base_url, href)
            found.append((text, href))
    return found


def run() -> list[Candidate]:
    out: list[Candidate] = []
    seen: set[str] = set()
    headers = {"User-Agent": UA}
    with httpx.Client(timeout=30.0, headers=headers, follow_redirects=True) as client:
        for url in URLS:
            try:
                r = client.get(url)
                if r.status_code >= 400:
                    print(f"[swfi] skip {url} status={r.status_code}")
                    continue
            except Exception as exc:  # noqa: BLE001
                print(f"[swfi] fetch failed {url}: {exc}")
                continue
            for name, href in _names_from_html(r.text, url):
                # Prefer FO-ish
                nl = name.lower()
                if "family office" in nl or any(
                    k in nl for k in ("capital", "investment", "partners", "holdings", "wealth", "expeditions", "cascade")
                ):
                    pass
                else:
                    continue
                nn = normalize_name(name)
                if nn in seen or len(nn) < 4:
                    continue
                # Drop sentences
                if len(name.split()) > 10:
                    continue
                seen.add(nn)
                urls = [url]
                if href:
                    urls.append(href)
                out.append(
                    Candidate(
                        candidate_id=candidate_id_for(nn),
                        name=name,
                        name_normalized=nn,
                        website_hint=href or None,
                        geo_hint=None,
                        snippet=f"Listed/linked from {url}",
                        discovery_source_class="B",
                        discovery_source_ids=[SOURCE_ID],
                        discovery_urls=urls,
                        discovered_at=utc_now_iso(),
                        raw={"page": url},
                    )
                )
    return out
