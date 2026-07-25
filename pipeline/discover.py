"""
Stage: discover
Input: none
Output: data/raw/candidates.jsonl + data/raw/discovery_stats.json

Multi-source Class A/B discovery. Soft gate: if any single source_id >50% of
candidates, run an extra DDG batch to rebalance.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from pipeline.models import Candidate
from pipeline.sources import ddg_queries, edgar_search, news_rss, swfi_parse, wiki_fo_list

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = RAW / "candidates.jsonl"
STATS = RAW / "discovery_stats.json"


def _merge(candidates: list[Candidate]) -> list[Candidate]:
    by_norm: dict[str, Candidate] = {}
    for c in candidates:
        key = c.name_normalized
        if not key:
            continue
        if key in by_norm:
            by_norm[key].merge_from(c)
        else:
            by_norm[key] = c.model_copy(deep=True)
    return list(by_norm.values())


def _stats(candidates: list[Candidate]) -> dict:
    primary = Counter()
    all_ids = Counter()
    classes = Counter()
    for c in candidates:
        classes[c.discovery_source_class] += 1
        if c.discovery_source_ids:
            primary[c.discovery_source_ids[0]] += 1
        for sid in c.discovery_source_ids:
            all_ids[sid] += 1
    n = max(len(candidates), 1)
    primary_share = {k: round(v / n, 4) for k, v in primary.items()}
    max_primary = max(primary_share.values()) if primary_share else 0.0
    return {
        "total_unique": len(candidates),
        "by_class": dict(classes),
        "by_primary_source_id": dict(primary),
        "primary_source_share": primary_share,
        "by_all_source_ids": dict(all_ids),
        "distinct_source_ids": len(all_ids),
        "max_primary_share": max_primary,
        "soft_gate_50pct_ok": max_primary <= 0.50,
    }


def discover() -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    buckets: list[Candidate] = []

    print("[discover] Class A - DuckDuckGo ...")
    buckets.extend(ddg_queries.run())
    print(f"  ddg cumulative raw={len(buckets)}")

    print("[discover] Class A - EDGAR ...")
    buckets.extend(edgar_search.run())
    print(f"  after edgar raw={len(buckets)}")

    print("[discover] Class A - News RSS ...")
    buckets.extend(news_rss.run())
    print(f"  after rss raw={len(buckets)}")

    print("[discover] Class B - Wikipedia ...")
    buckets.extend(wiki_fo_list.run())
    print(f"  after wiki raw={len(buckets)}")

    print("[discover] Class B - SWFI/public pages ...")
    buckets.extend(swfi_parse.run())
    print(f"  after swfi raw={len(buckets)}")

    merged = _merge(buckets)
    stats = _stats(merged)

    if not stats["soft_gate_50pct_ok"]:
        print("[discover] soft gate: one source >50% - running extra DDG batch ...")
        buckets.extend(ddg_queries.run_extra_batch())
        merged = _merge(buckets)
        stats = _stats(merged)

    with OUT.open("w", encoding="utf-8") as f:
        for c in sorted(merged, key=lambda x: x.name_normalized):
            f.write(c.model_dump_json() + "\n")

    STATS.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    return OUT


def main() -> None:
    path = discover()
    n = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    print(f"[discover] wrote {path} ({n} candidates)")
    print(f"[discover] stats -> {STATS}")


if __name__ == "__main__":
    main()
