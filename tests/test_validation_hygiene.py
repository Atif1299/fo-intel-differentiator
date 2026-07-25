"""Validation / hygiene unit tests."""

from __future__ import annotations

from pipeline.validate_lib.checks import entity_quality_reject, inclusion_checks


def test_rejects_report_title() -> None:
    row = {
        "fo_id": "x",
        "common_name": "Multi-Family Office Asset Pools Report",
        "inclusion_pass": True,
        "fo_type": "multi_family_office",
        "inclusion_evidence_summary": "mentions multi-family office pools in a research report",
        "proof_urls": ["https://www.withintelligence.com/insights/x"],
        "website": "https://www.withintelligence.com/insights/x",
    }
    assert entity_quality_reject(row) in {
        "entity_name_crumb",
        "entity_name_report",
        "entity_website_non_firm",
    }


def test_rejects_category_only_name() -> None:
    row = {
        "fo_id": "y",
        "common_name": "Single Family Office",
        "inclusion_pass": True,
        "fo_type": "single_family_office",
        "inclusion_evidence_summary": "Described as a single family office on a careers page with enough text here.",
        "proof_urls": ["https://example.com"],
        "website": "https://oplu.com",
    }
    assert entity_quality_reject(row) == "entity_category_only"


def test_inclusion_requires_evidence() -> None:
    row = {
        "fo_id": "z",
        "common_name": "Acme Family Office",
        "inclusion_pass": True,
        "fo_type": "single_family_office",
        "inclusion_evidence_summary": "",
        "proof_urls": ["https://acme.example"],
        "website": "https://acme.example",
    }
    assert inclusion_checks(row) == "missing_inclusion_evidence"
