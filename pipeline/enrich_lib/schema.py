"""Provenance helpers and empty enriched record factory."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


HIGH_VALUE_FIELDS = [
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
    "inclusion_evidence_summary",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def provenance(
    value: Any,
    sources: list[str],
    method: str,
    status: str,
) -> dict[str, Any]:
    return {
        "value": value,
        "sources": [s for s in sources if s],
        "method": method,
        "status": status,
        "checked_at": utc_now_iso(),
    }


def blank_prov(method: str = "not_attempted") -> dict[str, Any]:
    return provenance(None, [], method, "could_not_verify")


def empty_enriched(candidate: dict[str, Any]) -> dict[str, Any]:
    fo_id = candidate.get("candidate_id") or "unknown"
    fields = {k: blank_prov() for k in HIGH_VALUE_FIELDS}
    return {
        "fo_id": fo_id,
        "legal_name": candidate.get("name"),
        "common_name": candidate.get("name"),
        "fo_type": "unknown_type",
        "hq_city": candidate.get("geo_hint"),
        "hq_country": None,
        "website": candidate.get("website_hint"),
        "linkedin_company_url": None,
        "aum_note": None,
        "investment_thesis": None,
        "investment_mandates": None,
        "principal_name": None,
        "principal_title": None,
        "principal_linkedin": None,
        "principal_email": None,
        "principal_phone": None,
        "signal_1_summary": None,
        "signal_1_date": None,
        "signal_1_url": None,
        "signal_2_summary": None,
        "signal_2_date": None,
        "signal_2_url": None,
        "inclusion_evidence_summary": None,
        "confidence_overall": 0.0,
        "inclusion_pass": False,
        "discovery_source_class": candidate.get("discovery_source_class"),
        "discovery_source_ids": list(candidate.get("discovery_source_ids") or []),
        "discovery_urls": list(candidate.get("discovery_urls") or []),
        "proof_source_ids": [],
        "proof_urls": [],
        "fields": fields,
        "raw_candidate": {
            "snippet": candidate.get("snippet"),
            "discovered_at": candidate.get("discovered_at"),
        },
    }


def apply_field(
    record: dict[str, Any],
    key: str,
    value: Any,
    sources: list[str],
    method: str,
    status: str,
) -> None:
    if value is None or (isinstance(value, str) and not value.strip()):
        record["fields"][key] = provenance(None, sources, method, "could_not_verify")
        if key in record:
            record[key] = None
        return
    record["fields"][key] = provenance(value, sources, method, status)
    if key in record:
        record[key] = value
