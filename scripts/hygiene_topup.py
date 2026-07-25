"""One-off hygiene fill: DDG top-up until one unique validated FO exists."""
from __future__ import annotations

import json
import re
from pathlib import Path

from pipeline.enrich import OUT, _load_enriched, _shippable_count, enrich_one
from pipeline.models import Candidate
from pipeline.normalize import candidate_id_for, looks_like_org_name, normalize_name
from pipeline.validate_lib.checks import inclusion_checks, website_domain

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

ROOT = Path(__file__).resolve().parents[1]
VAL = ROOT / "data" / "processed" / "validated.jsonl"


def main() -> None:
    validated = [
        json.loads(l)
        for l in VAL.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    v_names = {
        normalize_name(r.get("common_name") or r.get("legal_name") or "")
        for r in validated
    }
    v_dom = {
        website_domain(r.get("website"))
        for r in validated
        if website_domain(r.get("website"))
    }

    existing = _load_enriched()
    existing_names = {
        normalize_name(e.get("common_name") or e.get("legal_name") or e.get("name") or "")
        for e in existing
    }

    queries = [
        "single family office official website -list -jobs -hiring",
        "family office managing the wealth of our family about",
    ]
    added = 0
    with DDGS() as ddgs:
        for q in queries:
            for row in list(ddgs.text(q, max_results=10)):
                title = (row.get("title") or "").split("|")[0].split(" - ")[0].strip()
                href = row.get("href") or row.get("link") or ""
                if not looks_like_org_name(title):
                    continue
                low = title.lower()
                if low in {
                    "family office",
                    "single family office",
                    "multi family office",
                    "confidential single family office",
                } or "confidential" in low and "family office" in low:
                    continue
                if re.search(r"^(the\s+)?(shared\s+)?single[-\s]?family\s+office", low):
                    continue
                norm = normalize_name(title)
                if norm in v_names or norm in existing_names:
                    continue
                c = Candidate(
                    candidate_id=candidate_id_for(norm),
                    name=title[:100],
                    name_normalized=norm,
                    website_hint=href or None,
                    snippet=row.get("body"),
                    discovery_source_class="A",
                    discovery_source_ids=["ddg:hygiene_topup"],
                    discovery_urls=[href] if href else [],
                )
                print(f"try {title[:60]}")
                rec = enrich_one(c.model_dump())
                print(
                    " ",
                    rec.get("inclusion_pass"),
                    rec.get("fo_type"),
                    (rec.get("inclusion_evidence_summary") or "")[:100],
                )
                existing.append(rec)
                existing_names.add(norm)
                added += 1
                probe = json.loads(json.dumps(rec))
                if inclusion_checks(probe) is not None:
                    continue
                nk = normalize_name(probe.get("common_name") or probe.get("legal_name") or "")
                d = website_domain(probe.get("website"))
                if nk in v_names:
                    continue
                if d and d in v_dom:
                    continue
                print("FILL_OK", probe.get("common_name"), probe.get("website"))
                with OUT.open("w", encoding="utf-8") as f:
                    for r in existing:
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
                print("shippable", _shippable_count(existing), "added", added)
                return
            if added >= 8:
                break

    with OUT.open("w", encoding="utf-8") as f:
        for r in existing:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("no_fill added", added)


if __name__ == "__main__":
    main()
