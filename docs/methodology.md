# Methodology summary (Stage 1 deliverable)

Covers: how records were found, how they were enriched, how AI output was validated, which source classes support which claims, and material blind spots that remained.

Artifacts that must reconcile with this note: `data/raw/discovery_stats.json`, `data/processed/enrich_stats.json`, `data/processed/validate_stats.json`, `data/export/export_stats.json`, `data/export/family_offices_50.csv`, `data/export/provenance.jsonl`.

## Observed vs assumed (method level)

| | |
|--|--|
| **Observed** | Multi-adapter discovery produced 261 unique candidates; post-sample-audit validate/export produced exactly 50 unique firms; max primary share **24%** RSS; answer eval **10/10** local/live (incl. multi-firm lists). |
| **Assumed** | Public web + filings + news are enough to *find* many real FOs; Class C site language is enough to *prove* FO type for inclusion when validator gates pass. |
| **Could be wrong if** | Site marketing mimics FO language without being an FO entity; or discovery systematically misses opaque SFOs with no web footprint. |
| **What would change the conclusion** | Sample audit by Falcon finding misclassified FO types, or primary discovery share >35% after recompute. |

## How the system found Family Office records

Stage: `python -m pipeline.discover` → `data/raw/candidates.jsonl`.

Discovery and proof stay separate. Phase 1 does **not** claim FO-type verification.

### Discovery classes used

| Class | Adapters (source ids) | Job |
|-------|----------------------|-----|
| A | DuckDuckGo geo/query set (`ddg:*`), SEC EDGAR full-text (`edgar:full_text_fo`), Google News RSS (`rss:google_news_fo`) | Find candidate names via search / filings / headlines |
| B | Wikipedia FO-adjacent (`wiki:list_family_offices`), SWFI/public profile HTML (`swfi:fo_profiles`) | Structured/public list-style seeds |

### Volumes (Phase 1)

- Unique candidates after merge: **261**  
- Distinct `discovery_source_ids`: **21**  
- By primary class: A **213**, B **48**  
- Largest primary share in candidate pool: RSS ≈ **24.9%** (soft discovery gate 50%)  
- Stats: `data/raw/discovery_stats.json`

### Deduping

Merge on `name_normalized` (suffix-stripped). Multiple adapters can credit the same firm via merged `discovery_source_ids`.

## How records were enriched

Stage: `python -m pipeline.enrich` → `data/processed/enriched.jsonl`.

1. **Prefilter** — drop junk / generic FO phrases → `data/audit/enrich_dropped.jsonl`  
2. **Rank** — prefer “family office” in name, multi-source discovery, website hint; process toward a shippable pool  
3. **Resolve website** — if missing/weak: DuckDuckGo `"{name}" family office official site` (`ddg_site_resolve`)  
4. **Fetch Class C** — httpx + BeautifulSoup on homepage/about + discovery URLs  
5. **OpenAI classify + extract** — `gpt-4o-mini` JSON: `fo_type`, `inclusion_pass` (DESIGN Rule 2), quote-level evidence, extractable fields only; else blank + `could_not_verify`

Per high-value cell: `{value, sources, method, status, checked_at}`. Contacts are never invented as verified.

### Volumes (enriched pool — `enrich_stats.json`)

- Processed ≈ **248** rows in final enrich/hygiene-fill mode  
- `fo_type` mix in pool: SFO **57**, MFO **28**, unknown **163**  
- `inclusion_pass=true`: **83** (quality over fake volume)  

## How AI output was validated

Stages: `python -m pipeline.validate` → `validated.jsonl` + `rejected.jsonl`; then `python -m pipeline.export` → exactly 50.

### Validation layer (deterministic — not a second LLM for inclusion)

1. `inclusion_pass` must be true  
2. `fo_type` must be SFO or MFO (`unknown_type` never ships)  
3. Non-empty `inclusion_evidence_summary`  
4. At least one `proof_urls` or Class-C `proof_source_ids`  
5. Dedupe on normalized name and institutional website domain (news/directory hosts ignored for identity)  
6. Entity hygiene: refuse report crumbs, denylist hubs, category-only names, geo crumbs without firm domains  
7. Rule 1 contact governance: verified email/phone without usable sources → blanked to `could_not_verify` (detail in audit)

### Export gates

- Exactly **50** rows in `data/export/family_offices_50.csv`  
- Sidecar `data/export/provenance.jsonl`  
- Primary discovery source share ≤ **35%**  
- **Shipped:** SFO **29** / MFO **21**; max primary share **24%** = `rss:google_news_fo` (`export_stats.json`)  

### Volumes (validate — `validate_stats.json`)

- Input enriched **266** → passed **50** / rejected **216**  
- Reject codes include brand near-dupes, denylisted network/platform rows, and inclusion failures  

### Sample-audit scrub (pre-submit)

Dropped / refused before final ship:

- Duplicate brand rows (second **Cresset**, second **Farther**)  
- **Global Family Office** (tfoa.info peer network — not an FO entity)  
- **(QP) Global** as clean SFO (multi-family platform language)  
- **Dakota** (dakota.com allocator intel ≠ FO entity)  
- **Family Office in London** (weak FO-services marketing vs entity bar)  

Coerced: **Alpha Capital Family Office** SFO → MFO (outsourced / multiple families).  

Fill to 50: six disclosed **manual spot-checks** (ICONIQ, Pathstone, Clearstead, Hillspire, Thiel Capital, MSD Partners) where automated classify returned `unknown_type` but public FO identity is clear — method `manual_spotcheck` in provenance.  

### Shipped actionability (honest fill rates)

Counted on `family_offices_50.csv` after renames:

| Field | Filled / 50 |
|-------|-------------|
| principal_name | 29 |
| principal_email | 10 |
| principal_phone | 10 |
| principal_linkedin | 2 |
| signal_1_summary | 34 |
| signal_1_date | 18 |
| website | 40 |
| investment_thesis | 22 |

Blanks are intentional candor where Rule 1 could not be met — not guesses labeled verified.

Three full chains: `docs/validation_chains.md` (Matter / ckandcompany / Westerman Capital).

## Source classes → claim types

| Claim type | Allowed source classes |
|------------|------------------------|
| Existence / candidate | A, B |
| FO type (inclusion) | C (+ corroboration); list membership alone does not ship |
| Principal / contact | D |
| Signals | E |

## Material blind spots that remained

- Large reject volume is expected: news/EDGAR/list noise fails Rule 2 or dedupe  
- Opaque SFOs with no web footprint remain systematically under-discovered  
- Wiki adapter added little unique after merge  
- Geography skew toward US English web/news  
- Contact density is still sparse (10 emails / 10 phones) — candid, not sellable as a dense dialer file  
- Directory-only evidence (e.g. Altss) may ship with blank website — weaker corroboration; disclosed  
- Six fill rows used disclosed `manual_spotcheck` where OpenAI returned `unknown_type` — human judgment visible in provenance  
- RSS remains the largest single primary share (**24%**) — under gate, but still the main concentration risk  
- Answer-layer grounding is score-thresholded on this 50-row corpus; re-tune if the file changes materially  

## What this methodology refuses

- Shipping `unknown_type` as FO  
- Relabeling MFO → SFO for “prize” optics  
- Inventing contacts  
- Treating one discovery source as the market  
- Letting validation findings sit unused while customer cells stay “verified”  
