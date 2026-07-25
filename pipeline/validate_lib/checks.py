"""Validation helpers: Rule 1/2 checks, contact blanking, dedupe keys, entity hygiene."""

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

# Cannot be the firm's primary website (publisher / directory / hub)
_NON_FIRM_WEBSITE_HOSTS = _NON_IDENTITY_DOMAINS | {
    "withintelligence.com",
    "familyofficehub.io",
    "marketsgroup.org",
    "pulse2.com",
    "grokipedia.com",
}

_FO_ID_DENYLIST = {
    "multi-family-office-asset-pools-report-c199b6f932",
    "miami-single-family-office-92ff8e78b8",
    # Sample-audit rejects: network / platform / wrong-entity / weak FO-services brand
    "global-family-office-db539972ce",  # tfoa.info SFO peer network — not an FO entity
    "your-elite-single-family-office-powered-by-qp-gl-8e06db07b1",  # manages SFOs for multiple families
    "office-in-london-your-expert-in-global-wealth-ba21e9f7fd",  # wealth-services marketing, weak Rule 2
    "london-based-single-family-office-managing-wealt-baa7674609",  # dakota.com allocator intel ≠ FO
}

# Domains that must never ship as the FO's institutional identity
_HARD_NON_FO_DOMAINS = {
    "tfoa.info",
    "dakota.com",
    "qp-global.com",
}

_BRAND_STOP = {
    "family",
    "office",
    "offices",
    "capital",
    "management",
    "company",
    "group",
    "wealth",
    "advisors",
    "advisor",
    "financial",
    "investments",
    "investment",
    "partners",
    "global",
    "the",
    "and",
    "for",
    "llc",
    "llp",
    "ltd",
    "inc",
    "single",
    "multi",
    "private",
    "trust",
}

_CRUMB_NAME = re.compile(
    r"\b("
    r"report|jobs?\s+in|hire\s+remote|consultants?\s+for|choose\s+the|"
    r"protecting\s+family|why\s+family|what\s+expert|connect\s+with|"
    r"asset\s+pools|notable\s+investments"
    r")\b",
    re.I,
)

_GEO_GENERIC = re.compile(
    r"^(?:the\s+)?("
    r"miami|dallas|boston|chicago|atlanta|denver|seattle|new\s+york|"
    r"los\s+angeles|san\s+francisco|houston|austin|phoenix|philly|"
    r"philadelphia|london|singapore|swiss|switzerland|us|u\.s\."
    r")\s+(?:single[-\s]?family\s+)?family\s+offices?$",
    re.I,
)

_CATEGORY_ONLY = re.compile(
    r"^(?:the\s+)?(?:largest|top|best|leading|biggest|confidential|shared)?\s*"
    r"(?:single[-\s]?family|multi[-\s]?family|family)\s+offices?\s*$",
    re.I,
)

