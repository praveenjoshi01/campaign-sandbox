"""Build out/<project>/ui.html: a MiroFish-style console (graph left, step workbench right, log below) from a saved run.

usage: python3 make_ui.py <project> [run_log_name]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from llm import MODEL
from poc import Project, _layout, evaluate, relabel, stats

ROOT = Path(__file__).parent


def fix(pr: Project, p: dict, r: dict) -> dict:
    """Replace the persona's own 'Ad 3' mentions with the real ad labels so quotes read correctly on the page."""
    lay = _layout(p, pr.texts)
    sub = lambda t: relabel(t, lay, lambda v: f'"{pr.labels[v]}"')
    return {**r, "reasoning": sub(r["reasoning"]), "objection": sub(r["objection"])}


def build_data(pr: Project, log_name: str) -> dict:
    res = json.loads((pr.out / "results.json").read_text())
    people = json.loads((pr.out / "personas.json").read_text())
    graph = json.loads((pr.out / "graph.json").read_text())
    r1, r2 = res["round1"], res["round2"]
    s1, s2 = stats(pr, people, r1), stats(pr, people, r2)
    log = (pr.out / log_name).read_text().split("\n5/5 report")[0].rstrip().split("\n")
    fields = [{"key": k, "label": k.replace("_context", "").replace("_", " ").capitalize()} for k in pr.meta.get("persona_fields", {})]
    return {
        "title": pr.meta["title"], "model": f"{MODEL} (local, Ollama)", "n": len(people), "hypothesis": pr.cfg["hypothesis"],
        "variants": [{"id": v, "name": pr.labels[v], "text": pr.texts[v], "rank1": s1["all"]["rank"][v], "rank2": s2["all"]["rank"][v],
                      "click1": s1["all"]["click"][v], "click2": s2["all"]["click"][v]} for v in pr.texts],
        "none1": s1["all"]["none"], "none2": s2["all"]["none"],
        "segments": [{"id": s["id"], "name": s["name"], "rank2": s2[s["id"]]["rank"], "click2": s2[s["id"]]["click"],
                      "none2": s2[s["id"]]["none"]} for s in pr.segments],
        "checks": {"r1": evaluate(pr, s1), "r2": evaluate(pr, s2)},
        "persona_fields": fields,
        "people": [{**p, "r1": fix(pr, p, r1[p["id"]]), "r2": fix(pr, p, r2[p["id"]])} for p in people],
        "graph": graph,
        "assumptions": [l.lstrip("- ").strip() for l in pr.product.splitlines() if "ASSUMED" in l and not l.startswith("Everything")],
        "log": log, "logname": f"out/{pr.name}/{log_name}",
    }


def main():
    pr = Project(sys.argv[1])
    log_name = sys.argv[2] if len(sys.argv) > 2 else "run.log"
    html = (ROOT / "ui_template.html").read_text().replace("__DATA__", json.dumps(build_data(pr, log_name)).replace("</", "<\\/"))
    (pr.out / "ui.html").write_text(html)
    print("wrote", pr.out / "ui.html", f"({len(html) // 1024} KB)")


if __name__ == "__main__":
    main()
