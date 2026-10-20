# campaign-sandbox

Test ad copy on a swarm of synthetic shoppers, fully local with Ollama. Swap in any product, get ranked wording and segment-level results.

![Simulation of six Thanksgiving ads for the HP Victus 15](docs/img/hp-thanksgiving-simulation.gif)

Campaign Sandbox simulates how different audience segments react to competing ad wordings before you spend on a real A/B test.
Drop a product brief, a set of ad variants and your audience segments into a project folder. A local LLM turns the brief into a
fact graph, writes personas, has each one rank the ads, lets them read peers' reactions and rank again, then reports which wording
wins for whom. No cloud APIs. Nothing leaves your machine.

Inspired by [MiroFish](https://github.com/666ghj/MiroFish) and [MiroFish-Offline](https://github.com/nikmcfly/MiroFish-Offline).
It is a small, separate implementation, not a fork.

**Read the write-up:** [`docs/medium-article.md`](docs/medium-article.md): 20 shoppers, six HP Victus 15 Thanksgiving ads, and why the result needs a caveat.

## What the HP example found

Project: `hp_victus_thanksgiving`. 20 personas, 4 segments, 6 ads, 2 rounds, `qwen3.8:27b-mlx`. Average position after peers (1 = best):

| Ad | Avg position | Ranked first by |
|---|---|---|
| Candid trade-offs | 1.65 | 13 of 20 |
| Upgradeable | 2.25 | 3 |
| Gift framing | 3.05 | 3 |
| Spec sheet (control) | 4.00 | 0 |
| Measured proof | 4.20 | 1 |
| Urgency | 5.85 | 0 (last for 17 of 20) |

The same ad wins or loses by audience: "Measured proof" averages 2.8 with competitive enthusiasts and 5.0 with parents buying a gift.
Full report: [`out/hp_victus_thanksgiving/report.md`](out/hp_victus_thanksgiving/report.md).

**Read this with care.** The personas are language-model output. In round 1, 16 of 20 used honesty language ("respects my intelligence")
to justify their pick, so this model likely over-rewards candor and under-rewards urgency compared with real shoppers.
The **$799 price and the 26-30 Nov 2026 offer window are assumptions**, not an HP offer. Treat results as hypotheses to test with a real A/B test.

## Quick start

Requirements: Python 3.9+, [Ollama](https://ollama.com) running with a chat model. `Pillow` is needed only for the animation.

```bash
ollama pull qwen3.8:27b-mlx              # or any chat model; set POC_MODEL to override
cp -r projects/hp_victus_thanksgiving projects/my_product
# edit project.json, product.md, campaigns.json, segments.json
python3 check_project.py my_product                       # validate before spending model time
python3 -u poc.py my_product 5 > out/my_product/run.log   # graph -> personas -> 2 rounds -> report (5 personas per segment)
python3 make_ui.py my_product                             # out/my_product/ui.html, a MiroFish-style console
python3 make_motion.py my_product                         # out/my_product/motion.gif (needs Pillow)
```

`python3 poc.py <project> --report` rebuilds the report from a saved run. Model calls are cached in `out/cache/`, so reruns are free.

## A project is four files

| File | What it holds |
|---|---|
| `project.json` | title, the scenario shown to personas (`{n}` = number of ads), scale wording, extra persona fields |
| `product.md` | the product brief, the only source of facts personas may rely on. Mark guesses `ASSUMED` |
| `campaigns.json` | hypothesis, ad variants (`label` + `text`), success tests |
| `segments.json` | audience segments and the life situations assigned to each persona |

A success test is data. `better` must out-rank `worse` by at least `by` places, overall or within one segment:

```json
{ "label": "Gift framing beats the spec sheet with parents",
  "better": "D_gift", "worse": "A_spec_sheet", "by": 0.3, "segment": "parent_gift_buyer" }
```

Included projects: `hp_victus_thanksgiving` (real product research, two assumptions flagged) and `pantrypilot` (a made-up product used as a dummy).

## How it works

1. **Graph.** The brief becomes entities, relations and a list of checkable facts, with numbers kept. Personas see only that fact list.
2. **Personas.** N per segment, each with a code-assigned name and life situation so they do not collapse into copies of each other.
3. **Round 1.** Each persona sees every ad (shuffled and neutrally numbered per persona), ranks them, picks one to click or none.
4. **Round 2.** Each persona reads three peers' reactions, translated into their own ad numbering, and ranks again.
5. **Report.** Mean position per ad and segment, first-choice shares, and a pass/fail per success test.

## Layout

```text
poc.py            simulation: graph, personas, rounds, report
check_project.py  pre-flight validation; flags ad numbers missing from the brief
make_ui.py        console page (graph, steps, report, persona replay)
make_motion.py    animated GIF and stills from a saved run
llm.py            tiny stdlib Ollama client with on-disk caching
projects/         one folder per product
out/<project>/    graph, personas, results, report, console, animation
docs/             article and its images
```

## Known limits and next steps

- Synthetic shoppers are a cheap filter for wording, not evidence of real conversion.
- Persona prompts say "be blunt, most advertising is ignored", which probably biases toward skepticism. Add a deal-heavy control and soften it.
- The `pantrypilot` example output was produced before two fixes (peer quotes used the wrong ad numbers in round 2; the fact list dropped numbers). Rerun it before relying on it.
- Phase 2: feed the brief from competitor intelligence (for example the playbook teardown described in [this article](https://praveenjoshi007.medium.com/i-built-an-ai-that-reverse-engineers-your-competitors-entire-marketing-playbook-in-one-click-537f77f6b2dc)).
- Possible move to MiroFish-Offline (Neo4j and OASIS) once multi-round social dynamics matter.
