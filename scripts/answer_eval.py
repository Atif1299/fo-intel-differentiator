"""
Answer-layer eval against a running FO Intel API.

Usage:
  python scripts/answer_eval.py
  python scripts/answer_eval.py --base-url https://YOUR-API.run.app
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import httpx

CASES: list[dict[str, Any]] = [
    {
        "id": "known_mfo",
        "query": "What type of family office is Matter Family Office?",
        "expect_status": "ok",
        "must_mention_any": ["Matter", "multi"],
    },
    {
        "id": "known_sfo",
        "query": "Is ckandcompany a single-family office?",
        "expect_status": "ok",
        "must_mention_any": ["ckandcompany", "single", "family"],
    },
    {
        "id": "swfi_sfo",
        "query": "What does Westerman Capital do?",
        "expect_status": "ok",
        "must_mention_any": ["Westerman"],
    },
    {
        "id": "sfo_filter",
        "query": "List single-family offices with investment or venture signals",
        "expect_status": "ok",
        "must_mention_any": ["family"],
    },
    {
        "id": "nonsense_decline",
        "query": "What is the phone number of the Emperor of Mars Family Office XYZQwerty999?",
        "expect_status": "insufficient_evidence",
        "must_mention_any": [],
    },
    {
        "id": "emptyish_decline",
        "query": "asdf qwerty zxcvbn unrelated gibberish 12345",
        "expect_status": "insufficient_evidence",
        "must_mention_any": [],
    },
]


def run_case(client: httpx.Client, base: str, case: dict[str, Any]) -> dict[str, Any]:
    r = client.post(f"{base.rstrip('/')}/ask", json={"query": case["query"]}, timeout=120.0)
    r.raise_for_status()
    body = r.json()
    status = body.get("status")
    text = " ".join(
        [
            str(body.get("answer") or ""),
            str(body.get("message") or ""),
            json.dumps(body.get("records") or []),
        ]
    )
    ok_status = status == case["expect_status"]
    needles = case.get("must_mention_any") or []
    ok_text = True
    if needles and case["expect_status"] == "ok":
        low = text.lower()
        ok_text = any(n.lower() in low for n in needles)
    passed = ok_status and ok_text
    return {
        "id": case["id"],
        "passed": passed,
        "expect_status": case["expect_status"],
        "got_status": status,
        "ok_status": ok_status,
        "ok_text": ok_text,
        "answer_preview": (body.get("answer") or body.get("message") or "")[:200],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    health = httpx.get(f"{args.base_url.rstrip('/')}/health", timeout=30.0)
    health.raise_for_status()
    h = health.json()
    if not h.get("index_ready"):
        print("FAIL: index_ready=false — run python -m pipeline.build_index", file=sys.stderr)
        sys.exit(2)

    results = []
    with httpx.Client() as client:
        for case in CASES:
            results.append(run_case(client, args.base_url, case))

    passed = sum(1 for r in results if r["passed"])
    print(json.dumps({"base_url": args.base_url, "passed": passed, "total": len(results), "results": results}, indent=2))
    if passed < len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
