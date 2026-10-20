"""Validate a project folder before spending model time on it.

  python3 check_project.py <project> [personas_per_segment]

Errors (exit 1): missing files/keys, criteria that point at unknown ads or segments, too few situations per segment.
Warnings: numbers, prices and spec tokens used in an ad that never appear in product.md (possible unsupported claim),
and brief lines still marked ASSUMED (a reminder to confirm them with the real offer).
"""
from __future__ import annotations

import re
import sys

from poc import Project

TOKEN = re.compile(r"\$?\d[\d,.]*\s?(?:%|hz|gb|tb|fps|w|kg|mah|wh)?|rtx\s?\d{4}", re.I)


def tokens(text: str) -> set:
    return {re.sub(r"[\s,]", "", t.lower()).rstrip(".") for t in TOKEN.findall(text)}


def main():
    name = sys.argv[1]
    per = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    pr = Project(name)
    errs, warns = [], []

    for k in ("title", "scenario", "persona_fields"):
        if k not in pr.meta:
            errs.append(f"project.json missing '{k}'")
    if "{n}" not in pr.meta.get("scenario", ""):
        warns.append("project.json scenario has no {n} placeholder for the number of ads")
    for k in ("hypothesis", "success_criteria", "variants"):
        if k not in pr.cfg:
            errs.append(f"campaigns.json missing '{k}'")
    if len(pr.texts) < 3:
        errs.append("need at least 3 ad variants to compare")
    seg_ids = {s["id"] for s in pr.segments}
    for s in pr.segments:
        if len(s.get("situations", [])) < per:
            warns.append(f"segment {s['id']} has {len(s.get('situations', []))} situations for {per} personas (they will repeat)")
    for c in pr.cfg.get("success_criteria", []):
        for k in ("better", "worse"):
            if c[k] not in pr.texts:
                errs.append(f"criterion '{c['label']}' references unknown ad '{c[k]}'")
        if c.get("segment") and c["segment"] not in seg_ids:
            errs.append(f"criterion '{c['label']}' references unknown segment '{c['segment']}'")

    core = lambda t: re.match(r"\$?\d[\d.]*", t).group(0) if re.match(r"\$?\d", t) else t
    brief = tokens(pr.product)
    brief_cores = {core(t) for t in brief}
    for v, text in pr.texts.items():  # a number counts as supported if the brief has it, with or without its unit
        miss = sorted(t for t in tokens(text) if t not in brief and core(t) not in brief_cores and len(t) > 1)
        if miss:
            warns.append(f"ad {v}: tokens not found in product.md: {', '.join(miss)}")
    for i, line in enumerate(pr.product.splitlines(), 1):
        if "ASSUMED" in line:
            warns.append(f"product.md line {i} is an ASSUMPTION: {line.strip()[:90]}")

    print(f"project {name}: {len(pr.texts)} ads, {len(pr.segments)} segments x {per} = {len(pr.segments) * per} personas, "
          f"{len(pr.cfg.get('success_criteria', []))} criteria")
    for w in warns:
        print("  WARN ", w)
    for e in errs:
        print("  ERROR", e)
    print("OK" if not errs else "FAILED")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
