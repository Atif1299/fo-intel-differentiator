"""Class A — SEC EDGAR full-text search for 'family office'."""

from __future__ import annotations

import re

import httpx

from pipeline.models import Candidate, utc_now_iso
from pipeline.normalize import candidate_id_for, normalize_name

EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
SOURCE_ID = "edgar:full_text_fo"
UA = "FO-Intel-Differentiator/0.1 (assessment; ranaatif1299@gmail.com)"

_ENTITY = re.compile(
    r"([A-Z][A-Za-z0-9&.,'\-]+(?:\s+[A-Z][A-Za-z0-9&.,'\-]+){0,8})",
)


def run(max_hits: int = 80) -> list[Candidate]:
    params = {
        "q": '"family office"',
        "dateRange": "custom",
        "startdt": "2018-01-01",
        "enddt": "2026-12-31",
        "forms": "13F-HR,10-K,10-Q,ADV",
    }
    headers = {"User-Agent": UA, "Accept": "application/json"}
    out: list[Candidate] = []
    try:
        with httpx.Client(timeout=45.0, headers=headers, follow_redirects=True) as client:
            # EDGAR efts often wants POST JSON
            r = client.get(EFTS_URL, params={**params, "from": 0, "size": max_hits})
            if r.status_code >= 400:
                r = client.post(
                    EFTS_URL,
                    json={
                        "q": '"family office"',
                        "dateRange": "custom",
                        "startdt": "2018-01-01",
                        "enddt": "2026-12-31",
                        "from": 0,
                        "size": max_hits,
                    },
                )
            r.raise_for_status()
            data = r.json()
    except Exception as exc:  # noqa: BLE001
        print(f"[edgar] search failed: {exc}")
        return out

    hits = (
        data.get("hits", {}).get("hits")
        if isinstance(data.get("hits"), dict)
        else data.get("hits")
        or data.get("results")
        or []
    )
    if not isinstance(hits, list):
        hits = []

    seen: set[str] = set()
    for hit in hits[:max_hits]:
        src = hit.get("_source") or hit.get("source") or hit
        display = (
            src.get("display_names")
            or src.get("entity_name")
            or src.get("name")
            or src.get("cik")
            or ""
        )
        if isinstance(display, list):
            display = display[0] if display else ""
        display = str(display)
        # Strip (CIK) suffixes common in EDGAR
        display = re.sub(r"\s*\(\d+\)\s*$", "", display).strip()
        if not display or len(display) < 4:
            # try file description
            display = str(src.get("file_description") or src.get("period_of_report") or "")
            m = _ENTITY.search(display)
            display = m.group(1) if m else ""
        if not display:
            continue
        nn = normalize_name(display)
        if nn in seen or len(nn) < 4:
            continue
        seen.add(nn)
        adsh = src.get("adsh") or src.get("id") or ""
        url = f"https://www.sec.gov/Archives/edgar/data/" if not adsh else f"https://efts.sec.gov/LATEST/search-index?q={display}"
        out.append(
            Candidate(
                candidate_id=candidate_id_for(nn),
                name=display,
                name_normalized=nn,
                website_hint=None,
                geo_hint="US",
                snippet=str(src.get("file_description") or src.get("form") or "EDGAR hit: family office")[:400],
                discovery_source_class="A",
                discovery_source_ids=[SOURCE_ID],
                discovery_urls=[url],
                discovered_at=utc_now_iso(),
                raw={"edgar": {k: src.get(k) for k in ("form", "adsh", "ciks", "file_date") if k in src}},
            )
        )
    return out
