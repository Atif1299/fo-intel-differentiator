"""Validation helpers: Rule 1/2 checks, contact blanking, dedupe keys."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from pipeline.normalize import normalize_name

SHIP_TYPES = {"single_family_office", "multi_family_office"}

# Domains that host many unrelated FO mentions — never use for identity dedupe
_NON_IDENTITY_DOMAINS = {
    "altss.com",
    "familywealthreport.com",
    "linkedin.com",
    "wikipedia.org",
    "sec.gov",
    "bloomberg.com",
    "reuters.com",
    "youtube.com",
    "twitter.com",
    "facebook.com",
    "crunchbase.com",
    "pitchbook.com",
    "swfinstitute.org",
    "google.com",
    "news.google.com",
    "duckduckgo.com",
    "medium.com",
    "substack.com",
    "forbes.com",
    "ft.com",
    "wsj.com",
    "businesswire.com",
    "prnewswire.com",
    "globenewswire.com",
    "praxisrock.com",
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"[\d+][\d\s().-]{6,}\d")


def website_domain(url: str | None) -> str | None:
    if not url or not isinstance(url, str):
        return None
    try:
        host = urlparse(url.strip()).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        if not host or host in _NON_IDENTITY_DOMAINS:
            return None
        # strip country news subhosts lightly
        return host or None
    except Exception:
        return None


def dedupe_keys(record: dict[str, Any]) -> tuple[str, str | None]:
    name = record.get("legal_name") or record.get("common_name") or ""
    return normalize_name(str(name)), website_domain(record.get("website"))


def contact_needs_blank(field_key: str, record: dict[str, Any]) -> bool:
    """True if verified contact should be blanked (no usable source / bad shape)."""
    fields = record.get("fields") or {}
    prov = fields.get(field_key) or {}
    value = prov.get("value") if prov.get("value") is not None else record.get(field_key)
    if not value:
        return False
    status = prov.get("status") or ""
    sources = prov.get("sources") or []
    if status != "verified":
        return False
    # Must have at least one URL-like or class_c proof source
    has_url_source = any(
        isinstance(s, str) and (s.startswith("http") or s in {"class_c_fetch", "fo_website"})
        for s in sources
    )
    if not has_url_source and not (record.get("proof_urls") or []):
        return True
    if field_key == "principal_email" and not _EMAIL_RE.match(str(value).strip()):
        return True
    if field_key == "principal_phone" and not _PHONE_RE.search(str(value)):
        return True
    return False


def blank_contact(record: dict[str, Any], field_key: str, audit: dict[str, Any]) -> None:
    from pipeline.enrich_lib.schema import utc_now_iso

    fields = record.setdefault("fields", {})
    old = fields.get(field_key) or {}
    audit.setdefault("blanked_contacts", []).append(
        {"field": field_key, "old_value": old.get("value") or record.get(field_key), "old_prov": old}
    )
    record[field_key] = None
    fields[field_key] = {
        "value": None,
        "sources": [],
        "method": "validation_blank",
        "status": "could_not_verify",
        "checked_at": utc_now_iso(),
    }


def inclusion_checks(record: dict[str, Any]) -> str | None:
    """Return rejection_reason or None if inclusion OK."""
    if not record.get("inclusion_pass"):
        return "inclusion_pass_false"
    if record.get("fo_type") not in SHIP_TYPES:
        return "fo_type_not_shippable"
    evidence = record.get("inclusion_evidence_summary")
    if not (isinstance(evidence, str) and evidence.strip()):
        # also check fields map
        fe = (record.get("fields") or {}).get("inclusion_evidence_summary") or {}
        if not (isinstance(fe.get("value"), str) and fe["value"].strip()):
            return "missing_inclusion_evidence"
    proof_urls = record.get("proof_urls") or []
    proof_ids = record.get("proof_source_ids") or []
    if not proof_urls and not proof_ids:
        return "missing_proof_urls_or_ids"
    return None
