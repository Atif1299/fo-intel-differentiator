# Tech notes (Micro-RAG)

## Stack choices (relocked)

| Layer | Choice | Notes |
|-------|--------|-------|
| Pipeline | Python | Produces the 50 + provenance |
| API | FastAPI on Cloud Run | `/health`, `/search`, `/ask` |
| Orchestration | **LangGraph** | Bounded graph: retrieve → ground → generate\|decline |
| RAG primitives | **LangChain** | Documents, OpenAIEmbeddings, FAISS vectorstore |
| UI | Next.js on Cloud Run | Customer-facing product URL |
| Embeddings | OpenAI `text-embedding-3-small` | Paid — disclosed |
| Vectors | FAISS via LangChain | Built by `python -m pipeline.build_index` |
| Answer LLM | OpenAI `gpt-4o-mini` | Grounded only; Gemini backup |

## Paid tooling

We use OpenAI and GCP Cloud Run by design (assessment allows paid tools if disclosed). Bare FAISS scripts were rejected for this submission in favor of LangChain/LangGraph so retrieval orchestration matches the Agentic AI Engineer JD — without multi-agent theater on a 50-row corpus.

## Chunking strategy

Each exported FO row → 2–3 LangChain `Document`s with metadata (`fo_id`, `fo_type`, `hq_country`, `chunk_kind`):

1. **entity** — names, type, geo, website, thesis/mandates, inclusion evidence  
2. **principal** — only if principal fields present  
3. **signal** — only if signal_1/2 present  

Index: 122 documents / 50 firms (`data/index/index_meta.json`).

## Embedding model

OpenAI `text-embedding-3-small`

## Retrieval approach

1. Embed query; FAISS similarity top-k (LangChain)  
2. Optional structural filters: `fo_type` / country inferred from query (`sfo`/`mfo`, country keywords)  
3. **Grounding gate (working control):** top relevance score ≥ 0.55 and distance ≤ 0.95; soft token-overlap check for long specific queries  
4. Pass → `gpt-4o-mini` with cite-only system prompt  
5. Fail → readable decline (no JSON dump)

Graph code: `api/rag.py`. Eval: `python scripts/answer_eval.py`.

## What works / what does not

**Works**

- Named-firm questions (Matter, ckandcompany, Westerman) return grounded IR prose + firm list  
- Invented / gibberish queries decline via gate (not LLM politeness alone)  
- SFO-oriented queries retrieve single-family office chunks preferentially  

**Does not / limits**

- Sparse geo fields on many rows → country filters often soft  
- Contact fields often blank (honest dataset) — system must not invent phones  
- Score thresholds are corpus-tuned; re-tune if the 50 change materially  

## Live queries run against deployed system

| Query | Result | Notes |
|-------|--------|-------|
| What type of family office is Matter Family Office? | ok | MFO grounded |
| Is ckandcompany a single-family office? | ok | SFO grounded |
| What does Westerman Capital do? | ok | Class B discovery firm, Class C site proof in dataset |
| List single-family offices with investment or venture signals | ok | Structural+semantic |
| Phone of Emperor of Mars Family Office XYZQwerty999? | insufficient_evidence | Gate decline |
| asdf qwerty zxcvbn unrelated gibberish 12345 | insufficient_evidence | Gate decline |

Local eval: `scripts/answer_eval.py` → **6/6 passed**.  
Live API eval (same suite against Cloud Run): **6/6 passed** (2026-07-25).  
Live customer URL: https://fo-intel-web-95044197271.us-central1.run.app  
Live API: https://fo-intel-api-95044197271.us-central1.run.app  

## What we would improve

- Persist retrieval traces (LangSmith or simple JSONL) for every `/ask` in production  
- Add hybrid BM25 + vector for exact firm-name hits  
- Expand geo enrichment so country filters are sharper  
- Gemini failover path when OpenAI 5xx  

## Answer-layer vs dataset-layer

| Layer | How tested |
|-------|------------|
| Dataset | Phase 3 validate/export + validation_chains.md |
| Answers | LangGraph ground node + `scripts/answer_eval.py` (local + live Cloud Run) |