"""
Stage: export
Input: data/processed/validated.jsonl
Output: data/export/family_offices_50.csv + provenance.jsonl + export_stats.json

Hard gates:
- Exactly 50 qualifying records (or fail with clear message)
- No unknown_type
- Single discovery source ≤35% of the 50
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from pipeline.enrich_lib.schema import utc_now_iso

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "data" / "export"
IN_PATH = ROOT / "data" / "processed" / "validated.jsonl"
CSV_PATH = EXPORT / "family_offices_50.csv"
PROV_PATH = EXPORT / "provenance.jsonl"
STATS_PATH = EXPORT / "export_stats.json"

TARGET = 50
MAX_PRIMARY_SHARE = 0.35  # ≤17/50

CSV_COLUMNS = [
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


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path} — run validate first")
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _primary_source(row: dict[str, Any]) -> str:
    ids = row.get("discovery_source_ids") or []
    return ids[0] if ids else "unknown"


def select_fifty(rows: list[dict[str, Any]], target: int = TARGET) -> list[dict[str, Any]]:
    """SFO-first, then confidence; greedy under ≤35% primary discovery share."""
    sfo = [r for r in rows if r.get("fo_type") == "single_family_office"]
    mfo = [r for r in rows if r.get("fo_type") == "multi_family_office"]
    sfo.sort(key=lambda r: float(r.get("confidence_overall") or 0), reverse=True)
    mfo.sort(key=lambda r: float(r.get("confidence_overall") or 0), reverse=True)
    ordered = sfo + mfo

    max_per_source = int(target * MAX_PRIMARY_SHARE)  # 17
    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    skipped: list[dict[str, Any]] = []

    for r in ordered:
        if len(selected) >= target:
            break
        src = _primary_source(r)
        if counts[src] >= max_per_source:
            skipped.append(r)
            continue
        selected.append(r)
        counts[src] += 1

    # Fill remaining from skipped if room opened (shouldn't) or from leftover with swaps
    if len(selected) < target:
        for r in skipped + [x for x in ordered if x not in selected and x not in skipped]:
            if len(selected) >= target:
                break
            src = _primary_source(r)
            if counts[src] >= max_per_source:
                continue
            selected.append(r)
            counts[src] += 1

    return selected[:target]


def export() -> tuple[Path, Path]:
    EXPORT.mkdir(parents=True, exist_ok=True)
    rows = _load_jsonl(IN_PATH)
    if len(rows) < TARGET:
        print(
            f"ERROR: only {len(rows)} validated rows; need {TARGET}. "
            "Run enrich --resume then validate again.",
            file=sys.stderr,
        )
        sys.exit(1)

    selected = select_fifty(rows, TARGET)
    if len(selected) < TARGET:
        print(
            f"ERROR: selection yielded {len(selected)}/{TARGET} under 35% discovery gate. "
            "Need more diversified validated records.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Gate check
    primary = Counter(_primary_source(r) for r in selected)
    n = len(selected)
    shares = {k: round(v / n, 4) for k, v in primary.items()}
    max_share = max(shares.values()) if shares else 0.0
    if max_share > MAX_PRIMARY_SHARE + 1e-9:
        print(f"ERROR: discovery gate failed max_share={max_share} shares={shares}", file=sys.stderr)
        sys.exit(1)

    # Unknown type guard
    for r in selected:
        if r.get("fo_type") not in {"single_family_office", "multi_family_office"}:
            print(f"ERROR: unknown_type in export set: {r.get('fo_id')}", file=sys.stderr)
            sys.exit(1)

    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for r in selected:
            row = {c: r.get(c) for c in CSV_COLUMNS}
            writer.writerow(row)

    with PROV_PATH.open("w", encoding="utf-8") as f:
        for r in selected:
            prov = {
                "fo_id": r.get("fo_id"),
                "fields": r.get("fields") or {},
                "discovery_source_class": r.get("discovery_source_class"),
                "discovery_source_ids": r.get("discovery_source_ids") or [],
                "discovery_urls": r.get("discovery_urls") or [],
                "proof_source_ids": r.get("proof_source_ids") or [],
                "proof_urls": r.get("proof_urls") or [],
                "inclusion_pass": r.get("inclusion_pass"),
                "fo_type": r.get("fo_type"),
                "confidence_overall": r.get("confidence_overall"),
            }
            f.write(json.dumps(prov, ensure_ascii=False) + "\n")

    by_type = Counter(r.get("fo_type") for r in selected)
    stats = {
        "exported": n,
        "by_fo_type": dict(by_type),
        "primary_source_counts": dict(primary),
        "primary_source_share": shares,
        "max_primary_share": max_share,
        "discovery_gate_35pct_ok": max_share <= MAX_PRIMARY_SHARE,
        "finished_at": utc_now_iso(),
    }
    STATS_PATH.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    return CSV_PATH, PROV_PATH


def main() -> None:
    csv_path, prov_path = export()
    print(f"[export] {csv_path}")
    print(f"[export] {prov_path}")
    print(f"[export] stats={STATS_PATH}")


if __name__ == "__main__":
    main()
