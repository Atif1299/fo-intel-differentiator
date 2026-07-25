<p align="center">
  <img src="docs/assets/banner.png" alt="FO Intel — Family Office Intelligence" width="920"/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Next.js-000000?logo=nextdotjs&logoColor=white" alt="Next.js"/>
  <img src="https://img.shields.io/badge/LangGraph-1C3C3C?logo=langchain&logoColor=white" alt="LangGraph"/>
  <img src="https://img.shields.io/badge/FAISS-OpenAI-412991?logo=openai&logoColor=white" alt="FAISS OpenAI"/>
  <img src="https://img.shields.io/badge/GCP%20Cloud%20Run-4285F4?logo=googlecloud&logoColor=white" alt="GCP Cloud Run"/>
</p>

<p align="center"><b>Discover · prove · validate 50 family offices — then ask in natural language on a live customer UI.</b></p>

<p align="center">
  <a href="https://fo-intel-web-95044197271.us-central1.run.app">Live App</a> ·
  <a href="DESIGN.md">Design</a> ·
  <a href="docs/methodology.md">Methodology</a> ·
  <a href="docs/tech_notes.md">Tech Notes</a> ·
  <a href="https://fo-intel-api-95044197271.us-central1.run.app/docs">API Docs</a>
</p>

---

# FO Intel — Differentiator Stage 1

Pipeline-built dataset of **50 validated family office records**, served through a production-shaped Micro-RAG (LangChain FAISS + LangGraph grounding) and a **customer-facing** Next.js UI on GCP Cloud Run.

**Live customer URL:** https://fo-intel-web-95044197271.us-central1.run.app  
**API (supporting):** https://fo-intel-api-95044197271.us-central1.run.app/docs  

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
- **29** `single_family_office` / **21** `multi_family_office`  
- Max primary discovery share: **24%** (`rss:google_news_fo`) — under ≤35% hard gate  
- High-value cell fill on shipped CSV (honest blanks allowed): principal name **29**/50, email **10**/50, phone **10**/50, signal_1 **34**/50, website **40**/50  
- Sample-audit scrub: brand near-dupes collapsed (Cresset/Farther); network/platform rows refused (Global FO / QP / Dakota); Alpha coerced SFO→MFO; fill via disclosed manual spot-checks where classify returned unknown

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
