# Phase 1 POC report (forced-choice)

Model: `qwen3.8:27b-mlx` | personas: 20 | variants: 5

**Hypothesis:** Outcome-led wording that names a SPECIFIC, verifiable result (a number) converts better than feature-led wording, and better than the same outcome stated vaguely, especially among skeptical, price-sensitive people. Urgency/scarcity wording will backfire with skeptics.

## Overall (mean rank: 1=best; click share = picked as THE ad to click)

| variant | mean rank r1 | mean rank after peers | click share r1 | click share after peers | mean interest after peers |
|---|---|---|---|---|---|
| A_feature | 2 | 1.85 | 35% | 20% | 2.35 |
| B_outcome | 2.8 | 2.75 | 0% | 0% | 1.6 |
| B2_outcome_number | 1.65 | 1.7 | 15% | 15% | 1.95 |
| C_social | 3.55 | 3.7 | 0% | 0% | 1.5 |
| D_urgency | 5 | 5 | 0% | 0% | 1 |
| *(clicks none)* | | | 50% | 65% | |

## Mean rank after peers, by segment (lower is better)

| segment | A_feature | B_outcome | B2_outcome_number | C_social | D_urgency |
|---|---|---|---|---|---|
| skeptical_budget | 2.2 | 2.4 | 1.8 | 3.6 | 5 |
| busy_parent | 1.4 | 2.8 | 2 | 3.8 | 5 |
| eco_idealist | 1.6 | 2.8 | 1.6 | 4 | 5 |
| tech_enthusiast | 2.2 | 3 | 1.4 | 3.4 | 5 |

## Click share after peers, by segment

| segment | A_feature | B_outcome | B2_outcome_number | C_social | D_urgency | none |
|---|---|---|---|---|---|---|
| skeptical_budget | 20% | 0% | 0% | 0% | 0% | 80% |
| busy_parent | 20% | 0% | 0% | 0% | 0% | 80% |
| eco_idealist | 0% | 0% | 20% | 0% | 0% | 80% |
| tech_enthusiast | 40% | 0% | 40% | 0% | 0% | 20% |

## Why people ranked each variant last (round 1 objection from a persona who ranked it 4th)

- **D_urgency** / Noor Haddad (skeptical_budget): "Every single ad screams 'subscription trap' with phrases like 'founding member pricing' and '14 days free,' which immediately triggers my PTSD from that streaming service bill; I don't care about 'beta households' or 'founding members' when I'm trying to make $180 last a month. I would ignore all of them because none of them offer a free, ad-supported version, and the 'camera scan' feature sounds like a privacy nightmare for a studio renter who just wants to know what to cook with the eggs and spinach I already have."
- **D_urgency** / Callum Reid (skeptical_budget): "The emotional manipulation and urgency in Ad 3 are instant red flags that I would block, while Ad 4's dry, feature-focused list is the only one that respects my intelligence by explaining the actual utility without the fluff. Even then, the $9/month price tag is a non-starter for me since I can build a similar script in an afternoon, but I'd at least read the specs to see if the camera recognition is actually good."

## Verdict

**Round 1 (independent)**
- Numeric outcome ranks better than feature by >= 0.3: B2=1.65 vs A=2 -> **PASS**
- Numeric outcome ranks better than vague outcome by >= 0.3: B2=1.65 vs B=2.8 -> **PASS**
- Urgency ranks worse than numeric outcome for skeptics: D=5 vs B2=1.8 -> **PASS**
- Hypothesis SUPPORTED (round 1 (independent), n=20; rank gaps under ~0.4 are noise).

**After peers (social influence)**
- Numeric outcome ranks better than feature by >= 0.3: B2=1.7 vs A=1.85 -> **FAIL**
- Numeric outcome ranks better than vague outcome by >= 0.3: B2=1.7 vs B=2.75 -> **PASS**
- Urgency ranks worse than numeric outcome for skeptics: D=5 vs B2=1.8 -> **PASS**
- Hypothesis NOT SUPPORTED (after peers (social influence), n=20; rank gaps under ~0.4 are noise).

> Synthetic personas are a cheap filter for wording, not evidence of real-world conversion. The 31% figure in the seed is an illustrative sample number. Validate winners with a real A/B test.