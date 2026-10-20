"""Test campaign wording against a small synthetic audience, 100% local (Ollama).

Everything product-specific lives in projects/<name>/ so a new product is a new folder, not a code change:
  project.json    title, scenario shown to personas, scale wording, extra persona fields
  product.md      the product brief (the only source of facts personas may rely on)
  campaigns.json  hypothesis, ad variants, success criteria
  segments.json   audience segments (and the life situations assigned to each persona)

Pipeline (a miniature of MiroFish's seed -> graph -> personas -> simulate -> report loop):
  1. graph    : LLM turns product.md into entities, relations and checkable facts -> out/<name>/graph.json
  2. personas : LLM writes N personas per segment                                 -> out/<name>/personas.json
  3. round 1  : each persona sees all ads (shuffled, neutrally numbered), ranks them, picks one to click
  4. round 2  : each persona reads three peers' reactions, then ranks again (social influence)
  5. report   : mean rank per ad / segment and a verdict per success criterion    -> out/<name>/report.md

usage: python3 -u poc.py <project> [personas_per_segment]
"""
from __future__ import annotations

import json
import random
import re
import statistics as st
import sys
import zlib
from pathlib import Path

from llm import MODEL, chat

ROOT = Path(__file__).parent

NAMES = ["Gerald Pendergast", "Lena Ortiz", "Tomasz Kowalski", "Aisha Rahman", "Wei Zhang", "Fatima Al-Sayed", "Brendan O'Connor",
         "Yuki Tanaka", "Ngozi Okafor", "Carlos Mendes", "Ingrid Larsen", "Dmitri Volkov", "Kavita Menon", "Hassan Qureshi",
         "Maria Santos", "Jamal Washington", "Sofia Rinaldi", "Olumide Adeyemi", "Hannah Bergstrom", "Rafael Castillo",
         "Mei-Ling Chua", "Patrick Dunne", "Zainab Yusuf", "Anders Nilsson", "Camila Ferreira", "Idris Mahmoud", "Beatrix Holloway",
         "Arjun Patel", "Noor Haddad", "Callum Reid", "Esperanza Cruz", "Takumi Sato", "Linnea Berg", "Ravi Subramanian", "Marguerite Dubois",
         "Darnell Brooks", "Soo-jin Park", "Elias Haddad", "Tamsin Whitlock", "Oluwaseun Bello", "Greta Hoffmann", "Miguel Alvarado"]

DEFAULT_SYSTEM = "You simulate realistic consumers. Be honest and blunt; most advertising is ignored or disliked."
DEFAULT_SCALE = ("interest scale: 1=none, 2=slight, 3=moderate (would read more), 4=strong (would try it), 5=would act right now. "
                 "Use the range and differentiate between the ads. If truly none appeal, click=\"none\".")


class Project:
    def __init__(self, name: str):
        self.name = name
        d = ROOT / "projects" / name
        if not d.is_dir():
            raise SystemExit(f"no such project: {d}")
        self.meta = json.loads((d / "project.json").read_text())
        self.cfg = json.loads((d / "campaigns.json").read_text())
        self.segments = json.loads((d / "segments.json").read_text())
        self.product = (d / "product.md").read_text()
        self.out = ROOT / "out" / name
        self.out.mkdir(parents=True, exist_ok=True)
        self.texts = {v: x["text"] for v, x in self.cfg["variants"].items()}
        self.labels = {v: x["label"] for v, x in self.cfg["variants"].items()}
        self.seg_names = {s["id"]: s["name"] for s in self.segments}
        self.system = self.meta.get("system", DEFAULT_SYSTEM)
        self.scale = self.meta.get("scale", DEFAULT_SCALE)


# ---------- 1. graph ----------
def build_graph(pr: Project) -> dict:
    g = chat(
        "Extract a knowledge graph from this product brief. Return JSON: "
        '{"nodes":[{"id":str,"type":"product|feature|claim|audience|price|limitation"}],'
        '"edges":[{"src":str,"rel":str,"dst":str}],'
        '"facts":["short sentence per checkable fact, KEEPING every number, price, spec and limitation"]}. '
        "Mark claims that lack evidence in the brief with type 'claim' and include limitations explicitly.\n\n" + pr.product,
        system="You extract knowledge graphs. Output JSON only.", temperature=0.2, max_tokens=3500)
    (pr.out / "graph.json").write_text(json.dumps(g, indent=2))
    return g


