"""Render a ~24 s motion graphic (GIF) of a saved run, driven entirely by out/<project>/results.json.

  python3 make_motion.py <project>        ->  out/<project>/motion.gif

Scenes: title -> the ads -> the synthetic shoppers -> round 1 (everyone picks a favourite) -> round 2 (peers weigh in)
-> first-place votes -> where the same ad wins or loses by segment -> caveat + repo.
Pure Pillow, no ffmpeg or browser needed.
"""
from __future__ import annotations

import json
import math
import random
import sys

from PIL import Image, ImageDraw, ImageFont

from poc import Project, stats

W, H, S, FPS = 960, 540, 2, 15           # logical size, supersample, frames/s
BG, PANEL, EDGE, INK, DIM, ACCENT = "#0b1220", "#141d31", "#2a3a5c", "#f2f5fb", "#8b97b3", "#ff8a3d"
SEGCOL = ["#4da3ff", "#3ddc97", "#ffd166", "#ff7eb6", "#b79cff", "#5eead4"]
SANS = "/System/Library/Fonts/Avenir Next.ttc"
MONO = "/System/Library/Fonts/Menlo.ttc"
_fc: dict = {}


def font(size, kind="regular"):
    idx = {"bold": 0, "demi": 2, "medium": 5, "regular": 7, "heavy": 8}
    key = (size, kind)
    if key not in _fc:
        _fc[key] = ImageFont.truetype(MONO, int(size * S), index=0) if kind == "mono" else ImageFont.truetype(SANS, int(size * S), index=idx[kind])
    return _fc[key]


def ease(t):
    t = max(0.0, min(1.0, t))
    return 4 * t ** 3 if t < .5 else 1 - (-2 * t + 2) ** 3 / 2


def clamp(t):
    return max(0.0, min(1.0, t))


def mix(c1, c2, t):
    a, b = [int(c1[i:i + 2], 16) for i in (1, 3, 5)], [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * clamp(t)) for i in range(3))


