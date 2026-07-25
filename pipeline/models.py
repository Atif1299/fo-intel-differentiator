"""Shared candidate model for discovery stage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Candidate(BaseModel):
    candidate_id: str
    name: str
    name_normalized: str
    website_hint: str | None = None
    geo_hint: str | None = None
    snippet: str | None = None
    discovery_source_class: str  # A or B at discovery (primary at first find)
    discovery_source_ids: list[str] = Field(default_factory=list)
    discovery_urls: list[str] = Field(default_factory=list)
    discovered_at: str = Field(default_factory=utc_now_iso)
    raw: dict[str, Any] = Field(default_factory=dict)

    def merge_from(self, other: Candidate) -> None:
        """Merge another sighting of the same firm into this candidate."""
        for sid in other.discovery_source_ids:
            if sid not in self.discovery_source_ids:
                self.discovery_source_ids.append(sid)
        for url in other.discovery_urls:
            if url and url not in self.discovery_urls:
                self.discovery_urls.append(url)
        if other.website_hint and not self.website_hint:
            self.website_hint = other.website_hint
        if other.geo_hint and not self.geo_hint:
            self.geo_hint = other.geo_hint
        if other.snippet and (not self.snippet or len(other.snippet) > len(self.snippet or "")):
            self.snippet = other.snippet
        if other.discovered_at < self.discovered_at:
            self.discovered_at = other.discovered_at
        # Prefer Class A label if either sighting is A (discovery mix signal)
        if other.discovery_source_class == "A" or self.discovery_source_class == "A":
            self.discovery_source_class = "A"
        self.raw.setdefault("merged_from", [])
        self.raw["merged_from"].append(other.discovery_source_ids)


class EnrichedRecord(BaseModel):
    """Lightweight typed view of an enrich JSONL row (runtime uses dicts + schema helpers)."""

    fo_id: str
    legal_name: str | None = None
    common_name: str | None = None
    fo_type: str = "unknown_type"
    inclusion_pass: bool = False
    confidence_overall: float = 0.0
    website: str | None = None
    discovery_source_ids: list[str] = Field(default_factory=list)
    discovery_urls: list[str] = Field(default_factory=list)
    proof_source_ids: list[str] = Field(default_factory=list)
    proof_urls: list[str] = Field(default_factory=list)
    fields: dict[str, Any] = Field(default_factory=dict)
