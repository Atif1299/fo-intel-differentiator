"""
Micro-RAG: LangChain FAISS retrieval + LangGraph bounded orchestration.

Graph: retrieve → ground → (generate | decline)
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.graph import END, START, StateGraph

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

INDEX_DIR = Path(os.getenv("FO_INDEX_DIR", str(ROOT / "data" / "index")))
EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"

# Grounding gate (working control — not prompt-only)
MIN_TOP_SCORE = 0.55  # tuned: known FO ~0.65+, gibberish ~0.38, invented FO ~0.47
MAX_TOP_DISTANCE = 0.95  # FAISS L2; farther = weak match
MIN_DOCS = 1
RETRIEVE_K = 6

DECLINE_MESSAGE = (
    "We do not have enough verified evidence in the Family Office dataset to answer "
    "that reliably. Try a more specific question about a firm name, FO type "
    "(single- or multi-family office), geography, or a known investment signal."
)


class RagState(TypedDict, total=False):
    query: str
    fo_type: str | None
    hq_country: str | None
    docs: list[Document]
    scores: list[float]
    grounding_ok: bool
    status: str
    message: str
    answer: str | None
    records: list[dict[str, Any]]


def _score_from_distance(distance: float) -> float:
    """Convert FAISS L2 distance on normalized embeds to a 0–1-ish relevance score."""
    return float(1.0 / (1.0 + max(distance, 0.0)))


@lru_cache(maxsize=1)
def load_vectorstore() -> FAISS:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing")
    if not (INDEX_DIR / "index.faiss").exists() and not (INDEX_DIR / "index.pkl").exists():
        # LangChain FAISS save_local writes index.faiss + index.pkl
        raise FileNotFoundError(
            f"FAISS index not found at {INDEX_DIR}. Run: python -m pipeline.build_index"
        )
    embeddings = OpenAIEmbeddings(model=EMBED_MODEL, api_key=api_key)
    return FAISS.load_local(
        str(INDEX_DIR),
        embeddings,
        allow_dangerous_deserialization=True,
    )


def index_ready() -> bool:
    d = INDEX_DIR
    return (d / "index.faiss").exists() and (d / "index.pkl").exists()


def _infer_filters(query: str) -> tuple[str | None, str | None]:
    q = query.lower()
    fo_type = None
    if re.search(r"\b(sfo|single[-\s]?family)\b", q):
        fo_type = "single_family_office"
    elif re.search(r"\b(mfo|multi[-\s]?family)\b", q):
        fo_type = "multi_family_office"

    country = None
    country_map = {
        "united states": "United States",
        "usa": "United States",
        "u.s.": "United States",
        "uk": "United Kingdom",
        "united kingdom": "United Kingdom",
        "singapore": "Singapore",
        "switzerland": "Switzerland",
        "canada": "Canada",
    }
    for key, val in country_map.items():
        if key in q:
            country = val
            break
    return fo_type, country


def retrieve_node(state: RagState) -> RagState:
    query = (state.get("query") or "").strip()
    fo_type = state.get("fo_type")
    hq_country = state.get("hq_country")
    if fo_type is None and hq_country is None:
        fo_type, hq_country = _infer_filters(query)

    store = load_vectorstore()
    pairs = store.similarity_search_with_score(query, k=RETRIEVE_K * 3)
    docs: list[Document] = []
    scores: list[float] = []
    for doc, dist in pairs:
        meta = doc.metadata or {}
        if fo_type and meta.get("fo_type") and meta.get("fo_type") != fo_type:
            continue
        if hq_country and meta.get("hq_country") and meta.get("hq_country") != hq_country:
            # soft: keep if country blank on chunk
            if meta.get("hq_country"):
                continue
        score = _score_from_distance(float(dist))
        docs.append(doc)
        scores.append(score)
        if len(docs) >= RETRIEVE_K:
            break

    return {
        **state,
        "fo_type": fo_type,
        "hq_country": hq_country,
        "docs": docs,
        "scores": scores,
    }


def ground_node(state: RagState) -> RagState:
    docs = state.get("docs") or []
    scores = state.get("scores") or []
    top = scores[0] if scores else 0.0
    # Reconstruct approximate distance from score: score = 1/(1+d) → d = 1/score - 1
    top_dist = (1.0 / top - 1.0) if top > 0 else 999.0
    ok = len(docs) >= MIN_DOCS and top >= MIN_TOP_SCORE and top_dist <= MAX_TOP_DISTANCE
    if ok and not any((d.page_content or "").strip() for d in docs):
        ok = False
    # Soft name anchor: if query looks like a specific invented proper name, require overlap
    query = (state.get("query") or "").lower()
    if ok and len(query.split()) >= 6:
        names = " ".join((d.metadata or {}).get("common_name") or "" for d in docs).lower()
        # Require at least one contentful token from query to appear in firm names or chunk text
        tokens = [t for t in re.findall(r"[a-z]{4,}", query) if t not in {
            "what", "which", "about", "family", "office", "offices", "single", "multi",
            "tell", "list", "with", "have", "does", "from", "their", "there", "phone",
            "number", "email", "where", "based", "invest", "venture", "signal", "signals",
        }]
        blob = names + " " + " ".join((d.page_content or "").lower() for d in docs)
        if tokens and not any(t in blob for t in tokens[:8]):
            ok = False
    return {
        **state,
        "grounding_ok": ok,
        "status": "ok" if ok else "insufficient_evidence",
        "message": "Grounded on retrieved Family Office records." if ok else DECLINE_MESSAGE,
    }


def route_after_ground(state: RagState) -> Literal["generate", "decline"]:
    return "generate" if state.get("grounding_ok") else "decline"


def _docs_to_records(docs: list[Document]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    for d in docs:
        m = d.metadata or {}
        fo_id = str(m.get("fo_id") or "")
        if not fo_id or fo_id in seen:
            continue
        seen.add(fo_id)
        records.append(
            {
                "fo_id": fo_id,
                "common_name": m.get("common_name"),
                "fo_type": m.get("fo_type"),
                "hq_city": m.get("hq_city"),
                "hq_country": m.get("hq_country"),
                "website": m.get("website"),
                "chunk_kind": m.get("chunk_kind"),
            }
        )
    return records


def generate_node(state: RagState) -> RagState:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    docs = state.get("docs") or []
    context_blocks = []
    for i, d in enumerate(docs, 1):
        m = d.metadata or {}
        context_blocks.append(
            f"[{i}] fo_id={m.get('fo_id')} name={m.get('common_name')} "
            f"type={m.get('fo_type')} kind={m.get('chunk_kind')}\n{d.page_content}"
        )
    context = "\n\n".join(context_blocks)
    llm = ChatOpenAI(model=CHAT_MODEL, temperature=0, api_key=api_key)
    system = (
        "You are an investor-relations research assistant for verified Family Office data. "
        "Answer ONLY using the CONTEXT. Do not invent contacts, AUM, or FO types. "
        "If CONTEXT does not support a claim, omit it. "
        "Write clear prose for a non-technical IR reader. "
        "End with a short 'Based on:' line listing firm names you used."
    )
    user = f"QUESTION:\n{state.get('query')}\n\nCONTEXT:\n{context}"
    resp = llm.invoke(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    )
    answer = (resp.content or "").strip() if hasattr(resp, "content") else str(resp)
    return {
        **state,
        "status": "ok",
        "message": "Answer grounded in retrieved Family Office records.",
        "answer": answer,
        "records": _docs_to_records(docs),
    }


def decline_node(state: RagState) -> RagState:
    return {
        **state,
        "status": "insufficient_evidence",
        "message": DECLINE_MESSAGE,
        "answer": None,
        "records": _docs_to_records(state.get("docs") or []),
    }


@lru_cache(maxsize=1)
def build_graph():
    g = StateGraph(RagState)
    g.add_node("retrieve", retrieve_node)
    g.add_node("ground", ground_node)
    g.add_node("generate", generate_node)
    g.add_node("decline", decline_node)
    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "ground")
    g.add_conditional_edges("ground", route_after_ground, {"generate": "generate", "decline": "decline"})
    g.add_edge("generate", END)
    g.add_edge("decline", END)
    return g.compile()


def run_ask(
    query: str,
    fo_type: str | None = None,
    hq_country: str | None = None,
) -> dict[str, Any]:
    if not query.strip():
        return {
            "status": "insufficient_evidence",
            "message": "Empty query.",
            "query": query,
            "answer": None,
            "records": [],
        }
    if not index_ready():
        return {
            "status": "not_ready",
            "message": "Index not built yet. Run: python -m pipeline.build_index",
            "query": query,
            "answer": None,
            "records": [],
        }
    graph = build_graph()
    result = graph.invoke(
        {
            "query": query.strip(),
            "fo_type": fo_type,
            "hq_country": hq_country,
        }
    )
    return {
        "status": result.get("status") or "insufficient_evidence",
        "message": result.get("message") or DECLINE_MESSAGE,
        "query": query,
        "answer": result.get("answer"),
        "records": result.get("records") or [],
    }


def run_search(query: str, limit: int = 5) -> dict[str, Any]:
    if not query.strip():
        return {"status": "insufficient_evidence", "results": [], "message": "Empty query.", "query": query}
    if not index_ready():
        return {
            "status": "not_ready",
            "results": [],
            "message": "Index not built yet. Run: python -m pipeline.build_index",
            "query": query,
            "limit": limit,
        }
    store = load_vectorstore()
    fo_type, hq_country = _infer_filters(query)
    pairs = store.similarity_search_with_score(query, k=max(limit * 3, 6))
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for doc, dist in pairs:
        m = doc.metadata or {}
        if fo_type and m.get("fo_type") and m.get("fo_type") != fo_type:
            continue
        fo_id = str(m.get("fo_id") or "")
        if fo_id in seen:
            continue
        seen.add(fo_id)
        results.append(
            {
                "fo_id": fo_id,
                "common_name": m.get("common_name"),
                "fo_type": m.get("fo_type"),
                "hq_city": m.get("hq_city"),
                "hq_country": m.get("hq_country"),
                "website": m.get("website"),
                "score": round(_score_from_distance(float(dist)), 4),
                "snippet": (doc.page_content or "")[:280],
            }
        )
        if len(results) >= limit:
            break
    status = "ok" if results else "insufficient_evidence"
    return {
        "status": status,
        "results": results,
        "message": "Semantic search results." if results else DECLINE_MESSAGE,
        "query": query,
        "limit": limit,
        "filters": {"fo_type": fo_type, "hq_country": hq_country},
    }


# Back-compat helpers used by build tooling / tests
def build_index_from_csv(csv_path: str, index_dir: str) -> None:
    from pipeline.build_index import build_index

    build_index(Path(csv_path), Path(index_dir))


def retrieve(query: str, k: int = 5) -> list[dict]:
    out = run_search(query, limit=k)
    return list(out.get("results") or [])