class Canvas:
    def __init__(self):
        self.im = Image.new("RGB", (W * S, H * S), BG)
        self.d = ImageDraw.Draw(self.im)

    def text(self, xy, s, size=18, kind="regular", fill=INK, anchor="la", alpha=1.0):
        fill = mix(BG, fill, alpha) if alpha < 1 else fill
        self.d.text((xy[0] * S, xy[1] * S), s, font=font(size, kind), fill=fill, anchor=anchor)

    def rrect(self, box, r=12, fill=PANEL, outline=None, width=2, alpha=1.0):
        x0, y0, x1, y1 = [v * S for v in box]
        f = mix(BG, fill, alpha) if (fill and alpha < 1) else fill
        o = mix(BG, outline, alpha) if (outline and alpha < 1) else outline
        self.d.rounded_rectangle((x0, y0, x1, y1), r * S, fill=f, outline=o, width=width * S if outline else 0)

    def dot(self, x, y, r, fill, alpha=1.0, ring=None):
        f = mix(BG, fill, alpha) if alpha < 1 else fill
        self.d.ellipse(((x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S), fill=f, outline=ring, width=S if ring else 0)

    def out(self):
        return self.im.resize((W, H), Image.LANCZOS)


def wrap(text, width_chars):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width_chars:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return lines + [cur]


class Story:
    def __init__(self, pr: Project):
        self.pr = pr
        res = json.loads((pr.out / "results.json").read_text())
        self.people = json.loads((pr.out / "personas.json").read_text())
        self.r1, self.r2 = res["round1"], res["round2"]
        self.ads = list(pr.texts)
        self.seg_ids = [s["id"] for s in pr.segments]
        self.s2 = stats(pr, self.people, self.r2)
        self.n = len(self.people)
        self.first1 = {p["id"]: self.r1[p["id"]]["ranking"][0] for p in self.people}
        self.first2 = {p["id"]: self.r2[p["id"]]["ranking"][0] for p in self.people}
        self.votes2 = {a: sum(f == a for f in self.first2.values()) for a in self.ads}
        self.winner = max(self.ads, key=lambda a: self.votes2[a])
        self.loser = max(self.ads, key=lambda a: self.s2["all"]["rank"][a])
        rng = random.Random(3)
        self.cloud = {p["id"]: (60 + rng.random() * 230, 120 + rng.random() * 330) for p in self.people}
        self.col = {p["id"]: SEGCOL[self.seg_ids.index(p["segment"]) % len(SEGCOL)] for p in self.people}
        # card grid: 2 columns x 3 rows on the right
        cols = 2
        self.card = {}
        for i, a in enumerate(self.ads):
            r, c = divmod(i, cols)
            x0, y0 = 340 + c * 300, 82 + r * 118
            self.card[a] = (x0, y0, x0 + 280, y0 + 104)
        # settle positions: r1 grouping, then r2 grouping (stable for non-movers)
        self.pos1 = self.pack(self.first1, None)
        self.pos2 = self.pack(self.first2, self.pos1)
        # the ad whose rank differs most between segments
        spread = {a: max(self.s2[s]["rank"][a] for s in self.seg_ids) - min(self.s2[s]["rank"][a] for s in self.seg_ids) for a in self.ads}
        self.volatile = max(self.ads, key=lambda a: spread[a])
        self.hi_seg = min(self.seg_ids, key=lambda s: self.s2[s]["rank"][self.volatile])
        self.lo_seg = max(self.seg_ids, key=lambda s: self.s2[s]["rank"][self.volatile])
        self.moved = sum(self.first1[k] != self.first2[k] for k in self.first1)

    def pack(self, first, prev):
        slots, pos = {a: [] for a in self.ads}, {}
        order = sorted(self.people, key=lambda p: (prev is not None and first[p["id"]] != self.first1[p["id"]], p["id"]))
        for p in order:
            a = first[p["id"]]
            k = len(slots[a])
            slots[a].append(p["id"])
            x0, y0, x1, y1 = self.card[a]
            pos[p["id"]] = (x0 + 18 + (k % 10) * 25, y1 - 38 + (k // 10) * 20)
        return pos

    # ---------------- drawing helpers ----------------
    def header(self, c, eyebrow, line, a=1.0):
        c.text((40, 28), eyebrow, 13, "mono", ACCENT, alpha=a)
        c.text((40, 48), line, 24, "bold", INK, alpha=a)

    def draw_cards(self, c, alpha=None, counts=None, highlight=None, dim=None):
        for i, a in enumerate(self.ads):
            al = 1.0 if alpha is None else clamp(alpha(i))
            if al <= 0:
                continue
            x0, y0, x1, y1 = self.card[a]
            dy = (1 - ease(al)) * 18
            edge = ACCENT if highlight == a else EDGE
            fill = PANEL if dim != a else mix(BG, PANEL, .55)
            c.rrect((x0, y0 + dy, x1, y1 + dy), 12, fill, edge, 3 if highlight == a else 2, al)
            c.dot(x0 + 22, y0 + 24 + dy, 12, "#22314f", al)
            c.text((x0 + 22, y0 + 24 + dy), chr(65 + i), 14, "bold", INK, "mm", al)
            c.text((x0 + 42, y0 + 24 + dy), self.pr.labels[a], 16, "demi", INK if dim != a else DIM, "lm", al)
            if counts is not None:
                c.text((x1 - 18, y0 + 24 + dy), str(counts[a]), 22, "bold", ACCENT if highlight == a else INK, "rm", al)

    # ---------------- scenes (t in 0..1) ----------------
    def s_title(self, c, t):
        a = ease(t * 3)
        c.text((W / 2, 170), "THANKSGIVING WEEK 2026", 15, "mono", ACCENT, "mm", a)
        c.text((W / 2, 235), "One gaming laptop.", 52, "heavy", INK, "mm", a)
        c.text((W / 2, 297), f"{len(self.ads)} ways to sell it.", 52, "heavy", INK, "mm", ease(t * 3 - .5))
        c.text((W / 2, 372), self.pr.meta.get("product_name", self.pr.name), 20, "medium", DIM, "mm", ease(t * 3 - 1))
        c.text((W / 2, 404), "Which wording would 20 synthetic shoppers pick?", 18, "regular", DIM, "mm", ease(t * 3 - 1.4))

    def s_ads(self, c, t):
        self.header(c, "THE CONTENDERS", f"{len(self.ads)} ad wordings, one product", ease(t * 4))
        self.draw_cards(c, alpha=lambda i: t * 3.2 - i * .38)
        # the first ad text, so the viewer reads real copy
        a = self.ads[min(len(self.ads) - 1, int(clamp(t * 1.1) * len(self.ads)))]
        for j, line in enumerate(wrap('"' + self.pr.texts[a] + '"', 40)[:7]):
            c.text((40, 150 + j * 24), line, 15, "regular", DIM, alpha=ease(t * 4))
        c.text((40, 128), self.pr.labels[a].upper(), 12, "mono", ACCENT, alpha=ease(t * 4))

    def draw_dots(self, c, pos_fn, alpha_fn=lambda i: 1.0, r=7):
        for i, p in enumerate(self.people):
            al = alpha_fn(i)
            if al <= 0:
                continue
            x, y = pos_fn(p["id"], i)
            c.dot(x, y, r * (0.6 + 0.4 * ease(al)), self.col[p["id"]], clamp(al))

    def legend(self, c, a=1.0, y=438):
        x = 40
        for k, s in enumerate(self.pr.segments):
            c.dot(x + 6, y + 8, 6, SEGCOL[k % len(SEGCOL)], a)
            c.text((x + 18, y + 8), s["name"], 13, "medium", DIM, "lm", a)
            x += 24 + int(font(13, "medium").getlength(s["name"]) / S) + 18

    def s_shoppers(self, c, t):
        self.header(c, "THE PANEL", f"{self.n} synthetic shoppers, {len(self.pr.segments)} audiences", 1)
        self.draw_cards(c)
        self.draw_dots(c, lambda pid, i: (self.cloud[pid][0] + math.sin(t * 5 + i) * 3, self.cloud[pid][1] + math.cos(t * 4 + i) * 3),
                       lambda i: t * 2.6 - i * .07)
        self.legend(c, ease(t * 3))

    def round_title(self, c, label, line):
        c.rrect((40, 474, 920, 512), 10, PANEL, None)
        c.text((58, 493), label, 12, "mono", ACCENT, "lm")
        c.text((170, 493), line, 15, "medium", INK, "lm")

    def s_round1(self, c, t):
        self.header(c, "ROUND 1", "Everyone ranks all six ads, alone", 1)
        counts = {a: 0 for a in self.ads}
        pos = {}
        for i, p in enumerate(self.people):
            e = ease((t * 1.5 - i * 0.045) / 0.6)
            x0, y0 = self.cloud[p["id"]]
            x1, y1 = self.pos1[p["id"]]
            arc = math.sin(e * math.pi) * -40
            pos[p["id"]] = (x0 + (x1 - x0) * e, y0 + (y1 - y0) * e + arc)
            if e >= .98:
                counts[self.first1[p["id"]]] += 1
        self.draw_cards(c, counts=counts)
        self.draw_dots(c, lambda pid, i: pos[pid])
        self.legend(c, 1)
        self.round_title(c, "FIRST CHOICE", "Each dot flies to the ad that shopper ranks #1")

    def s_round2(self, c, t):
        self.header(c, "ROUND 2", "Then they read three peers' reactions", 1)
        e = ease((t - .25) / .5)
        counts = {a: 0.0 for a in self.ads}
        pos = {}
        for p in self.people:
            pid = p["id"]
            (x0, y0), (x1, y1) = self.pos1[pid], self.pos2[pid]
            pos[pid] = (x0 + (x1 - x0) * e, y0 + (y1 - y0) * e - (math.sin(e * math.pi) * 24 if self.first1[pid] != self.first2[pid] else 0))
            counts[self.first1[pid]] += 1 - e
            counts[self.first2[pid]] += e
        counts = {a: round(v) for a, v in counts.items()}
        self.draw_cards(c, counts=counts)
        self.draw_dots(c, lambda pid, i: pos[pid])
        self.legend(c, 1)
        self.round_title(c, "PEER INFLUENCE", f"{self.moved} of {self.n} shoppers changed their #1 pick" if e > .5 else "Peers weigh in...")

    def s_votes(self, c, t):
        self.header(c, "RESULT", "Who ranks each ad first (after peers)", 1)
        order = sorted(self.ads, key=lambda a: -self.votes2[a])
        mx = max(self.votes2.values()) or 1
        for k, a in enumerate(order):
            y = 118 + k * 62
            g = ease(t * 1.7 - k * .12)
            win = a == self.winner
            c.text((40, y + 14), self.pr.labels[a], 17, "demi", INK if win else DIM, "lm", clamp(g * 2))
            bx0, bx1 = 270, 760
            c.rrect((bx0, y, bx1, y + 28), 8, PANEL, None)
            wbar = (bx1 - bx0) * self.votes2[a] / mx * g
            if wbar > 4:
                c.rrect((bx0, y, bx0 + wbar, y + 28), 8, ACCENT if win else "#4a5d8a", None)
            c.text((bx0 + max(wbar, 0) + 12, y + 14), f"{round(self.votes2[a] * g)}", 20, "bold", ACCENT if win else DIM, "lm", clamp(g * 2))
            c.text((920, y + 14), f"avg #{self.s2['all']['rank'][a]:.2f}", 13, "mono", DIM, "rm", clamp(g * 2))
        c.text((920, 96), "AVG POSITION (1 = BEST)", 11, "mono", DIM, "rm", ease(t * 3))

    def s_segments(self, c, t):
        self.header(c, "BY AUDIENCE", "The same ad wins or loses depending on who sees it", 1)
        for k, s in enumerate(self.pr.segments):
            y = 120 + k * 56
            g = ease(t * 2.2 - k * .22)
            best = min(self.ads, key=lambda a: self.s2[s["id"]]["rank"][a])
            c.dot(52, y + 20, 8, SEGCOL[k % len(SEGCOL)], clamp(g * 2))
            c.text((72, y + 20), s["name"], 18, "demi", INK, "lm", clamp(g * 2))
            c.rrect((380, y, 920, y + 40), 10, PANEL, None, alpha=clamp(g * 2))
            c.text((398, y + 20), f"best: {self.pr.labels[best]}", 17, "bold", ACCENT, "lm", clamp(g * 2))
            c.text((904, y + 20), f"avg #{self.s2[s['id']]['rank'][best]:.1f}", 14, "mono", DIM, "rm", clamp(g * 2))
        g = ease(t * 2.4 - 1.4)
        v, hi, lo = self.volatile, self.hi_seg, self.lo_seg
        names = {s["id"]: s["name"] for s in self.pr.segments}
        c.rrect((40, 362, 920, 450), 14, "#1b2640", ACCENT, 2, clamp(g))
        c.text((64, 386), f'"{self.pr.labels[v]}"', 20, "bold", ACCENT, "lm", clamp(g))
        c.text((64, 420), f"ranks #{self.s2[hi]['rank'][v]:.1f} with {names[hi].lower()}, but #{self.s2[lo]['rank'][v]:.1f} with {names[lo].lower()}.",
               18, "medium", INK, "lm", clamp(g))

    def s_end(self, c, t):
        a = ease(t * 3)
        c.text((W / 2, 150), "Simulated shoppers, not real ones.", 34, "heavy", INK, "mm", a)
        c.text((W / 2, 200), "Treat the winner as a hypothesis, then run a real A/B test.", 20, "medium", DIM, "mm", ease(t * 3 - .5))
        c.rrect((190, 260, 770, 330), 14, PANEL, EDGE, 2, ease(t * 3 - 1))
        c.text((W / 2, 288), "100% local  |  Ollama  |  no data leaves your machine", 17, "medium", INK, "mm", ease(t * 3 - 1.1))
        c.text((W / 2, 314), "swap any product: projects/<name>/", 14, "mono", DIM, "mm", ease(t * 3 - 1.2))
        c.text((W / 2, 396), "github.com/praveenjoshi01/campaign-sandbox", 22, "mono", ACCENT, "mm", ease(t * 3 - 1.6))


SCENES = [("title", 2.6), ("ads", 3.6), ("shoppers", 2.4), ("round1", 4.2), ("round2", 3.0), ("votes", 3.6), ("segments", 4.0), ("end", 3.2)]


def render(pr: Project, out_path: str):
    st = Story(pr)
    fns = {"title": st.s_title, "ads": st.s_ads, "shoppers": st.s_shoppers, "round1": st.s_round1, "round2": st.s_round2,
           "votes": st.s_votes, "segments": st.s_segments, "end": st.s_end}
    frames, fade = [], 0.18
    for name, dur in SCENES:
        n = int(dur * FPS)
        for f in range(n):
            t = f / max(1, n - 1)
            c = Canvas()
            fns[name](c, t)
            im = c.out()
            edge = min(f, n - 1 - f) / (fade * FPS)  # cross-fade through the background at scene edges
            if edge < 1 and name not in ("round1", "round2"):
                im = Image.blend(Image.new("RGB", im.size, BG), im, ease(edge))
            frames.append(im)
    # hold the last frame a little longer
    frames += [frames[-1]] * int(1.0 * FPS)
    # one shared palette for every frame (no colour flicker, smaller file)
    tiles = frames[:: max(1, len(frames) // 24)]
    sheet = Image.new("RGB", (W * 4, H * ((len(tiles) + 3) // 4)))
    for i, f in enumerate(tiles):
        sheet.paste(f, ((i % 4) * W, (i // 4) * H))
    sw = ImageDraw.Draw(sheet)  # large swatches so every key colour keeps its own palette slot
    for i, col in enumerate(SEGCOL[:4] + [ACCENT, INK, DIM, PANEL, EDGE, BG]):
        sw.rectangle((i * 60, 0, i * 60 + 59, 59), fill=col)
    base = sheet.quantize(colors=160, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = [f.quantize(palette=base, dither=Image.Dither.NONE) for f in frames]
    pal[0].save(out_path, save_all=True, append_images=pal[1:], duration=int(1000 / FPS), loop=0, optimize=True, disposal=1)
    print(f"wrote {out_path}: {len(frames)} frames, {len(frames) / FPS:.1f}s")


def stills(pr: Project):
    """Full-resolution PNGs of the key end-states, for articles and READMEs."""
    st = Story(pr)
    d = pr.out / "stills"
    d.mkdir(exist_ok=True)
    for name, fn, t in (("1-ads", st.s_ads, 0.97), ("2-round1", st.s_round1, 1.0), ("3-round2", st.s_round2, 1.0),
                        ("4-votes", st.s_votes, 1.0), ("5-segments", st.s_segments, 1.0)):
        c = Canvas()
        fn(c, t)
        c.im.save(d / f"{name}.png", optimize=True)
    print("wrote stills to", d)


if __name__ == "__main__":
    pr = Project(sys.argv[1])
    if "--stills" in sys.argv:
        stills(pr)
    else:
        render(pr, str(pr.out / "motion.gif"))