def graph_facts(g: dict) -> str:
    facts = g.get("facts") or [f"{e['src']} {e['rel']} {e['dst']}" for e in g.get("edges", [])]
    return "\n".join(f"- {f}" for f in facts)


# ---------- 2. personas ----------
def make_personas(pr: Project, per_segment: int) -> list:
    rng = random.Random(zlib.crc32(pr.name.encode()))
    names = NAMES[:]
    rng.shuffle(names)
    extra = pr.meta.get("persona_fields", {})
    extra_shape = "".join(f'"{k}":"{v}",' for k, v in extra.items())
    people = []
    for seg in pr.segments:
        sits = seg["situations"]
        mine = [(names.pop(), sits[i % len(sits)]) for i in range(per_segment)]
        spec = "\n".join(f"{i + 1}. name: {n}; life situation: {sit}" for i, (n, sit) in enumerate(mine))
        res = chat(
            f"Write {per_segment} realistic consumer personas for the segment '{seg['name']}' ({seg['description']}). "
            f"Use EXACTLY these names and life situations, in order, and make each person's job, means and attitudes different:\n{spec}\n"
            f'Return JSON {{"personas":[{{"name":str,"age":int,"job":str,"household":str,{extra_shape}'
            '"bio":"2 sentences on habits and attitudes to advertising and spending"}]}',
            system=pr.system, temperature=0.8, seed=zlib.crc32(seg["id"].encode()) % 1000, max_tokens=2200)
        got = res["personas"][:per_segment]
        assert len(got) == per_segment, f"{seg['id']}: model returned {len(got)} personas"
        for i, p in enumerate(got):
            p["name"] = mine[i][0]  # enforce uniqueness regardless of what the model wrote
            p["segment"], p["id"] = seg["id"], f"{seg['id']}_{i}"
            people.append(p)
    assert len({p["name"] for p in people}) == len(people)
    (pr.out / "personas.json").write_text(json.dumps(people, indent=2))
    return people


def card(pr: Project, p: dict) -> str:
    extras = " ".join(f"{str(p[k]).rstrip('.')}." for k in pr.meta.get("persona_fields", {}) if p.get(k))
    return f"You are {p['name']}, {p['age']}, {p['job']}. Household: {p['household']}. {extras} {p['bio']}".replace("  ", " ")


def shape(n: int) -> str:
    return ('Reply JSON in this order: {"reasoning":"2 sentences in your own voice comparing the ads","ranking":[ad numbers, best first],'
            '"click":"the ONE ad number you would click, or none","interest":{' + ",".join(f'"{i}":1-5' for i in range(1, n + 1)) +
            '},"top_objection":"your biggest doubt about the ad you ranked first"}')


def _layout(p: dict, variants: dict):
    """Neutral per-persona shuffle: ad numbers 1..n -> variant ids (removes label/order bias)."""
    order = list(variants)
    random.Random(zlib.crc32(p["id"].encode())).shuffle(order)
    return {str(i + 1): v for i, v in enumerate(order)}


def _parse(r: dict, lay: dict) -> dict:
    rank = [lay[str(n)] for n in r.get("ranking", []) if str(n) in lay]
    rank += [v for v in lay.values() if v not in rank]  # fill any gaps
    rank = list(dict.fromkeys(rank))
    click = lay.get(str(r.get("click")).strip().replace("Ad ", ""))
    inter = {lay[k]: max(1, min(5, int(x))) for k, x in r.get("interest", {}).items() if k in lay}
    for v in lay.values():
        inter.setdefault(v, 3)
    return {"ranking": rank, "click": click, "interest": inter,
            "reasoning": r.get("reasoning", ""), "objection": r.get("top_objection", "")}


def relabel(text: str, src_lay: dict, to) -> str:
    """Personas refer to ads by THEIR shuffled numbers ("Ad 3"). Translate those mentions into another numbering or a label."""
    return re.sub(r"\bAd (\d+)\b", lambda m: to(src_lay[m.group(1)]) if m.group(1) in src_lay else m.group(0), text)


