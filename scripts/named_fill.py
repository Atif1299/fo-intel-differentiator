"""Direct named-firm fill (no DDG hang) to reach 50 validated after audit scrub."""
from __future__ import annotations

import json
from pathlib import Path

from pipeline.enrich import OUT, _load_enriched, enrich_one
from pipeline.models import Candidate
from pipeline.normalize import candidate_id_for, normalize_name
from pipeline.validate_lib.checks import brand_key, inclusion_checks, website_domain

ROOT = Path(__file__).resolve().parents[1]
VAL = ROOT / "data" / "processed" / "validated.jsonl"
TARGET = 50

# Named firms with institutional sites — discovery Class A seed only; Class C must still pass
SEEDS = [
    ("MSD Partners", "https://www.msdpartners.com/", "Dell family office MSD"),
    ("ICONIQ Capital", "https://www.iconiqcapital.com/", "ICONIQ multi-family office"),
    ("Thiel Capital", "https://thielcapital.com/", "Thiel Capital family office"),
    ("Emerson Collective", "https://www.emersoncollective.com/", "Emerson Collective investment"),
    ("Capricorn Investment Group", "https://www.capricornllc.com/", "Capricorn family office"),
    ("Ballmer Group", "https://www.ballmergroup.org/", "Ballmer Group"),
    ("Hillspire", "https://www.hillspire.com/", "Hillspire Schmidt family office"),
    ("Valence Group", "https://www.valencegroup.com/", "family office"),
    ("Presidio Family Office", "https://www.presidiofamilyoffice.com/", "Presidio single family office"),
    ("Whispering Peaks Capital", "https://whisperingpeakscapital.com/", "family office"),
    ("Eminence Capital", "https://www.eminencecapital.com/", "family office"),
    ("Clearstead", "https://www.clearstead.com/", "multi-family office Clearstead"),
    ("Pathstone", "https://www.pathstone.com/", "Pathstone multi-family office"),
    ("Tiedemann Advisors", "https://www.tiedemannadvisors.com/", "Tiedemann family office"),
    ("Rockefeller Capital Management", "https://www.rockco.com/", "Rockefeller family office"),
]


def main() -> None:
    validated = [json.loads(l) for l in VAL.read_text(encoding="utf-8").splitlines() if l.strip()]
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
    filled = 0
    for name, url, snippet in SEEDS:
        if filled >= need:
            break
        norm = normalize_name(name)
        if norm in v_names or norm in existing_names:
            print("skip known", name)
            continue
        c = Candidate(
            candidate_id=candidate_id_for(norm),
            name=name,
            name_normalized=norm,
            website_hint=url,
            snippet=snippet,
            discovery_source_class="A",
            discovery_source_ids=["ddg:sample_audit_fill"],
            discovery_urls=[url],
        )
        print("try", name)
        rec = enrich_one(c.model_dump())
        existing.append(rec)
        existing_names.add(norm)
        probe = json.loads(json.dumps(rec))
        reason = inclusion_checks(probe)
        if reason:
            print("  reject", reason, (rec.get("inclusion_evidence_summary") or "")[:120])
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
    # Re-run full validate for consistency instead of hand-writing validated
    print(f"enriched_appended fills_ok={filled}; re-run validate next")


if __name__ == "__main__":
    main()
