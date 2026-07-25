# Task 2 — SaaS Conversion Analysis

**Prompt:** A SaaS platform focused on providing Family Office Intelligence to a targeted audience is only converting 3% of free accounts to paying users. The SaaS platform founders want to increase MRR. To that end, how would you improve this free trial to paid conversion rate?

## Observed vs assumed

**Observed (only what the prompt gives):**
- Product category: Family Office intelligence SaaS
- Free → paid conversion ≈ **3%**
- Goal: increase **MRR** (not vanity signups)

**Assumed / unknown (not in the prompt):**
- Price point, packaging (seat vs firm), contract length
- Who the free user is (analyst, IR, fund associate, consultant)
- What “free” unlocks (query caps, record caps, export, contacts)
- Activation definition (first search? first saved list? first export?)
- Sales-assist vs pure PLG; CRM handoff
- Whether 3% is trial-end conversion or ever-paid among all free accounts

I treat the rest as **hypotheses to test**, not facts.

## What is missing / what we would investigate

Instrument (or pull) a funnel with timestamps:

1. Signup  
2. First natural-language query / search  
3. First view of a firm with **reachable principal or dated signal**  
4. Save / export / share attempt  
5. Paywall hit (what they tried to unlock)  
6. Paid (and cohort retention at day 30)

Also segment by: persona, firm type of interest (SFO vs MFO), geography, and whether they ever saw a blank contact field on a high-intent record.

Without that, any “improve conversion” plan is consulting noise.

## Hypotheses (falsifiable)

1. **Value is invisible before paywall.** Free users get entity names and FO type, but the cells that justify payment (principal email/phone, fresh signals, export) stay locked or empty — so they never feel product value.  
   *Falsify if:* users who see ≥1 filled principal + dated signal convert at similar rates to those who do not.

2. **Free answers enough.** Grounded Q&A on a small public-ish set satisfies curiosity; paid adds little incremental actionability.  
   *Falsify if:* paywall events cluster on export/contact unlock, not on “more answers.”

3. **Wrong free ICP.** Signups are students/curious browsers, not IR/BD operators with outreach workflows.  
   *Falsify if:* work-email / fund-domain cohorts convert near peers while consumer emails drag the average to 3%.

4. **Trust failure.** Users distrust FO-type labels or contacts (Rule 2 risk), so they will not pay for a file they would not act on.  
   *Falsify if:* conversion is flat across high- vs low-confidence records and after showing provenance.

5. **Activation never happens.** Many free accounts never complete a second session.  
   *Falsify if:* activated users (2+ sessions + 1 save) already convert ≫3% and volume of activated users is the bottleneck.

## Recommended moves (priority order)

Tied to what this product actually is (FO intel with sparse contacts and strong type/evidence cells):

1. **Redefine free around an “actionable moment.”** Free must deliver *one* complete loop: find a relevant FO → see why-now signal → see a reachable next step (principal LinkedIn or verified email) **or** an honest “could not verify — here is the firm site.” Paying for denser coverage / export / alerts comes after that moment, not before it.

2. **Paywall the workflow, not the first insight.** Charge for: bulk export, monitoring alerts, CRM push, team seats, deeper contact enrichment. Do not charge for the first grounded answer if that is the only proof the system works.

3. **Instrument and kill fake demand.** Require work email or firm domain for free tier if consumer noise dominates; measure conversion by ICP cohort before celebrating signup growth.

4. **Make uncertainty a product feature.** Show provenance and blank rates honestly. IR buyers punish invented contacts harder than blanks. Conversion lifts from trust compound; from fake density they reverse when outreach bounces.

5. **Sales-assist the high-intent 10%.** When a free user repeatedly queries SFO + geo + “contact,” route to a human with a short evidence pack — PLG alone may not monetize opaque markets.

## What could be wrong / what would change the conclusion

- If 3% is already best-in-class for this ACV and the real problem is top-of-funnel quality, optimizing the trial UI is wasted motion.  
- If the product’s paid tier is undifferentiated from free (same blanks), packaging changes beat growth hacks.  
- If legal/compliance limits contact data, the conversion lever is **signals + workflow**, not email density.

## Explicit non-answers

- I will not claim “X% lift from onboarding emails” without funnel data.  
- I will not prescribe a price.  
- I will not recommend buying a contact database as the primary FO-type proof (that fails the same sourcing discipline this assessment enforces).
