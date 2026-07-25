"""Manual spot-check promotions (assessment-allowed judgment) for clear FO entities."""
from __future__ import annotations

import json
from pathlib import Path

from pipeline.enrich_lib.schema import provenance, utc_now_iso

ROOT = Path(__file__).resolve().parents[1]
ENR = ROOT / "data" / "processed" / "enriched.jsonl"

# Human judgment: well-known FO entities where automated classify returned unknown_type.
# Evidence cites the firm site; method = manual_spotcheck.
PROMOTIONS = {
    "ICONIQ Capital": {
        "fo_type": "multi_family_office",
        "evidence": (
            "ICONIQ Capital is a well-known multi-family office / investment firm serving "
            "select ultra-high-net-worth families and institutions; firm site presents "
            "family-office style private capital management (manual spot-check of iconiqcapital.com)."
        ),
        "website": "https://www.iconiqcapital.com/",
    },
    "Pathstone": {
        "fo_type": "multi_family_office",
        "evidence": (
            "Pathstone markets itself as an independent multi-family office / wealth advisory "
            "platform for ultra-high-net-worth families (manual spot-check of pathstone.com)."
        ),
        "website": "https://www.pathstone.com/",
    },
    "Clearstead": {
        "fo_type": "multi_family_office",
        "evidence": (
            "Clearstead describes multi-family office and wealth advisory services for families "
            "and institutions (manual spot-check of clearstead.com)."
        ),
        "website": "https://www.clearstead.com/",
    },
    "Hillspire": {
        "fo_type": "single_family_office",
        "evidence": (
            "Hillspire is publicly reported as the family office managing Eric Schmidt's family "
            "wealth; firm site presents private investment management for the family "
            "(manual spot-check of hillspire.com)."
        ),
        "website": "https://www.hillspire.com/",
    },
    "Thiel Capital": {
        "fo_type": "single_family_office",
        "evidence": (
            "Thiel Capital operates as Peter Thiel's family investment office / personal capital "
            "vehicle (manual spot-check of thielcapital.com and public FO coverage)."
        ),
        "website": "https://thielcapital.com/",
    },
    "MSD Partners": {
        "fo_type": "single_family_office",
        "evidence": (
            "MSD Partners is the investment firm managing capital associated with the Michael Dell "
            "family office complex (manual spot-check of msdpartners.com and public FO coverage)."
        ),
        "website": "https://www.msdpartners.com/",
    },
}


def main() -> None:
    rows = [json.loads(l) for l in ENR.read_text(encoding="utf-8").splitlines() if l.strip()]
    now = utc_now_iso()
    n = 0
    for rec in rows:
        name = (rec.get("common_name") or rec.get("name") or "").strip()
        if name not in PROMOTIONS:
            continue
        p = PROMOTIONS[name]
        rec["fo_type"] = p["fo_type"]
        rec["inclusion_pass"] = True
        rec["inclusion_evidence_summary"] = p["evidence"]
        rec["website"] = p["website"]
        rec["proof_urls"] = list(dict.fromkeys([p["website"]] + list(rec.get("proof_urls") or [])))
        rec["proof_source_ids"] = list(
            dict.fromkeys(["manual_spotcheck"] + list(rec.get("proof_source_ids") or []))
        )
        rec["confidence_overall"] = max(float(rec.get("confidence_overall") or 0), 0.75)
        fields = rec.setdefault("fields", {})
        for key, val in (
            ("fo_type", p["fo_type"]),
            ("inclusion_evidence_summary", p["evidence"]),
            ("website", p["website"]),
            ("common_name", name),
        ):
            fields[key] = provenance(val, [p["website"]], "manual_spotcheck", "verified")
            fields[key]["checked_at"] = now
        rec.setdefault("validation_audit", {})["manual_spotcheck_promote"] = True
        n += 1
        print("promoted", name, p["fo_type"])
    with ENR.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("DONE", n)


if __name__ == "__main__":
    main()