_KNOWN_FIRM_DOMAINS_FOR_GEO = {
    "sowellco.com",
    "oldmountain.net",
    "themiamifamilyoffice.com",
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
        return host or None
    except Exception:
        return None


def _raw_host(url: str | None) -> str | None:
    if not url or not isinstance(url, str):
        return None
    try:
        host = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host or None
    except Exception:
        return None


def dedupe_keys(record: dict[str, Any]) -> tuple[str, str | None]:
    name = record.get("legal_name") or record.get("common_name") or ""
    return normalize_name(str(name)), website_domain(record.get("website"))


def brand_key(record: dict[str, Any]) -> str | None:
    """
    Distinctive brand token for near-duplicate collapse (Cresset / Farther).
    Returns None when no stable brand token exists.
    """
    name = f"{record.get('legal_name') or ''} {record.get('common_name') or ''}".strip()
    toks = [
        t
        for t in re.findall(r"[a-z0-9]+", name.lower())
        if len(t) >= 4 and t not in _BRAND_STOP
    ]
    if not toks:
        return None
    return toks[0]


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


def maybe_improve_geo_name(record: dict[str, Any]) -> None:
    """If geo-generic crumb but firmer legal_name exists, prefer it as common_name."""
    name = (record.get("common_name") or record.get("legal_name") or "").strip()
    if not _GEO_GENERIC.match(name):
        return
    legal = (record.get("legal_name") or "").strip()
    if legal and legal.lower() != name.lower() and not _GEO_GENERIC.match(legal):
        record["common_name"] = legal
        record.setdefault("validation_audit", {})["renamed_from_geo_crumb"] = name


def _prefer_firm_website(record: dict[str, Any]) -> None:
    """If primary website is a publisher/hub, promote an institutional proof URL when present."""
    host = _raw_host(record.get("website"))
    if host and host not in _NON_FIRM_WEBSITE_HOSTS:
        return
    candidates = list(record.get("proof_urls") or []) + list(record.get("discovery_urls") or [])
    for url in candidates:
        h = _raw_host(url)
        if h and h not in _NON_FIRM_WEBSITE_HOSTS:
            old = record.get("website")
            record["website"] = url if "://" in str(url) else f"https://{url}"
            record.setdefault("validation_audit", {})["website_promoted_from"] = old
            return
    # Directory-only profiles: one DDG resolve for an official-looking site
    if host in {"altss.com", "familyofficehub.io", "swfinstitute.org"}:
        name = (record.get("common_name") or record.get("legal_name") or "").strip()
        if not name:
            return
        try:
            from pipeline.enrich_lib.fetch import resolve_website_ddg

            resolved, meta = resolve_website_ddg(name)
            rh = _raw_host(resolved)
            if resolved and rh and rh not in _NON_FIRM_WEBSITE_HOSTS and rh not in {
                "altss.com",
                "familyofficehub.io",
                "withintelligence.com",
            }:
                record.setdefault("validation_audit", {})["website_ddg_resolve"] = meta
                record["website"] = resolved
        except Exception as exc:  # noqa: BLE001
            record.setdefault("validation_audit", {})["website_ddg_resolve_error"] = str(exc)


def entity_quality_reject(record: dict[str, Any]) -> str | None:
    """Hard/soft entity hygiene — refuse non-firms that slipped past enrich."""
    fo_id = str(record.get("fo_id") or "")
    if fo_id in _FO_ID_DENYLIST:
        return "entity_denylist"

    name = (record.get("common_name") or record.get("legal_name") or "").strip()
    if not name:
        return "missing_name"
    if _CRUMB_NAME.search(name):
        return "entity_name_crumb"
    if re.search(r"\breport\b", name, re.I):
        return "entity_name_report"
    if _CATEGORY_ONLY.match(name):
        return "entity_category_only"

    evidence = (record.get("inclusion_evidence_summary") or "").strip()
    ev_l = evidence.lower()
    # Networks / associations / peer clubs are not FO entities (Rule 2)
    if re.search(
        r"peer\s+network|membership\s+network|association\s+of\s+(?:single[-\s]?)?family|"
        r"community\s+of\s+single\s+family|sfo\s+community",
        ev_l,
    ):
        return "entity_network_not_fo"
    # SFO label while evidence describes multi-family / outsourced platform → coerce to MFO
    if record.get("fo_type") == "single_family_office" and re.search(
        r"managing\s+(?:the\s+)?single\s+family\s+offices\s+for|"
        r"outsourced\s+family\s+office|"
        r"serving\s+a\s+limited\s+number\s+of\s+families|"
        r"handful\s+of\s+(?:distinguished\s+)?families|"
        r"multiple\s+families",
        ev_l,
    ):
        record["fo_type"] = "multi_family_office"
        record.setdefault("validation_audit", {})["coerced_sfo_to_mfo"] = True
        fields = record.setdefault("fields", {})
        if "fo_type" in fields and isinstance(fields["fo_type"], dict):
            fields["fo_type"]["value"] = "multi_family_office"
            fields["fo_type"]["method"] = "validation_coerce_sfo_to_mfo"

    _prefer_firm_website(record)
    host = _raw_host(record.get("website"))

    _HARD_BAD = {"withintelligence.com", "familyofficehub.io"} | _HARD_NON_FO_DOMAINS
    if host and host in _HARD_BAD:
        return "entity_website_non_firm"

    if host and host in _NON_FIRM_WEBSITE_HOSTS | {"altss.com", "preqin.com"}:
        # Real firms often only have press URLs from discovery — blank customer website,
        # keep proof_urls; do not ship directory/report publishers as the firm home.
        evidence = (record.get("inclusion_evidence_summary") or "").strip()
        if len(evidence) < 60:
            return "entity_website_non_firm"
        record.setdefault("validation_audit", {})["blanked_news_website"] = record.get("website")
        record["website"] = None
        fields = record.setdefault("fields", {})
        from pipeline.enrich_lib.schema import provenance

        fields["website"] = provenance(None, [], "validation_blank_news_host", "could_not_verify")

    if _GEO_GENERIC.match(name):
        host2 = _raw_host(record.get("website"))
        if not host2 or host2 in _NON_FIRM_WEBSITE_HOSTS:
            return "entity_geo_generic_weak_site"
        # Geo SERP crumbs are low-trust even with a site — require known firm domain
        if host2 not in _KNOWN_FIRM_DOMAINS_FOR_GEO:
            return "entity_geo_generic_unverified_domain"

    return None


def inclusion_checks(record: dict[str, Any]) -> str | None:
    """Return rejection_reason or None if inclusion OK."""
    if not record.get("inclusion_pass"):
        return "inclusion_pass_false"
    if record.get("fo_type") not in SHIP_TYPES:
        return "fo_type_not_shippable"
    evidence = record.get("inclusion_evidence_summary")
    if not (isinstance(evidence, str) and evidence.strip()):
        fe = (record.get("fields") or {}).get("inclusion_evidence_summary") or {}
        if not (isinstance(fe.get("value"), str) and fe["value"].strip()):
            return "missing_inclusion_evidence"
    proof_urls = record.get("proof_urls") or []
    proof_ids = record.get("proof_source_ids") or []
    if not proof_urls and not proof_ids:
        return "missing_proof_urls_or_ids"
    hygiene = entity_quality_reject(record)
    if hygiene:
        return hygiene
    return None
