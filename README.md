# FO Intel — Differentiator Stage 1

Customer-facing Family Office intelligence (Next.js) over a Python pipeline-built dataset of 50 validated records. API on FastAPI. Deploy target: GCP Cloud Run.

## Docs

- [DESIGN.md](DESIGN.md) — inclusion rules, sources, schema, grounding, stack
- [docs/methodology.md](docs/methodology.md)
- [docs/validation_chains.md](docs/validation_chains.md)
- [docs/tech_notes.md](docs/tech_notes.md)
- [docs/task2_conversion.md](docs/task2_conversion.md)
- [docs/build_session_summary.md](docs/build_session_summary.md)

## Layout

```
pipeline/   # discover → enrich → validate → export (Python)
api/        # FastAPI JSON API + RAG index
web/        # Next.js customer UI
data/       # raw / processed / export / audit
```

## Setup

```bash
cd Polarity_Differentiator/fo-intel
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Put OPENAI_API_KEY in .env

cd web
copy .env.local.example .env.local
npm install
```

## Pipeline

```bash
python -m pipeline.discover
python -m pipeline.enrich          # or: python -m pipeline.enrich --resume
python -m pipeline.validate
python -m pipeline.export
python -m pipeline.build_index     # LangChain FAISS for Micro-RAG
```

## Local API + UI

```bash
# terminal 1
uvicorn api.main:app --reload --port 8000

# terminal 2
cd web
npm run dev
```

Open `http://127.0.0.1:3000` (UI). API health: `http://127.0.0.1:8000/health`.

Answer-layer checks: `python scripts/answer_eval.py`

## Live (GCP Cloud Run)

- **Customer UI:** https://fo-intel-web-95044197271.us-central1.run.app  
- **API:** https://fo-intel-api-95044197271.us-central1.run.app  

Redeploy: `.\scripts\deploy_cloud_run.ps1`

## Paid tooling

OpenAI embeddings + gpt-4o-mini, LangChain/LangGraph orchestration, and Cloud Run are intentional (disclosed in tech_notes / DESIGN).

## Priority

Dataset first → working functionality second → presentation third.