def _ads(lay: dict, variants: dict) -> str:
    return "\n".join(f'Ad {n}: "{variants[v]}"' for n, v in lay.items())


# ---------- 3. round 1 ----------
def compare(pr: Project, p: dict, facts: str) -> dict:
    lay = _layout(p, pr.texts)
    scenario = pr.meta["scenario"].format(n=len(pr.texts))
    r = chat(
        f"{card(pr, p)}\n\n{scenario}\n\n{_ads(lay, pr.texts)}\n\nWhat is verifiable about the product:\n{facts}\n\n{pr.scale}\n{shape(len(pr.texts))}",
        system=pr.system, temperature=0.7, seed=zlib.crc32(p["id"].encode()) % 10000, max_tokens=500)
    return _parse(r, lay)


# ---------- 4. round 2 ----------
def social_round(pr: Project, p: dict, r1: dict, people: list, rng: random.Random) -> dict:
    lay = _layout(p, pr.texts)
    inv = {v: n for n, v in lay.items()}
    peers = rng.sample([q for q in people if q["id"] != p["id"]], 3)
    chatter = []
    for q in peers:
        c = r1[q["id"]]["click"]
        pick = f"clicked Ad {inv[c]}" if c else "would click none"
        said = relabel(r1[q["id"]]["reasoning"], _layout(q, pr.texts), lambda v: f"Ad {inv[v]}")  # peer's numbers -> this reader's numbers
        chatter.append(f'{q["name"]} ({pr.seg_names[q["segment"]]}) {pick}: "{said}"')
    mine = f"You first ranked: {', '.join('Ad ' + inv[v] for v in r1[p['id']]['ranking'])}; you would " + \
           (f"click Ad {inv[r1[p['id']]['click']]}." if r1[p['id']]['click'] else "click none.")
    r = chat(
        f"{card(pr, p)}\n\nThe ads:\n{_ads(lay, pr.texts)}\n\n{mine}\n\nThen you read what other people said:\n"
        + "\n".join(chatter) + "\n\nReconsider. Stay true to yourself; change your ranking only if peers genuinely made you think.\n"
        f"{pr.scale}\n{shape(len(pr.texts))}",
        system=pr.system, temperature=0.5, seed=zlib.crc32((p["id"] + "r2").encode()) % 10000, max_tokens=500)
    return _parse(r, lay)


# ---------- 5. report ----------
def mean(xs):
    xs = list(xs)
    return round(st.mean(xs), 2) if xs else float("nan")


def stats(pr: Project, people: list, rnd: dict) -> dict:
    """Mean rank (1 = best) and click share per variant, overall and per segment."""
    out = {}
    for scope in [None] + [s["id"] for s in pr.segments]:
        ps = [p for p in people if scope is None or p["segment"] == scope]
        out[scope or "all"] = {
            "rank": {v: mean(rnd[p["id"]]["ranking"].index(v) + 1 for p in ps) for v in pr.texts},
            "click": {v: round(sum(rnd[p["id"]]["click"] == v for p in ps) / len(ps), 3) for v in pr.texts},
            "none": round(sum(rnd[p["id"]]["click"] is None for p in ps) / len(ps), 3)}
    return out


def evaluate(pr: Project, st_: dict) -> list:
    """Each success criterion: `better` must out-rank `worse` by at least `by` places (overall or within one segment)."""
    res = []
    for c in pr.cfg["success_criteria"]:
        r = st_[c.get("segment") or "all"]["rank"]
        gap = round(r[c["worse"]] - r[c["better"]], 2)
        res.append({"label": c["label"], "pass": gap >= c["by"], "better": c["better"], "worse": c["worse"],
                    "detail": f"{pr.labels[c['better']]} {r[c['better']]} vs {pr.labels[c['worse']]} {r[c['worse']]} (gap {gap}, need {c['by']})"
                              + (f" in {pr.seg_names[c['segment']]}" if c.get("segment") else "")})
    return res


