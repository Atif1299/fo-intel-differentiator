"""
Stage: validate
Input: data/processed/enriched.jsonl
Output: data/processed/validated.jsonl + data/audit/rejected.jsonl + validate_stats.json

Validation layer (separate from production enrich):
- Rule 2: firm must have affirmative FO evidence
- Rule 1: cell status integrity; findings govern release
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.enrich_lib.schema import utc_now_iso
from pipeline.validate_lib.checks import (
    blank_contact,
    contact_needs_blank,
    dedupe_keys,
    inclusion_checks,
    maybe_improve_geo_name,
)

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
AUDIT = ROOT / "data" / "audit"
IN_PATH = PROCESSED / "enriched.jsonl"
PASS_PATH = PROCESSED / "validated.jsonl"
REJECT_PATH = AUDIT / "rejected.jsonl"
STATS_PATH = PROCESSED / "validate_stats.json"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _apply_contact_governance(record: dict[str, Any]) -> dict[str, Any]:
    audit: dict[str, Any] = {}
    for key in ("principal_email", "principal_phone"):
        if contact_needs_blank(key, record):
            blank_contact(record, key, audit)
    if audit:
        record.setdefault("validation_audit", {}).update(audit)
    return record


def validate() -> tuple[Path, Path]:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)

    enriched = _load_jsonl(IN_PATH)
    # Sort for deterministic dedupe: higher confidence wins
    enriched_sorted = sorted(
        enriched,
        key=lambda r: float(r.get("confidence_overall") or 0.0),
        reverse=True,
    )

    seen_names: set[str] = set()
    seen_domains: set[str] = set()
    passed: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    reasons: dict[str, int] = {}

    for rec in enriched_sorted:
        row = json.loads(json.dumps(rec))  # deep copy
        reason = inclusion_checks(row)
        if reason:
            row["rejection_reason"] = reason
            rejected.append(row)
            reasons[reason] = reasons.get(reason, 0) + 1
            continue

        name_key, domain = dedupe_keys(row)
        if name_key and name_key in seen_names:
            row["rejection_reason"] = "duplicate_name"
            rejected.append(row)
            reasons["duplicate_name"] = reasons.get("duplicate_name", 0) + 1
            continue
        if domain and domain in seen_domains:
            row["rejection_reason"] = "duplicate_website_domain"
            rejected.append(row)
            reasons["duplicate_website_domain"] = reasons.get("duplicate_website_domain", 0) + 1
            continue

        row = _apply_contact_governance(row)
        maybe_improve_geo_name(row)
        row["validated_at"] = utc_now_iso()
        if name_key:
            seen_names.add(name_key)
        if domain:
            seen_domains.add(domain)
        passed.append(row)

    with PASS_PATH.open("w", encoding="utf-8") as f:
        for r in passed:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with REJECT_PATH.open("w", encoding="utf-8") as f:
        for r in rejected:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    by_type: dict[str, int] = {}
    for r in passed:
        t = r.get("fo_type") or "?"
        by_type[t] = by_type.get(t, 0) + 1

    stats = {
        "input_enriched": len(enriched),
        "passed": len(passed),
        "rejected": len(rejected),
        "rejection_reasons": reasons,
        "passed_by_fo_type": by_type,
        "finished_at": utc_now_iso(),
    }
    STATS_PATH.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    return PASS_PATH, REJECT_PATH


def main() -> None:
    passed, rejected = validate()

    def count(path: Path) -> int:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())

    print(f"[validate] pass={count(passed)} reject={count(rejected)}")
    print(f"  {passed}")
    print(f"  {rejected}")
    print(f"  stats={STATS_PATH}")


if __name__ == "__main__":
    main()
