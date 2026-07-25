# Validation chains (3 records)

Selected from pipeline export `data/export/family_offices_50.csv` (not hand-picked into the CSV — only documented here after export).

## Record 1 — `fo_id`: `matter-family-office-8dd64fb0e1`

**Firm:** Matter Family Office (`multi_family_office`)  
**Confidence:** 0.9

1. **Discovery source**  
   Class A. Primary `ddg:fo_denver`, also `ddg:extra_midwest`. Discovery URLs included LinkedIn company page and team page on matterfamilyoffice.com.

2. **Extraction method**  
   Name/snippet from DuckDuckGo HTML results; URLs carried on the candidate; merged multi-source ids at discovery.

3. **Enrichment steps**  
   Website already institutional → Class C fetch of homepage + discovery URLs → `gpt-4o-mini` JSON classify/extract. Self-description as multifamily office with integrated FO services.

4. **Validation logic**  
   `inclusion_pass=true`; `fo_type` shippable; non-empty inclusion evidence; proof URLs present (`class_c_fetch`, `fo_website`); no name/domain duplicate vs higher-confidence row; contact fields left blank or provenance-backed (principal Katherine Lintz retained from page extract).

5. **Confidence assessment**  
   High: firm site language matches MFO inclusion bar; discovery ≠ sole proof.

6. **Exact sources / links**  
   - https://www.matterfamilyoffice.com/  
   - https://www.matterfamilyoffice.com/the-matter-team/  
   - https://ca.linkedin.com/company/matter-family-office  

---

## Record 2 — `fo_id`: `ckandcompany-family-office-b8ceadc621`

**Firm:** ckandcompany Family Office (`single_family_office`)  
**Confidence:** 1.0

1. **Discovery source**  
   Class A. `ddg:sfo_sf`. Discovery URL: careers/research-analyst posting describing the firm as a family office.

2. **Extraction method**  
   DDG title/URL/snippet → candidate name + URL.

3. **Enrichment steps**  
   Site resolve/fetch of ckandcomp.com career page (+ about) → OpenAI extract. Explicit single-family office language; invests for charitable/other family-associated organizations.

4. **Validation logic**  
   Passed Rule 2 (affirmative FO entity language on own site materials); Rule 1 provenance on filled cells; no duplicate name/domain; shipped as SFO without relabel.

5. **Confidence assessment**  
   High for FO type from primary site text; principal/email blank (honest `could_not_verify`).

6. **Exact sources / links**  
   - https://www.ckandcomp.com  
   - https://www.ckandcomp.com/research-analyst-family-office-sf  

---

## Record 3 — `fo_id`: `venture-capital-3783a3b103`

**Firm:** Westerman Capital (`single_family_office`)  
**Confidence:** 1.0

1. **Discovery source**  
   Class B. `swfi:fo_profiles` (public SWFI/HTML list seed — discovery only).

2. **Extraction method**  
   HTML list/profile parse → candidate name + outbound URL hints.

3. **Enrichment steps**  
   Class C fetch of https://westermancapital.com/ → OpenAI classify. Mission text: manage interests of the Westerman Family → treated as SFO entity context (not “FO services” marketing alone).

4. **Validation logic**  
   Inclusion evidence + proof URLs required; Class B discovery alone would not ship — Class C site proof required and present; dedupe cleared; contacts blank if unverified.

5. **Confidence assessment**  
   High for inclusion given own-site family-wealth entity framing; secondary fields sparse (expected opacity).

6. **Exact sources / links**  
   - https://westermancapital.com/  
   - Discovery seed: SWFI/public FO profile scrape (`swfi:fo_profiles`) — list used only to find the name, not as sole FO-type proof.

### Observed vs assumed (shared)

| Claim | Status |
|-------|--------|
| Firm is an FO entity of stated type | Verified via Class C page text + validator gates |
| Discovery source mix on final 50 | Verified in `export_stats.json` (max primary share 24% RSS) |
| Email/phone reachability | Not claimed; blanked when provenance insufficient |
