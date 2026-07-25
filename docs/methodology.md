# Methodology summary (Stage 1 deliverable)

## How the system found Family Office records

Pipeline stage: `python -m pipeline.discover` → `data/raw/candidates.jsonl`.

### Discovery classes used

| Class | Adapters | Role |
|-------|----------|------|
| A | DuckDuckGo geo/query set (`ddg:*`), SEC EDGAR full-text (`edgar:full_text_fo`), Google News RSS (`rss:google_news_fo`) | Find candidate names via search / filings / headlines |
| B | Wikipedia FO-adjacent pages (`wiki:list_family_offices`), SWFI/public profile HTML (`swfi:fo_profiles`) | Structured/public list-style seeds |

Discovery and proof stay separate: Phase 1 does **not** claim FO-type verification (Class C is Phase 2).

Paid stack (disclosed): OpenAI embeddings/LLM + Next.js UI on GCP Cloud Run for the product layer; Python remains the system of record for producing the 50.

### Volumes (Phase 1 run)

- Unique candidates after merge: **261**
- Distinct `discovery_source_ids`: **21**
- By class (primary label): A **213**, B **48**
- Largest primary source share: RSS ≈ **24.9%** (under discovery soft gate of 50%; final 50 still capped at ≤35% per source at export)
- Stats artifact: `data/raw/discovery_stats.json`

### Deduping

Candidates merge on `name_normalized` (suffix-stripped). Multiple adapters credit the same firm via merged `discovery_source_ids`.

## How records were enriched

Pipeline stage: `python -m pipeline.enrich` → `data/processed/enriched.jsonl` + `enrich_stats.json`.

### Steps

1. **Prefilter** — drop junk / generic FO phrases; drops logged to `data/audit/enrich_dropped.jsonl`
2. **Rank** — prioritize “family office” in name, multi-source discovery, website hint, discovery URLs; cap **120**
3. **Resolve website** — if missing/weak: DuckDuckGo `"{name}" family office official site` (`method=ddg_site_resolve`)
4. **Fetch Class C** — httpx + BeautifulSoup on homepage/about + discovery URLs; truncated text corpus
5. **OpenAI classify + extract** — `gpt-4o-mini` JSON mode: `fo_type`, `inclusion_pass` (DESIGN Rule 2), quote-level evidence, extractable fields only; else blank + `could_not_verify`

### Volumes (Phase 2 + resume)

- Initial enrich budget **120** → then `python -m pipeline.enrich --resume` until shippable SFO+MFO ≥ **80**
- Final enriched rows: **234** (`enrich_stats.json`)
- Final `fo_type` mix (enriched pool): SFO **54**, MFO **28**, unknown **152**
- `inclusion_pass=true`: **80** (quality over fake volume)

Per high-value cell: `{value, sources, method, status, checked_at}`. Contacts are never invented as verified.

## How AI output was validated

Pipeline stages: `python -m pipeline.validate` → `validated.jsonl` + `rejected.jsonl`; then `python -m pipeline.export` → exactly 50.

### Validation layer (separate from enrich)

Deterministic gates — no second LLM for inclusion:

1. `inclusion_pass` must be true  
2. `fo_type` must be SFO or MFO (`unknown_type` never ships)  
3. Non-empty `inclusion_evidence_summary`  
4. At least one `proof_urls` or Class-C `proof_source_ids`  
5. Dedupe on normalized name and institutional website domain (news/directory hosts ignored for identity)  
6. Rule 1 contact governance: verified email/phone without usable sources → blanked to `could_not_verify` (detail in audit)

### Export gates

- Exactly **50** rows in `data/export/family_offices_50.csv`  
- Sidecar `data/export/provenance.jsonl`  
- Primary discovery source share ≤ **35%** (observed max **24%** = `rss:google_news_fo`)  
- Shipped mix: SFO **32**, MFO **18** (≥15 SFO target met without relabeling)

### Volumes (Phase 3 run)

- Validated pass **51** / reject **183** (`validate_stats.json`)  
- Exported **50** (`export_stats.json`)  
- Three full chains: `docs/validation_chains.md`

## Source classes → claim types

| Claim type | Allowed source classes |
|------------|------------------------|
| Existence / candidate | A, B |
| FO type (inclusion) | C (+ corroboration) |
| Principal / contact | D |
| Signals | E |

## Material blind spots that remained

- Large reject volume is expected: news/EDGAR/list noise fails Rule 2 or dedupe  
- Enrich resume stopped at shippable **80**; some kept candidates remain un-checked  
- Class B / RSS discovery still needs Class C proof — list membership alone does not ship  
- Wiki adapter contributed little unique after merge  
- Geography skew toward US English web/news  
- Many shipped rows still lack principal email/phone (honest blanks)  
- A few RSS-discovered names resolve to news/article hosts rather than pristine corporate homes — validator + export still require FO evidence text
