"""Fill validated pool to 50 after sample-audit hygiene rejects."""
from __future__ import annotations

import json
import re
from pathlib import Path

from pipeline.enrich import OUT, _load_enriched, enrich_one
from pipeline.models import Candidate
from pipeline.normalize import candidate_id_for, looks_like_org_name, normalize_name
from pipeline.validate_lib.checks import brand_key, inclusion_checks, website_domain

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

ROOT = Path(__file__).resolve().parents[1]
VAL = ROOT / "data" / "processed" / "validated.jsonl"
TARGET = 50

QUERIES = [
    "single family office \"manages the wealth of\" about -jobs -hiring -list",
    "\"family office\" \"our family\" investment Seattle OR Denver OR Austin -jobs",
    "\"single-family office\" \"family's capital\" official site -network -association",
    "\"family office\" CIO \"family's assets\" United States -multi-family -jobs",
    "Willoughby Capital family office",
    "Duchossois Capital Management family office",
    "Emerson Collective family office",
    "Iconiq Capital family office",
    "Soros Fund Management family office",
    "Dell family office MSD Capital",
]


def _load_val() -> list[dict]:
    if not VAL.exists():
        return []
    return [json.loads(l) for l in VAL.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> None:
    validated = _load_val()
    v_names = {normalize_name(r.get("common_name") or r.get("legal_name") or "") for r in validated}
    v_dom = {website_domain(r.get("website")) for r in validated if website_domain(r.get("website"))}
    v_brand = {brand_key(r) for r in validated if brand_key(r)}

    existing = _load_enriched()
    existing_names = {
        normalize_name(e.get("common_name") or e.get("legal_name") or e.get("name") or "")
        for e in existing
    }

    need = TARGET - len(validated)
    print(f"validated={len(validated)} need={need}")
    if need <= 0:
        print("already at target")
        return

    filled = 0
    with DDGS() as ddgs:
        for q in QUERIES:
            if filled >= need:
                break
            try:
                hits = list(ddgs.text(q, max_results=12))
            except Exception as exc:  # noqa: BLE001
                print("ddg fail", q, exc)
                continue
            for row in hits:
                if filled >= need:
                    break
                title = (row.get("title") or "").split("|")[0].split(" - ")[0].strip()
                href = row.get("href") or row.get("link") or ""
                if not looks_like_org_name(title):
                    continue
                low = title.lower()
                if any(
                    x in low
                    for x in (
                        "jobs",
                        "hiring",
                        "salary",
                        "report",
                        "list of",
                        "what is",
                        "how to",
                        "peer network",
                    )
                ):
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
                    discovery_source_ids=["ddg:sample_audit_fill"],
                    discovery_urls=[href] if href else [],
                )
                print(f"try {title[:70]}")
                rec = enrich_one(c.model_dump())
                existing.append(rec)
                existing_names.add(norm)
                probe = json.loads(json.dumps(rec))
                if inclusion_checks(probe) is not None:
                    print("  reject", inclusion_checks(probe), (rec.get("inclusion_evidence_summary") or "")[:80])
                    continue
                nk = normalize_name(probe.get("common_name") or probe.get("legal_name") or "")
                d = website_domain(probe.get("website"))
                bk = brand_key(probe)
                if nk in v_names or (d and d in v_dom) or (bk and bk in v_brand):
                    print("  dupe", nk, d, bk)
                    continue
                print("FILL_OK", probe.get("common_name"), probe.get("fo_type"), probe.get("website"))
                validated.append(probe)
                v_names.add(nk)
                if d:
                    v_dom.add(d)
                if bk:
                    v_brand.add(bk)
                filled += 1

    with OUT.open("w", encoding="utf-8") as f:
        for r in existing:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with VAL.open("w", encoding="utf-8") as f:
        for r in validated:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"DONE filled={filled} validated_now={len(validated)}")


if __name__ == "__main__":
    main()
