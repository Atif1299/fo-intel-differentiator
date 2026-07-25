"""FO Intel API — LangGraph Micro-RAG over verified Family Office records."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api import rag
from api.startup import ensure_index


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_index()
    yield


app = FastAPI(
    title="FO Intel API",
    description="Family Office intelligence retrieval. Grounded answers only (LangGraph).",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    fo_type: str | None = None
    hq_country: str | None = None


class AskResponse(BaseModel):
    status: str  # ok | insufficient_evidence | not_ready
    message: str
    query: str
    answer: str | None = None
    records: list[dict] = Field(default_factory=list)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "fo-intel-api",
        "index_ready": rag.index_ready(),
        "orchestration": "langgraph",
        "retrieval": "langchain-faiss-openai",
    }


@app.get("/search")
async def search(q: str = "", limit: int = 5) -> dict:
    """Structural filters (inferred) + semantic top-k."""
    return rag.run_search(q, limit=min(max(limit, 1), 20))


@app.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest) -> AskResponse:
    """LangGraph: retrieve → ground → generate | decline."""
    out = rag.run_ask(body.query, fo_type=body.fo_type, hq_country=body.hq_country)
    return AskResponse(
        status=out["status"],
        message=out["message"],
        query=out["query"],
        answer=out.get("answer"),
        records=out.get("records") or [],
    )
