# FO Intel — Differentiator Stage 1

Pipeline-built dataset of **50 validated family office records**, served through a production-shaped Micro-RAG (LangChain FAISS + LangGraph grounding) and a **customer-facing** Next.js UI on GCP Cloud Run.

**GitHub:** https://github.com/Atif1299/fo-intel-differentiator  
**Live customer URL:** https://fo-intel-web-95044197271.us-central1.run.app  
**API (supporting):** https://fo-intel-api-95044197271.us-central1.run.app  

The 50-row CSV is produced by `pipeline/` (discover → enrich → validate → export). It was not hand-assembled row by row.

## Stage 1 deliverable map

| Deliverable | Where |
|-------------|--------|
| 50-record dataset (CSV) | `data/export/family_offices_50.csv` |
| Provenance sidecar | `data/export/provenance.jsonl` |
| Methodology (find / enrich / validate / source classes / blind spots) | `docs/methodology.md` |
| 3 full validation chains | `docs/validation_chains.md` |
| Full pipeline + RAG in GitHub | this repo |
| Live customer-facing URL | link above (not API-only) |
| Stack / chunking / retrieval / live queries / limits | `docs/tech_notes.md` |
| Task 2 — SaaS conversion | `docs/task2_conversion.md` |
| Build session summary | `docs/build_session_summary.md` |
| Locked inclusion / schema / grounding rules | `DESIGN.md` |

## Final export snapshot (reconciles with artifacts)

From `data/export/export_stats.json` after hygiene + on-site name pass:

- **50** unique qualifying rows  
- **31** `single_family_office` / **19** `multi_family_office`  
- Max primary discovery share: **28%** (`rss:google_news_fo`) — under ≤35% hard gate  
- High-value cell fill on shipped CSV (honest blanks allowed): principal name **31**/50, email **11**/50, phone **11**/50, signal_1 **37**/50, website **39**/50  

## Docs

- [DESIGN.md](DESIGN.md) — Rule 1/2, source classes, schema, RAG controls  
- [docs/methodology.md](docs/methodology.md)  
- [docs/validation_chains.md](docs/validation_chains.md)  
- [docs/tech_notes.md](docs/tech_notes.md)  
- [docs/task2_conversion.md](docs/task2_conversion.md)  
- [docs/build_session_summary.md](docs/build_session_summary.md)  

## Layout

```
pipeline/   # discover → enrich → validate → export → build_index
api/        # FastAPI + LangGraph RAG (/health, /search, /ask)
web/        # Next.js customer UI (IR-readable answers + declines)
data/       # raw / processed / export / index / audit
docs/       # assessment write-ups
scripts/    # deploy, answer_eval, hygiene helpers
```

## Setup

```bash
cd fo-intel
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Set OPENAI_API_KEY in .env

cd web
copy .env.local.example .env.local
npm install
```

## Pipeline (system of record for the 50)

```bash
python -m pipeline.discover
python -m pipeline.enrich          # or: python -m pipeline.enrich --resume
python -m pipeline.validate
python -m pipeline.export
python -m pipeline.build_index     # LangChain FAISS → data/index/
```

## Local API + UI

```bash
# terminal 1
uvicorn api.main:app --reload --port 8000

# terminal 2
cd web
npm run dev
```

UI: `http://127.0.0.1:3000` · API health: `http://127.0.0.1:8000/health`  
Answer-layer suite: `python scripts/answer_eval.py`

## Deploy

```powershell
.\scripts\deploy_cloud_run.ps1
```

## Paid tooling (disclosed)

OpenAI (`text-embedding-3-small`, `gpt-4o-mini`) and GCP Cloud Run are intentional design choices. See `DESIGN.md` and `docs/tech_notes.md`.

## Priority used on this build

Dataset first → working functionality second → presentation third.