def report(pr: Project, people: list, r1: dict, r2: dict) -> str:
    variants, n = list(pr.texts), len(people)
    s1, s2 = stats(pr, people, r1), stats(pr, people, r2)
    L = [f"# {pr.meta['title']}: simulation report\n", f"Model: `{MODEL}` | personas: {n} | ads: {len(variants)}\n",
         f"**Hypothesis:** {pr.cfg['hypothesis']}\n", "## Overall (mean rank: 1=best; click = picked as THE ad to click)\n",
         "| ad | mean rank r1 | mean rank after peers | click r1 | click after peers |", "|---|---|---|---|---|"]
    for v in sorted(variants, key=lambda v: s2["all"]["rank"][v]):
        L.append(f"| {pr.labels[v]} | {s1['all']['rank'][v]} | {s2['all']['rank'][v]} | {s1['all']['click'][v]:.0%} | {s2['all']['click'][v]:.0%} |")
    L.append(f"| *(clicks none)* | | | {s1['all']['none']:.0%} | {s2['all']['none']:.0%} |")
    L += ["\n## Mean rank after peers, by segment (lower is better)\n", "| segment | " + " | ".join(pr.labels[v] for v in variants) + " |", "|---" * (len(variants) + 1) + "|"]
    for s in pr.segments:
        L.append(f"| {s['name']} | " + " | ".join(str(s2[s["id"]]["rank"][v]) for v in variants) + " |")
    L += ["\n## First choice (would click) after peers, by segment\n", "| segment | " + " | ".join(pr.labels[v] for v in variants) + " | none |", "|---" * (len(variants) + 2) + "|"]
    for s in pr.segments:
        L.append(f"| {s['name']} | " + " | ".join(f"{s2[s['id']]['click'][v]:.0%}" for v in variants) + f" | {s2[s['id']]['none']:.0%} |")
    L.append("\n## Why people ranked each ad last (round 1)\n")
    for v in variants:
        for p in [q for q in people if r1[q["id"]]["ranking"][-1] == v][:2]:
            said = relabel(r1[p["id"]]["reasoning"], _layout(p, pr.texts), lambda x: f'"{pr.labels[x]}"')
            L.append(f"- **{pr.labels[v]}** / {p['name']} ({pr.seg_names[p['segment']]}): \"{said}\"")
    L.append("\n## Verdict\n")
    for label, st_ in (("Round 1 (independent)", s1), ("After peers", s2)):
        ev = evaluate(pr, st_)
        L.append(f"**{label}**")
        L += [f"- {e['label']}: {e['detail']} -> **{'PASS' if e['pass'] else 'FAIL'}**" for e in ev]
        L += [f"- Hypothesis {'SUPPORTED' if all(e['pass'] for e in ev) else 'NOT SUPPORTED'} (n={n}; rank gaps under ~0.4 are noise).", ""]
    L.append("> Synthetic personas are a cheap filter for wording, not evidence of real-world conversion. Validate winners with a real A/B test.")
    text = "\n".join(L)
    (pr.out / "report.md").write_text(text)
    return text


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    pr = Project(sys.argv[1])
    if "--report" in sys.argv:  # rebuild report.md from the saved run
        res = json.loads((pr.out / "results.json").read_text())
        print(report(pr, json.loads((pr.out / "personas.json").read_text()), res["round1"], res["round2"]))
        return
    per_segment = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    rng = random.Random(7)

    print(f"project: {pr.name} | model: {MODEL}")
    print("1/5 graph ..."); facts = graph_facts(build_graph(pr))
    print("2/5 personas ..."); people = make_personas(pr, per_segment)
    print(f"3/5 round 1: {len(people)} personas rank {len(pr.texts)} ads ...")
    r1 = {}
    for p in people:
        r1[p["id"]] = compare(pr, p, facts)
        print(f"   {p['name']:<20} {p['segment']:<24} rank: {' > '.join(v.split('_')[0] for v in r1[p['id']]['ranking'])}  click: {r1[p['id']]['click']}")
    print("4/5 round 2 (peer influence) ...")
    r2 = {}
    for p in people:
        r2[p["id"]] = social_round(pr, p, r1, people, rng)
        print(f"   {p['name']:<20} rank: {' > '.join(v.split('_')[0] for v in r2[p['id']]['ranking'])}  click: {r2[p['id']]['click']}")
    (pr.out / "results.json").write_text(json.dumps({"round1": r1, "round2": r2}, indent=2))
    print("5/5 report\n"); print(report(pr, people, r1, r2))


if __name__ == "__main__":
    main()
