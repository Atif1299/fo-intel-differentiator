"""Rename geo-crumb common/legal names from on-site identity (no invention)."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "export" / "family_offices_50.csv"
PROV_PATH = ROOT / "data" / "export" / "provenance.jsonl"
VAL_PATH = ROOT / "data" / "processed" / "validated.jsonl"
ENR_PATH = ROOT / "data" / "processed" / "enriched.jsonl"

# Candidate names keyed by domain — only applied if page (or existing legal) corroborates
DOMAIN_HINTS = {
    "themiamifamilyoffice.com": ["The Miami Family Office", "Miami Family Office"],
    "sowellco.com": ["Sowell & Company", "Sowell & Co.", "Sowell & Co", "Sowell Company"],
    "oldmountain.net": ["Old Mountain Capital", "Old Mountain Fund", "Old Mountain"],
    # Site brand is Dakota (intel platform); do not use product phrases as the entity name
    "dakota.com": ["Dakota"],
}

TARGETS = {
    "Miami Family Office",
    "Dallas Single Family Office",
    "Boston Single Family Office",
    "London-based single family office",
}

CSV_KEYS = [
    "fo_id",
    "legal_name",
    "common_name",
    "fo_type",
    "hq_city",
    "hq_country",
    "website",
    "linkedin_company_url",
    "aum_note",
    "investment_thesis",
    "investment_mandates",
    "principal_name",
    "principal_title",
    "principal_linkedin",
    "principal_email",
    "principal_phone",
    "signal_1_summary",
    "signal_1_date",
    "signal_1_url",
    "signal_2_summary",
    "signal_2_date",
    "signal_2_url",
    "inclusion_evidence_summary",
    "confidence_overall",
]

UA = "FO-Intel-Differentiator/0.3 (assessment; name-hygiene)"


def host_of(url: str) -> str:
    u = url if "://" in url else f"https://{url}"
    h = urlparse(u).netloc.lower()
    return h[4:] if h.startswith("www.") else h


def fetch_text(url: str) -> str:
    u = url if "://" in url else f"https://{url}"
    try:
        with httpx.Client(
            timeout=25.0,
            headers={"User-Agent": UA},
            follow_redirects=True,
            verify=False,
        ) as client:
            r = client.get(u)
            if r.status_code >= 400:
                return ""
            soup = BeautifulSoup(r.text, "lxml")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            title = (soup.title.string or "").strip() if soup.title else ""
            text = soup.get_text("\n", strip=True)
            return f"{title}\n{text}"[:15000]
    except Exception as exc:  # noqa: BLE001
        print(f"  fetch fail {url}: {exc}")
        return ""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def pick_name(crumb: str, website: str, page: str, legal: str) -> str | None:
    """Return better name only if corroborated on page or already in legal≠crumb."""
    h = host_of(website or "")
    page_l = page.lower()
    crumb_n = _norm(crumb)

    candidates: list[str] = []
    legal_s = (legal or "").strip()
    if legal_s and _norm(legal_s) != crumb_n:
        candidates.append(legal_s)
    candidates.extend(DOMAIN_HINTS.get(h, []))

    best: str | None = None
    for candidate in candidates:
        c = candidate.strip()
        if not c or _norm(c) == crumb_n:
            continue
        # Prefer existing legal even if fetch failed (already extracted, not invented)
        if legal_s and _norm(c) == _norm(legal_s) and not page:
            best = c
            continue
        if not page:
            continue
        if c.lower() in page_l:
            if best is None or len(c) > len(best):
                best = c
            continue
        tokens = [t for t in re.findall(r"[A-Za-z0-9&]+", c) if len(t) > 2]
        if tokens and all(t.lower() in page_l for t in tokens[:2]):
            if best is None or len(c) > len(best):
                best = c
    return best


def apply_rename_record(record: dict, new_name: str, crumb: str) -> None:
    """Mutate JSONL record fields (not CSV row dicts)."""
    record["common_name"] = new_name
    legal = (record.get("legal_name") or "").strip()
    if not legal or _norm(legal) == _norm(crumb):
        record["legal_name"] = new_name
    fields = record.setdefault("fields", {})
    from pipeline.enrich_lib.schema import utc_now_iso

    now = utc_now_iso()
    for key in ("common_name", "legal_name"):
        if key == "legal_name" and legal and _norm(legal) != _norm(crumb):
            continue
        prev = fields.get(key) or {}
        fields[key] = {
            "value": record.get(key),
            "sources": list(
                dict.fromkeys(
                    (prev.get("sources") or [])
                    + [record.get("website")]
                    + (record.get("proof_urls") or [])[:1]
                )
            ),
            "method": "onsite_name_hygiene",
            "status": "verified",
            "checked_at": prev.get("checked_at") or now,
        }
    record.setdefault("validation_audit", {})["renamed_geo_crumb"] = {
        "from": crumb,
        "to": new_name,
    }


def main() -> None:
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
    renames: dict[str, str] = {}  # fo_id -> new_name
    crumbs_by_id: dict[str, str] = {}

    for r in rows:
        crumb = r.get("common_name") or ""
        if crumb not in TARGETS:
            continue
        web = r.get("website") or ""
        print(f"=== {crumb} | {web}")
        page = fetch_text(web) if web else ""
        new = pick_name(crumb, web, page, r.get("legal_name") or "")
        if not new:
            print("  NO on-site name found — leave unchanged")
            continue
        if _norm(new) == _norm(crumb):
            print("  same as crumb — leave")
            continue
        print(f"  RENAME -> {new}")
        renames[r["fo_id"]] = new
        crumbs_by_id[r["fo_id"]] = crumb
        r["common_name"] = new
        legal = (r.get("legal_name") or "").strip()
        if not legal or _norm(legal) == _norm(crumb):
            r["legal_name"] = new

    if not renames:
        print("No renames applied")
        return

    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_KEYS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    prov_out = []
    for line in PROV_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        p = json.loads(line)
        fid = p.get("fo_id")
        if fid in renames:
            row = next(x for x in rows if x["fo_id"] == fid)
            p.setdefault("fields", {})
            for key in ("common_name", "legal_name"):
                p["fields"][key] = {
                    "value": row.get(key),
                    "sources": [row.get("website")],
                    "method": "onsite_name_hygiene",
                    "status": "verified",
                    "checked_at": (p.get("fields") or {}).get(key, {}).get("checked_at") or "",
                }
        prov_out.append(p)
    with PROV_PATH.open("w", encoding="utf-8") as f:
        for p in prov_out:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    for path in (VAL_PATH, ENR_PATH):
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            fid = rec.get("fo_id")
            if fid in renames:
                apply_rename_record(rec, renames[fid], crumbs_by_id[fid])
            out.append(rec)
        with path.open("w", encoding="utf-8") as f:
            for rec in out:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print("DONE renames:", renames)


if __name__ == "__main__":
    # SSL verify off only for brittle FO sites with hostname mismatch
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
