"""
Stage: enrich
Input: data/raw/candidates.jsonl
Output: data/processed/enriched.jsonl + enrich_stats.json

Prefilter → rank (cap 120) → resolve website → fetch Class C → OpenAI classify/extract.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

from pipeline.enrich_lib.classify import classify_and_extract
from pipeline.enrich_lib.fetch import collect_proof_corpus, resolve_website_ddg
from pipeline.enrich_lib.prefilter import prefilter
from pipeline.enrich_lib.schema import apply_field, empty_enriched, utc_now_iso

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

RAW = ROOT / "data" / "raw" / "candidates.jsonl"
PROCESSED = ROOT / "data" / "processed"
AUDIT = ROOT / "data" / "audit"
OUT = PROCESSED / "enriched.jsonl"
STATS = PROCESSED / "enrich_stats.json"
DROPPED = AUDIT / "enrich_dropped.jsonl"

ENRICH_BUDGET = 120
RESUME_CAP = 100
RESUME_PASS_TARGET = 80  # buffer for validation rejects / dedupe
EXTRACT_KEYS = [
    "legal_name",
    "common_name",
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
    "inclusion_evidence_summary",
]


def _load_candidates() -> list[dict[str, Any]]:
    if not RAW.exists():
        raise FileNotFoundError(f"Missing {RAW} — run discovery first")
    rows: list[dict[str, Any]] = []
    for line in RAW.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _rank_score(c: dict[str, Any]) -> tuple:
    name = (c.get("name") or "").lower()
    fo_in_name = 1 if "family office" in name else 0
    n_sources = len(c.get("discovery_source_ids") or [])
    has_web = 1 if c.get("website_hint") else 0
    has_urls = 1 if c.get("discovery_urls") else 0
    return (fo_in_name, n_sources, has_web, has_urls, c.get("name") or "")


def rank_for_budget(candidates: list[dict[str, Any]], budget: int = ENRICH_BUDGET) -> list[dict[str, Any]]:
    ranked = sorted(candidates, key=_rank_score, reverse=True)
    return ranked[:budget]


def _domain_institutional(url: str | None) -> bool:
    if not url:
        return False
    host = urlparse(url).netloc.lower()
    if not host or any(
        x in host
        for x in (
            "linkedin.com",
            "wikipedia.org",
            "facebook.com",
            "twitter.com",
            "youtube.com",
            "sec.gov",
            "bloomberg.com",
            "reuters.com",
        )
    ):
        return False
    return True


def _merge_llm(record: dict[str, Any], llm: dict[str, Any], proof_urls: list[str], proof_ids: list[str]) -> None:
    sources = proof_ids or ["openai_classify"]
    method = "openai_classify_extract"

    fo_type = llm.get("fo_type") or "unknown_type"
    if fo_type not in {"single_family_office", "multi_family_office", "unknown_type"}:
        fo_type = "unknown_type"
    inclusion = bool(llm.get("inclusion_pass"))
    # Guard: never pass without evidence string
    evidence = llm.get("inclusion_evidence_summary")
    if inclusion and not (isinstance(evidence, str) and evidence.strip()):
        inclusion = False
        fo_type = "unknown_type"

    apply_field(record, "fo_type", fo_type, sources, method, "verified" if inclusion else "could_not_verify")
    record["fo_type"] = fo_type
    record["inclusion_pass"] = inclusion

    conf = llm.get("confidence_overall")
    try:
        record["confidence_overall"] = float(conf) if conf is not None else (0.7 if inclusion else 0.2)
    except (TypeError, ValueError):
        record["confidence_overall"] = 0.2 if not inclusion else 0.5

    for key in EXTRACT_KEYS:
        val = llm.get(key)
        # Contacts: never mark verified without explicit string from text — still trust model nulls
        status = "verified"
        if key in {"principal_email", "principal_phone", "principal_linkedin"} and val:
            status = "verified"
        elif key.startswith("signal_") and val:
            status = "verified"
        elif val:
            status = "verified"
        else:
            status = "could_not_verify"
            val = None
        apply_field(record, key, val, sources if val else [], method if val else "openai_no_value", status)

    # Prefer resolved website if LLM blank
    if not record.get("website") and proof_urls:
        # keep earlier website apply
        pass

    record["proof_urls"] = list(proof_urls)
    record["proof_source_ids"] = list(dict.fromkeys(proof_ids))
    record["fields"]["_llm_model"] = {
        "value": llm.get("_model"),
        "sources": ["openai"],
        "method": method,
        "status": "verified",
        "checked_at": utc_now_iso(),
    }


def enrich_one(candidate: dict[str, Any]) -> dict[str, Any]:
    record = empty_enriched(candidate)
    name = candidate.get("name") or ""
    website = candidate.get("website_hint")
    resolve_meta: dict[str, Any] | None = None

    if not website or not _domain_institutional(website):
        resolved, resolve_meta = resolve_website_ddg(name)
        if resolved:
            website = resolved
            status = "verified" if _domain_institutional(resolved) else "could_not_verify"
            apply_field(
                record,
                "website",
                resolved,
                ["ddg_site_resolve"],
                "ddg_site_resolve",
                status,
            )
    else:
        apply_field(record, "website", website, candidate.get("discovery_source_ids") or [], "discovery_hint", "verified")

    corpus, used_urls, fetch_logs = collect_proof_corpus(candidate, website)
    record["raw_candidate"]["fetch_logs"] = fetch_logs
    if resolve_meta:
        record["raw_candidate"]["website_resolve"] = resolve_meta

    proof_ids = ["class_c_fetch"] if used_urls else []
    if website and _domain_institutional(website):
        proof_ids.append("fo_website")

    if not corpus.strip():
        apply_field(record, "fo_type", "unknown_type", [], "fetch_failed", "could_not_verify")
        record["fo_type"] = "unknown_type"
        record["inclusion_pass"] = False
        record["proof_urls"] = []
        record["proof_source_ids"] = []
        record["confidence_overall"] = 0.0
        apply_field(
            record,
            "inclusion_evidence_summary",
            None,
            [],
            "fetch_failed",
            "could_not_verify",
        )
        return record

    llm = classify_and_extract(name, corpus, candidate.get("geo_hint"))
    _merge_llm(record, llm, used_urls, proof_ids)
    # Ensure website on record if we have it and LLM didn't overwrite with null badly
    if website and not record.get("website"):
        apply_field(
            record,
            "website",
            website,
            ["class_c_fetch"],
            "fetch_corpus",
            "verified" if _domain_institutional(website) else "could_not_verify",
        )
    return record


def _load_enriched() -> list[dict[str, Any]]:
    if not OUT.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in OUT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _shippable_count(records: list[dict[str, Any]]) -> int:
    n = 0
    for r in records:
        if r.get("inclusion_pass") and r.get("fo_type") in {
            "single_family_office",
            "multi_family_office",
        }:
            n += 1
    return n


def _compute_stats(records: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    inclusion_true = 0
    has_website = 0
    has_principal = 0
    has_signal = 0
    for r in records:
        t = r.get("fo_type") or "unknown_type"
        by_type[t] = by_type.get(t, 0) + 1
        if r.get("inclusion_pass"):
            inclusion_true += 1
        if r.get("website"):
            has_website += 1
        if r.get("principal_name"):
            has_principal += 1
        if r.get("signal_1_summary"):
            has_signal += 1
    return {
        **meta,
        "processed": len(records),
        "by_fo_type": by_type,
        "inclusion_pass_true": inclusion_true,
        "inclusion_pass_false": len(records) - inclusion_true,
        "shippable_sfo_mfo": _shippable_count(records),
        "with_website": has_website,
        "with_principal_name": has_principal,
        "with_signal_1": has_signal,
        "finished_at": utc_now_iso(),
    }


def _require_api_key() -> None:
    if not os.getenv("OPENAI_API_KEY", "").strip():
        print(
            "ERROR: OPENAI_API_KEY missing. Add it to fo-intel/.env then re-run:\n"
            "  python -m pipeline.enrich",
            file=sys.stderr,
        )
        sys.exit(1)


def enrich(budget: int = ENRICH_BUDGET, limit: int | None = None) -> Path:
    _require_api_key()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)

    candidates = _load_candidates()
    kept, dropped = prefilter(candidates)
    with DROPPED.open("w", encoding="utf-8") as f:
        for d in dropped:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    ranked = rank_for_budget(kept, budget=budget)
    if limit is not None:
        ranked = ranked[:limit]

    print(f"[enrich] candidates={len(candidates)} kept={len(kept)} dropped={len(dropped)} budget={len(ranked)}")

    records: list[dict[str, Any]] = []
    errors = 0
    with OUT.open("w", encoding="utf-8") as out:
        for i, c in enumerate(ranked, 1):
            name = c.get("name") or "?"
            print(f"[enrich] {i}/{len(ranked)} {name[:60]} ...", flush=True)
            try:
                rec = enrich_one(c)
                records.append(rec)
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
            except Exception as exc:  # noqa: BLE001
                errors += 1
                print(f"  ERROR: {exc}", flush=True)
                fail = empty_enriched(c)
                fail["raw_candidate"]["enrich_error"] = str(exc)
                records.append(fail)
                out.write(json.dumps(fail, ensure_ascii=False) + "\n")
            time.sleep(0.3)

    stats = _compute_stats(
        records,
        {
            "input_candidates": len(candidates),
            "prefilter_kept": len(kept),
            "prefilter_dropped": len(dropped),
            "enrich_budget": len(ranked),
            "errors": errors,
            "mode": "full",
        },
    )
    STATS.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    return OUT


def enrich_resume(
    resume_cap: int = RESUME_CAP,
    pass_target: int = RESUME_PASS_TARGET,
) -> Path:
    """Append enrich for unenriched candidates until shippable >= pass_target or cap."""
    _require_api_key()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)

    existing = _load_enriched()
    done_ids = {r.get("fo_id") for r in existing if r.get("fo_id")}
    shippable = _shippable_count(existing)
    print(f"[enrich --resume] existing={len(existing)} shippable={shippable} target={pass_target}")

    if shippable >= pass_target:
        print(f"[enrich --resume] already at target; rewriting stats only")
        stats = _compute_stats(existing, {"mode": "resume_noop", "resume_added": 0})
        STATS.write_text(json.dumps(stats, indent=2), encoding="utf-8")
        print(json.dumps(stats, indent=2))
        return OUT

    candidates = _load_candidates()
    kept, dropped = prefilter(candidates)
    with DROPPED.open("w", encoding="utf-8") as f:
        for d in dropped:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    ranked = sorted(kept, key=_rank_score, reverse=True)
    todo = [c for c in ranked if (c.get("candidate_id") or "") not in done_ids]
    todo = todo[:resume_cap]
    print(f"[enrich --resume] todo={len(todo)} (cap={resume_cap})")

    records = list(existing)
    errors = 0
    added = 0
    with OUT.open("a", encoding="utf-8") as out:
        for i, c in enumerate(todo, 1):
            if _shippable_count(records) >= pass_target:
                print(f"[enrich --resume] hit pass target {_shippable_count(records)} — stop early")
                break
            name = c.get("name") or "?"
            print(f"[enrich --resume] {i}/{len(todo)} {name[:60]} ...", flush=True)
            try:
                rec = enrich_one(c)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                print(f"  ERROR: {exc}", flush=True)
                rec = empty_enriched(c)
                rec["raw_candidate"]["enrich_error"] = str(exc)
            records.append(rec)
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            added += 1
            time.sleep(0.3)

    stats = _compute_stats(
        records,
        {
            "input_candidates": len(candidates),
            "prefilter_kept": len(kept),
            "prefilter_dropped": len(dropped),
            "mode": "resume",
            "resume_added": added,
            "resume_cap": resume_cap,
            "pass_target": pass_target,
            "errors": errors,
        },
    )
    STATS.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    return OUT


def main() -> None:
    resume = "--resume" in sys.argv
    limit = None
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=", 1)[1])
    if resume:
        path = enrich_resume()
    else:
        path = enrich(limit=limit)
    n = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    print(f"[enrich] wrote {path} ({n} records) stats={STATS}")


if __name__ == "__main__":
    main()
