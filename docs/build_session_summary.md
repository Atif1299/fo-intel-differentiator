# Build session summary

Keep under half a page. (Stage 1 deliverable.)

1. **Approximate build time:** ~14–16 hours of actual working time across 25 Jul 2026 (PKT), inside the 48h Stage 1 window — not continuous coding. Not padded.

2. **Main work sessions:**
   - Design lock (Rule 1/2, ≤35% discovery, SFO preference) + multi-source discovery (261 candidates)  
   - Enrich / FO classify (OpenAI) + validate / export exactly 50 + provenance  
   - LangGraph Micro-RAG + Next.js customer UI + Cloud Run live URL + answer eval  
   - Self-eval hygiene (refuse non-entity crumbs) + on-site geo-name pass + Task 2 / submission docs  

3. **Major components — AI produced vs human changed/decided:**
   - **Pipeline:** AI drafted adapters and orchestrators; human locked DESIGN rules (discovery ≠ proof, ≤35% gate, never relabel MFO→SFO, validation must govern release).  
   - **Dataset / validation:** AI enriched/classified; human required entity-hygiene rejects, honest blanks over invented contacts, re-export after self-audit, and on-site renames only when corroborated.  
   - **RAG / UI:** AI implemented LangChain FAISS + LangGraph ground gate + Next.js; human insisted on a real grounding control (not prompt-only), Cloud Run over localhost, and IR-readable declines.  
   - **Task 2:** Structured as observed vs assumed; refused guaranteed conversion lift without funnel data.  
