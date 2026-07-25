"""
Build FAISS index from exported 50 FO CSV using LangChain + OpenAI embeddings.

CLI: python -m pipeline.build_index
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

CSV_PATH = ROOT / "data" / "export" / "family_offices_50.csv"
INDEX_DIR = ROOT / "data" / "index"
META_PATH = INDEX_DIR / "index_meta.json"

EMBED_MODEL = "text-embedding-3-small"


def _cell(row: dict, key: str) -> str:
    v = row.get(key)
    if v is None:
        return ""
    s = str(v).strip()
    return s if s and s.lower() != "none" else ""


def row_to_documents(row: dict) -> list[Document]:
    fo_id = _cell(row, "fo_id") or "unknown"
    name = _cell(row, "common_name") or _cell(row, "legal_name") or fo_id
    fo_type = _cell(row, "fo_type")
    city = _cell(row, "hq_city")
    country = _cell(row, "hq_country")
    website = _cell(row, "website")

    base_meta = {
        "fo_id": fo_id,
        "fo_type": fo_type,
        "hq_city": city,
        "hq_country": country,
        "common_name": name,
        "website": website,
    }

    docs: list[Document] = []

    entity_parts = [
        f"Family office: {name}",
        f"Legal name: {_cell(row, 'legal_name')}" if _cell(row, "legal_name") else "",
        f"Type: {fo_type.replace('_', ' ')}" if fo_type else "",
        f"HQ: {city}, {country}".strip(", ") if city or country else "",
        f"Website: {website}" if website else "",
        f"LinkedIn: {_cell(row, 'linkedin_company_url')}" if _cell(row, "linkedin_company_url") else "",
        f"AUM note: {_cell(row, 'aum_note')}" if _cell(row, "aum_note") else "",
        f"Investment thesis: {_cell(row, 'investment_thesis')}" if _cell(row, "investment_thesis") else "",
        f"Investment mandates: {_cell(row, 'investment_mandates')}" if _cell(row, "investment_mandates") else "",
        f"Inclusion evidence: {_cell(row, 'inclusion_evidence_summary')}"
        if _cell(row, "inclusion_evidence_summary")
        else "",
    ]
    entity_text = "\n".join(p for p in entity_parts if p)
    docs.append(
        Document(
            page_content=entity_text,
            metadata={**base_meta, "chunk_kind": "entity"},
        )
    )

    principal_bits = [
        f"Principal for {name}",
        f"Name: {_cell(row, 'principal_name')}" if _cell(row, "principal_name") else "",
        f"Title: {_cell(row, 'principal_title')}" if _cell(row, "principal_title") else "",
        f"LinkedIn: {_cell(row, 'principal_linkedin')}" if _cell(row, "principal_linkedin") else "",
        f"Email: {_cell(row, 'principal_email')}" if _cell(row, "principal_email") else "",
        f"Phone: {_cell(row, 'principal_phone')}" if _cell(row, "principal_phone") else "",
    ]
    principal_body = "\n".join(p for p in principal_bits if p)
    if _cell(row, "principal_name") or _cell(row, "principal_email") or _cell(row, "principal_linkedin"):
        docs.append(
            Document(
                page_content=principal_body,
                metadata={**base_meta, "chunk_kind": "principal"},
            )
        )

    signal_bits = [
        f"Signals for {name}",
        f"Signal 1: {_cell(row, 'signal_1_summary')}" if _cell(row, "signal_1_summary") else "",
        f"Signal 1 date: {_cell(row, 'signal_1_date')}" if _cell(row, "signal_1_date") else "",
        f"Signal 1 URL: {_cell(row, 'signal_1_url')}" if _cell(row, "signal_1_url") else "",
        f"Signal 2: {_cell(row, 'signal_2_summary')}" if _cell(row, "signal_2_summary") else "",
        f"Signal 2 date: {_cell(row, 'signal_2_date')}" if _cell(row, "signal_2_date") else "",
        f"Signal 2 URL: {_cell(row, 'signal_2_url')}" if _cell(row, "signal_2_url") else "",
    ]
    signal_body = "\n".join(p for p in signal_bits if p)
    if _cell(row, "signal_1_summary") or _cell(row, "signal_2_summary"):
        docs.append(
            Document(
                page_content=signal_body,
                metadata={**base_meta, "chunk_kind": "signal"},
            )
        )

    return docs


def load_documents(csv_path: Path = CSV_PATH) -> list[Document]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing {csv_path} — run pipeline export first")
    docs: list[Document] = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            docs.extend(row_to_documents(row))
    return docs


def build_index(csv_path: Path = CSV_PATH, index_dir: Path = INDEX_DIR) -> Path:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("ERROR: OPENAI_API_KEY missing in fo-intel/.env", file=sys.stderr)
        sys.exit(1)

    docs = load_documents(csv_path)
    if not docs:
        print("ERROR: no documents from CSV", file=sys.stderr)
        sys.exit(1)

    print(f"[build_index] documents={len(docs)} model={EMBED_MODEL}")
    embeddings = OpenAIEmbeddings(model=EMBED_MODEL, api_key=api_key)
    store = FAISS.from_documents(docs, embeddings)

    index_dir.mkdir(parents=True, exist_ok=True)
    store.save_local(str(index_dir))

    meta = {
        "embed_model": EMBED_MODEL,
        "document_count": len(docs),
        "csv": str(csv_path.as_posix()),
        "fo_count": len({d.metadata.get("fo_id") for d in docs}),
    }
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[build_index] wrote {index_dir} meta={meta}")
    return index_dir


def main() -> None:
    build_index()


if __name__ == "__main__":
    main()
