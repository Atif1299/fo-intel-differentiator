# DESIGN — FO Intel Differentiator (Stage 1)

> Locked in Phase 0. Changes require an explicit entry in `../BUILD_TRACKER.md` Locked decisions.

## Hypothesis

Multi-class discovery + separate proof sources will produce a more decision-grade Family Office file than copying one public directory at scale. If any single discovery source exceeds 35% of the final 50, we treat that as a failed discovery design and rebalance before export.

## Inclusion bar (Rule 2 — firm)

### Categories

| `fo_type` | Ships in final 50? |
|-----------|-------------------|
| `single_family_office` | Yes, if inclusion evidence passes |
| `multi_family_office` | Yes, if inclusion evidence passes |
| `unknown_type` | **Never** |

### Affirmative evidence required

A firm qualifies only when we have affirmative evidence it **is** a family office. Acceptable evidence classes (need at least one strong, preferably corroborated):

- Firm self-describes as single- or multi-family office on its own site or materials
- Regulatory / filing language that names it as a family office
- Authoritative directory listing **plus** independent corroboration (site, press, filing)
- Principal / family wealth context that clearly names an FO **entity** (not a person alone)

**Not sufficient alone:** serves wealthy clients; “family office services” marketing by an RIA/bank; family-related words in the name; appearance on a FO-adjacent list without type confirmation.

### Mix target

Aim for **≥15** verified `single_family_office` records in the final 50 **if evidence supports**. Never relabel MFO → SFO. Prefer fewer honest SFOs over padded misclassified rows.

### Rejects

Duplicates, unconfirmed identity, failed inclusion standard → `data/audit/rejected.jsonl` (not customer CSV).

## Cell bar (Rule 1)

Every high-value field in provenance carries:

```json
{
  "value": "...",
  "sources": ["https://..."],
  "method": "page_extract|search_snippet|manual_spotcheck|...",
  "status": "verified|could_not_verify|rejected",
  "checked_at": "ISO-8601"
}
```

- Honest blank + `could_not_verify` = candor (allowed)
- Guessed value labeled `verified` = refuse to ship (self-disqualify)
- Validation governs release: failed email/check → blank customer field; keep detail in audit only

## Source classes (discovery ≠ proof)

| Class | Role | Examples (free / public) | Cap |
|-------|------|--------------------------|-----|
| A — Web discovery | Find candidate names | Targeted search, news (“family office” + geo), EDGAR search hits | Part of multi-class mix |
| B — Structured public lists | Seed only | Public FO directories, filings naming FOs, open lists | Must not dominate |
| C — Entity proof | Confirm FO type | Firm About pages, LinkedIn company, press with explicit FO language | Required for ship |
| D — Principal / contact | Actionability | LinkedIn profiles, team pages, public contact pages | No paid contact DB as primary proof |
| E — Signals | Why-now | Dated news, investments, hirings (date + URL) | Strongly preferred |

**Hard gate:** any single **discovery** source ID ≤ **35%** of firms in the qualifying 50. Pipeline export must print discovery-source distribution; fail export if gate broken.

## Customer schema (CSV)

| Column | Notes |
|--------|--------|
| `fo_id` | Stable id (slug or hash) |
| `legal_name` | |
| `common_name` | |
| `fo_type` | `single_family_office` \| `multi_family_office` |
| `hq_city` | |
| `hq_country` | |
| `website` | |
| `linkedin_company_url` | |
| `aum_note` | Text; blank ok if unverified |
| `investment_thesis` | |
| `investment_mandates` | |
| `principal_name` | |
| `principal_title` | |
| `principal_linkedin` | |
| `principal_email` | Only if validation allows |
| `principal_phone` | Only if validation allows |
| `signal_1_summary` | |
| `signal_1_date` | ISO date if known |
| `signal_1_url` | |
| `signal_2_summary` | Optional |
| `signal_2_date` | Optional |
| `signal_2_url` | Optional |
| `inclusion_evidence_summary` | Why this firm is an FO |
| `confidence_overall` | 0.0–1.0 |

## Provenance sidecar (JSONL)

One object per `fo_id`:

- `fields`: map of column → provenance object (above)
- `discovery_source_class`: primary discovery class letter
- `discovery_source_ids`: list of source ids used to **find** the firm
- `proof_source_ids`: sources used to **prove** FO type
- `rejection_reason`: if rejected

## Pipeline stages

1. **discover** → `data/raw/candidates.jsonl`
2. **enrich** → `data/processed/enriched.jsonl` (classify FO type + fill cells)
3. **validate** → pass / reject; validation layer checks inclusion + cell integrity
4. **export** → `data/export/family_offices_50.csv` + provenance JSONL; enforce 50 count + 35% gate

Manual spot-checks and judgment notes are allowed. Manual record-by-record CSV compilation is not.

## Micro-RAG + product

- Chunk each shipped record into retrieval units (entity card + principal + signals) via LangChain `Document`s
- Embeddings: OpenAI `text-embedding-3-small` via `OPENAI_API_KEY` (**paid — disclosed design decision**)
- Index: LangChain FAISS vectorstore (`python -m pipeline.build_index` → `data/index/`)
- Orchestration: **LangGraph** bounded graph `retrieve → ground → generate|decline` (not multi-agent swarm)
- Retrieval: structural filters (`fo_type`, `hq_country`, inferred from query) + semantic top-k
- **Grounding control (working gate):** min top relevance score + ≥1 usable chunk; else decline node — not prompt-only
- Answer LLM: OpenAI `gpt-4o-mini` over retrieved context only; `GEMINI_API_KEY` reserved as backup
- Customer UI: **Next.js** (App Router) — IR user opens live URL, asks a question, understands results without reading code
- API: FastAPI (`api/`) — `/health`, `/search`, `/ask`
- Deploy: **GCP Cloud Run** — services `fo-intel-api` + `fo-intel-web`

## Stack summary

| Layer | Choice |
|-------|--------|
| Pipeline | Python 3.11+ (`pipeline/`) |
| API | FastAPI (`api/`) |
| Customer UI | Next.js (`web/`) |
| RAG primitives | LangChain (Documents, OpenAIEmbeddings, FAISS) |
| Orchestration | LangGraph (thin retrieve→ground→answer\|decline) |
| Embeddings | OpenAI `text-embedding-3-small` |
| Vectors | FAISS via LangChain |
| Answer LLM | OpenAI `gpt-4o-mini` (Gemini backup) |
| Hosting | GCP Cloud Run |
| Repo target | `Atif1299/fo-intel-differentiator` |

## Paid tooling disclosure

Assessment allows paid tools if owned as a design decision. We use OpenAI + Cloud Run for retrieval quality and a production-shaped customer UI. Free-tier alternatives remain possible but are not the primary path for this submission.

## Out of scope (assessment discipline)

- Full commercial CRM
- Paid lead databases as primary discovery
- Localhost-only or notebook-only demos
- One-source bulk copy of a public FO list
- Jinja as the customer-facing product (API may keep a debug page only)
