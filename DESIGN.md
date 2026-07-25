# DESIGN — FO Intel Differentiator (Stage 1)

> Locked in Phase 0. Material changes belong in the build tracker / methodology blind spots — not silent drift.

## Hypothesis

Multi-class discovery plus **separate** proof sources produces a more decision-grade Family Office file than copying one public directory at scale. If any single **discovery** source exceeds **35%** of the final 50, treat that as a failed discovery design and rebalance before export.

**What we verified on the shipped file:** max primary share **28%** (`rss:google_news_fo`) — gate held (`data/export/export_stats.json`).

## Inclusion bar (Rule 2 — firm)

### Categories

| `fo_type` | Ships in final 50? |
|-----------|-------------------|
| `single_family_office` | Yes, if inclusion evidence passes |
| `multi_family_office` | Yes, if inclusion evidence passes |
| `unknown_type` | **Never** |

### Affirmative evidence required

A firm qualifies only when we have affirmative evidence it **is** a family office. Acceptable evidence (need at least one strong Class C proof, preferably corroborated):

- Firm self-describes as single- or multi-family office on its own site or materials  
- Regulatory / filing language that names it as a family office  
- Authoritative directory listing **plus** independent corroboration (site, press, filing)  
- Principal / family wealth context that clearly names an FO **entity** (not a person alone)

**Not sufficient alone:** serves wealthy clients; “family office services” marketing by an RIA/bank; family-related words in the name; appearance on a FO-adjacent list without type confirmation.

### Mix target

Aim for **≥15** verified `single_family_office` records in the final 50 **if evidence supports**. Never relabel MFO → SFO.

**Shipped mix:** SFO **31** / MFO **19** (`export_stats.json`).

### Rejects

Duplicates, unconfirmed identity, failed inclusion, entity-hygiene fails → `data/audit/rejected.jsonl` (not customer CSV).

### Entity hygiene (post-self-audit gate)

Refuse to ship as FO entities:

- Report / title crumbs (e.g. “Asset Pools Report”)  
- Hub / publisher firm homes used as the FO identity  
- Category-only names  
- Geo SERP crumbs **without** a known firm domain  

News-host URLs are blanked rather than treated as institutional websites. Geo crumbs that **did** map to firm domains were later renamed to on-site brand/legal names only when corroborated (see methodology) — no invented names.

## Cell bar (Rule 1)

Every high-value field in provenance carries:

```json
{
  "value": "...",
  "sources": ["https://..."],
  "method": "page_extract|search_snippet|openai_classify_extract|onsite_name_hygiene|...",
  "status": "verified|could_not_verify|rejected",
  "checked_at": "ISO-8601"
}
```

- Honest blank + `could_not_verify` = candor (allowed)  
- Guessed value labeled `verified` = refuse to ship  
- Validation governs release: unsafe/unproven contact → blank customer field; detail stays in audit only  

## Source classes (discovery ≠ proof)

| Class | Role | Examples used | Cap |
|-------|------|---------------|-----|
| A — Web discovery | Find candidate names | DuckDuckGo geo/query adapters, Google News RSS, SEC EDGAR full-text | Part of multi-class mix |
| B — Structured public lists | Seed only | SWFI/public FO profile HTML; wiki adapter ran (little unique after merge) | Must not dominate |
| C — Entity proof | Confirm FO type | Firm site / about / careers pages (`class_c_fetch`) | Required to ship |
| D — Principal / contact | Actionability | Team pages, LinkedIn when present | No paid contact DB as primary proof |
| E — Signals | Why-now | Dated news / activity with URL when extractable | Preferred; blanks honest |

**Hard gate:** any single discovery source ID ≤ **35%** of firms in the qualifying 50. Export fails if broken.

## Customer schema (CSV)

| Column | Notes |
|--------|--------|
| `fo_id` | Stable id (slug + hash) |
| `legal_name` | |
| `common_name` | |
| `fo_type` | `single_family_office` \| `multi_family_office` |
| `hq_city` / `hq_country` | |
| `website` / `linkedin_company_url` | |
| `aum_note` | Text; blank if unverified |
| `investment_thesis` / `investment_mandates` | |
| `principal_name` / `principal_title` / `principal_linkedin` | |
| `principal_email` / `principal_phone` | Only if provenance allows |
| `signal_1_*` / `signal_2_*` | Summary, date, URL |
| `inclusion_evidence_summary` | Why this firm is an FO |
| `confidence_overall` | 0.0–1.0 |

## Provenance sidecar (JSONL)

One object per `fo_id` in `data/export/provenance.jsonl`:

- `fields`: column → provenance object  
- `discovery_source_class` / `discovery_source_ids`  
- `proof_source_ids`  
- rejection detail lives in audit when not shipped  

## Pipeline stages

1. **discover** → `data/raw/candidates.jsonl` (+ `discovery_stats.json`)  
2. **enrich** → `data/processed/enriched.jsonl` (classify FO type + fill cells)  
3. **validate** → pass / reject; inclusion + cell integrity + entity hygiene  
4. **export** → `family_offices_50.csv` + provenance; enforce 50 count + 35% gate  
5. **build_index** → LangChain FAISS under `data/index/`  

Manual spot-checks and judgment notes are allowed. Manual record-by-record CSV compilation is not.

## Micro-RAG + product

- Chunk each shipped record into LangChain `Document`s: **entity** (+ **principal** / **signal** when present)  
- Embeddings: OpenAI `text-embedding-3-small` (**paid — disclosed**)  
- Index: LangChain FAISS (`python -m pipeline.build_index`) — **124** documents / **50** firms after final rename pass  
- Orchestration: **LangGraph** bounded graph `retrieve → ground → generate|decline` (not a multi-agent swarm)  
- Retrieval: semantic top-k + optional structural filters (`fo_type` / country cues from query)  
- **Grounding control (working gate):** relevance score + distance thresholds; fail → readable decline — not prompt-only  
- Answer LLM: OpenAI `gpt-4o-mini` over retrieved context only  
- Customer UI: **Next.js** — IR user opens live URL, asks a question, reads prose (success or decline) without decoding pipeline vocabulary  
- API: FastAPI — `/health`, `/search`, `/ask`  
- Deploy: **GCP Cloud Run** — `fo-intel-api` + `fo-intel-web`  

## Stack summary

| Layer | Choice |
|-------|--------|
| Pipeline | Python 3.11+ (`pipeline/`) |
| API | FastAPI (`api/`) |
| Customer UI | Next.js (`web/`) |
| RAG primitives | LangChain Documents / OpenAIEmbeddings / FAISS |
| Orchestration | LangGraph (retrieve → ground → answer\|decline) |
| Embeddings | OpenAI `text-embedding-3-small` |
| Answer LLM | OpenAI `gpt-4o-mini` |
| Hosting | GCP Cloud Run |
| Repo | https://github.com/Atif1299/fo-intel-differentiator |

## Paid tooling disclosure

Assessment allows paid tools if owned as a design decision. We use OpenAI + Cloud Run for retrieval quality and a production-shaped customer UI.

## Out of scope (assessment discipline)

- Full commercial CRM  
- Paid lead databases as primary discovery or FO-type proof  
- Localhost-only or notebook-only demos  
- One-source bulk copy of a public FO list  
- Multi-agent theater on a 50-row corpus  
- Inventing contacts or FO types to fill cells  
