# Tech notes (Micro-RAG) — Stage 1 deliverable

Brief note covering: stack choices, chunking, embedding model, retrieval, what works / what does not, **live queries actually run** against the deployed system, and what we would improve.

## Stack choices

| Layer | Choice | Notes |
|-------|--------|-------|
| Pipeline | Python | System of record for the 50 + provenance |
| API | FastAPI on Cloud Run | `/health`, `/search`, `/ask` |
| Orchestration | **LangGraph** | Bounded graph: retrieve → ground → generate\|decline |
| RAG primitives | **LangChain** | Documents, OpenAIEmbeddings, FAISS vectorstore |
| UI | Next.js on Cloud Run | Customer-facing product URL (IR-readable) |
| Embeddings | OpenAI `text-embedding-3-small` | Paid — disclosed |
| Vectors | FAISS via LangChain | `python -m pipeline.build_index` |
| Answer LLM | OpenAI `gpt-4o-mini` | Grounded on retrieved chunks only |

### Paid tooling

OpenAI and GCP Cloud Run are intentional. Bare FAISS scripts were rejected for this submission in favor of LangChain/LangGraph so retrieval orchestration matches a production-shaped micro-system — without multi-agent theater on a 50-row corpus.

## Chunking strategy

Each exported FO row → 2–3 LangChain `Document`s with metadata (`fo_id`, `fo_type`, `hq_country`, `chunk_kind`):

1. **entity** — names, type, geo, website, thesis/mandates, inclusion evidence  
2. **principal** — only if principal fields present  
3. **signal** — only if signal_1/2 present  

**Current index:** **118** documents / **50** firms (`data/index/index_meta.json`) after sample-audit scrub.

## Embedding model

OpenAI `text-embedding-3-small`

## Retrieval approach

1. Embed query; FAISS similarity top-k (LangChain)  
2. Optional structural filters: `fo_type` / country inferred from query (`sfo`/`mfo`, country keywords)  
3. **Grounding gate (working control):** top relevance score ≥ **0.55** and distance ≤ **0.95**; soft token-overlap check for long specific queries  
4. Pass → `gpt-4o-mini` with cite-only system prompt  
5. Fail → readable decline in customer language (no JSON dump)

Graph code: `api/rag.py`. Eval harness: `python scripts/answer_eval.py`.

This gate is the answer-layer control required by the assessment: prompt instructions alone are not treated as sufficient.

## What works / what does not

**Works**

- Named-firm questions (Matter, ckandcompany, Westerman, Sowell & Company, Old Mountain) return grounded IR prose + firm context  
- Invented / gibberish queries decline via gate (not LLM politeness alone)  
- SFO-oriented queries prefer single-family office chunks when filters fire  

**Does not / limits**

- Sparse geo fields on many rows → country filters often soft  
- Contact fields often blank (honest dataset) — system must not invent phones  
- Score thresholds are corpus-tuned; re-tune if the 50 change materially  
- Semantic retrieval can surface near-neighbors that are relevant but not the exact firm asked — grounding + cite discipline must hold  

## Live queries run against the deployed system

Customer UI: https://fo-intel-web-95044197271.us-central1.run.app  
API: https://fo-intel-api-95044197271.us-central1.run.app  

### Answer-eval suite (local + live Cloud Run) — **10/10 passed** (2026-07-25)

| Query | Result | Firms shown | Notes |
|-------|--------|-------------|-------|
| What type of family office is Matter Family Office? | ok | 1 | MFO grounded |
| Is ckandcompany a single-family office? | ok | 1 | SFO grounded |
| What does Westerman Capital do? | ok | 1 | Named-firm only (not neighbors) |
| List single-family offices with investment or venture signals | ok | 6 | Multi-firm list |
| Which family offices are multi-family offices? | ok | 6 | Multi-firm MFO list |
| List family offices in Texas or Dallas | ok | 3 | Multi-firm geo list |
| Which family offices have recent investment or hiring signals? | ok | 3 | Multi-firm signals |
| Name family offices that invest in real estate or private equity | ok | 3 | Multi-firm mandate |
| Phone of Emperor of Mars Family Office XYZQwerty999? | insufficient_evidence | 0 | Gate decline |
| asdf qwerty zxcvbn unrelated gibberish 12345 | insufficient_evidence | 0 | Gate decline |

### Post-rename search smoke (live API `/search`, after geo-name pass)

| Query | Top hit observed |
|-------|------------------|
| Sowell | Sowell & Company |
| Old Mountain | Old Mountain |
| Dakota | Dakota |
| Miami Family | The Miami Family Office |

## What we would improve

- Persist retrieval traces (JSONL or LangSmith) for every `/ask` in production  
- Hybrid BM25 + vector for exact firm-name hits  
- Expand geo enrichment so country filters are sharper  
- Optional second LLM provider failover on OpenAI 5xx (not wired in this build)  
- Deeper contact enrichment with the same Rule 1 discipline (fight for cells without inventing)  

## Answer-layer vs dataset-layer (both tested)

| Layer | How tested |
|-------|------------|
| Dataset | Phase 3 validate/export + `docs/validation_chains.md` + export_stats gates |
| Answers | LangGraph ground node + `scripts/answer_eval.py` (local + live Cloud Run) + post-rename `/search` smoke |

Testing one layer does not substitute for the other.
