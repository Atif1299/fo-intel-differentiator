"""Ensure FAISS index exists at API startup (Cloud Run cold start safety)."""

from __future__ import annotations

import os
from pathlib import Path

from api import rag


def ensure_index() -> None:
    if rag.index_ready():
        return
    csv_path = Path(os.getenv("FO_CSV_PATH", "/app/data/export/family_offices_50.csv"))
    index_dir = Path(os.getenv("FO_INDEX_DIR", "/app/data/index"))
    if not csv_path.exists():
        # Local default
        root = Path(__file__).resolve().parents[1]
        csv_path = root / "data" / "export" / "family_offices_50.csv"
        index_dir = root / "data" / "index"
    if not csv_path.exists():
        print(f"[startup] no CSV at {csv_path}; index not built")
        return
    print(f"[startup] building FAISS index from {csv_path} → {index_dir}")
    from pipeline.build_index import build_index

    build_index(csv_path, index_dir)
    rag.load_vectorstore.cache_clear()
    rag.build_graph.cache_clear()
    print(f"[startup] index_ready={rag.index_ready()}")
