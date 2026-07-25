"""OpenAI classification + field extraction for FO enrich."""

from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

SYSTEM = """You are verifying whether an entity is a real Family Office for a data product.
Rules (strict):
- inclusion_pass=true ONLY with affirmative evidence the entity IS a family office (self-description, filing language, clear FO entity — not merely RIA/bank "family office services", not name alone).
- fo_type must be single_family_office, multi_family_office, or unknown_type.
- Never invent emails, phones, LinkedIn, AUM, or principals. If not clearly in the text, use null.
- Prefer unknown_type + inclusion_pass=false over guessing.
- Return JSON only matching the schema."""


def classify_and_extract(
    name: str,
    corpus: str,
    geo_hint: str | None,
    model: str = "gpt-4o-mini",
) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing — set it in fo-intel/.env")

    client = OpenAI(api_key=api_key)
    user = {
        "candidate_name": name,
        "geo_hint": geo_hint,
        "page_text": corpus[:18000] if corpus else "",
        "schema": {
            "fo_type": "single_family_office|multi_family_office|unknown_type",
            "inclusion_pass": "bool",
            "inclusion_evidence_summary": "string|null — quote/paraphrase basis",
            "confidence_overall": "0-1 float",
            "legal_name": "string|null",
            "common_name": "string|null",
            "hq_city": "string|null",
            "hq_country": "string|null",
            "website": "string|null",
            "linkedin_company_url": "string|null",
            "aum_note": "string|null",
            "investment_thesis": "string|null",
            "investment_mandates": "string|null",
            "principal_name": "string|null",
            "principal_title": "string|null",
            "principal_linkedin": "string|null",
            "principal_email": "string|null",
            "principal_phone": "string|null",
            "signal_1_summary": "string|null",
            "signal_1_date": "YYYY-MM-DD|null",
            "signal_1_url": "string|null",
        },
    }
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(user)},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    data = json.loads(content)
    data["_model"] = model
    data["_usage"] = {
        "prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
        "completion_tokens": getattr(resp.usage, "completion_tokens", None),
    }
    return data
