#!/usr/bin/env python3
"""Word-by-word caption overlay (transparent ProRes 4444), only the spoken word in red.

  python render_captions.py words_timeline.json --font ../fonts/MomoTrustDisplay/MomoTrustDisplay-Regular.ttf \
      --duration 124.7 --out captions.mov

words_timeline.json: [{"text": "Kamu", "start": 0.0, "end": 0.34, "brk": false, "verse": false}, ...]
("brk": true forces a new page before that word). Same rules as the Remotion template:
86 px, line height 86, GPOS pair kerning read with fontTools plus per-pair overrides (Al -30 units),
greedy wrap at 960 px, 4 lines per page, a page shows from the end of the previous page's last word.
Also writes <out>.pages.json. Glyphs are placed one by one with the kerning above (same layout as the Remotion template).
"""
import argparse, json, subprocess
import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("timeline"); ap.add_argument("--font", required=True); ap.add_argument("--out", default="captions.mov")
ap.add_argument("--duration", type=float, required=True); ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--size", type=int, default=86); ap.add_argument("--line-height", type=int, default=86)
ap.add_argument("--max-width", type=int, default=960); ap.add_argument("--lines", type=int, default=4)
ap.add_argument("--top", type=int, default=220, help="y of the first line's ascender")
ap.add_argument("--red", default="#E8242B"); ap.add_argument("--black", default="#000000")
ap.add_argument("--override", action="append", default=["Al:-30"], help="pair:units, repeatable")
a = ap.parse_args()
W, H = 1080, 1920
hexc = lambda h: tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
RED, BLACK = hexc(a.red), hexc(a.black)
OVR = {o.split(":")[0]: int(o.split(":")[1]) for o in a.override}


def load_kern(path):
    tt = TTFont(path)
    cmap, upem = tt.getBestCmap(), tt["head"].unitsPerEm
    lookups = [lu for lu in tt["GPOS"].table.LookupList.Lookup if lu.LookupType == 2] if "GPOS" in tt else []
    cache = {}

    def kern(x, y):
        if (x, y) in cache:
            return cache[(x, y)]
        g1, g2, total = cmap.get(ord(x)), cmap.get(ord(y)), 0
        for lu in lookups:
            for sub in lu.SubTable:
                if g1 is None or g2 is None or g1 not in sub.Coverage.glyphs:
                    continue
                if sub.Format == 1:
                    for rec in sub.PairSet[sub.Coverage.glyphs.index(g1)].PairValueRecord:
                        if rec.SecondGlyph == g2 and rec.Value1 and rec.Value1.XAdvance:
                            total += rec.Value1.XAdvance
                else:
                    rec = sub.Class1Record[sub.ClassDef1.classDefs.get(g1, 0)].Class2Record[sub.ClassDef2.classDefs.get(g2, 0)]
                    if rec.Value1 and rec.Value1.XAdvance:
                        total += rec.Value1.XAdvance
        cache[(x, y)] = total + OVR.get(x + y, 0)
        return cache[(x, y)]
    return kern, upem


kern, upem = load_kern(a.font)
font = ImageFont.truetype(a.font, a.size)
asc, desc = font.getmetrics()
sc = a.size / upem
measure = lambda t: sum(font.getlength(c) for c in t) + sum(kern(t[i], t[i + 1]) for i in range(len(t) - 1)) * sc
space = font.getlength(" ")
line_w = lambda ln: sum(measure(w["text"]) for w in ln) + space * (len(ln) - 1)


def sprite(text, fill):
    im = Image.new("RGBA", (int(np.ceil(measure(text))) + 16, asc + desc + 16), (0, 0, 0, 0))
    d, x = ImageDraw.Draw(im), 8.0
    for i, c in enumerate(text):
        d.text((x, 8 + asc), c, font=font, fill=fill, anchor="ls")
        x += font.getlength(c) + (kern(c, text[i + 1]) * sc if i + 1 < len(text) else 0)
    return np.array(im)


words = json.load(open(a.timeline))
groups = [[]]
for w in words:
    if w.get("brk") and groups[-1]:
        groups.append([])
    groups[-1].append(w)
pages = []
for g in groups:
    lines, cur = [], []
    for w in g:
        if cur and line_w(cur + [w]) > a.max_width:
            lines.append(cur); cur = [w]
        else:
            cur.append(w)
    lines += [cur] if cur else []
    pages += [lines[i:i + a.lines] for i in range(0, len(lines), a.lines)]
show = [0.0]
for i in range(1, len(pages)):
    show.append(max(pages[i - 1][-1][-1]["end"], show[-1]))
base0 = a.top + asc
placed, cache = [], {}
for pg in pages:
    items = []
    for li, ln in enumerate(pg):
        x = (W - line_w(ln)) / 2
        for w in ln:
            if w["text"] not in cache:
                cache[w["text"]] = (sprite(w["text"], BLACK), sprite(w["text"], RED))
            items.append((w, x, base0 + li * a.line_height))
            x += measure(w["text"]) + space
    placed.append(items)
json.dump([{"page": i, "show": show[i], "first": p[0][0]["text"], "last": p[-1][-1]["text"]} for i, p in enumerate(pages)],
          open(a.out + ".pages.json", "w"), indent=0, ensure_ascii=False)

N = int(round(a.duration * a.fps))
proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                         "-r", str(a.fps), "-i", "pipe:0", "-c:v", "prores_ks", "-profile:v", "4444",
                         "-pix_fmt", "yuva444p10le", "-an", a.out], stdin=subprocess.PIPE)
frame, bi = np.zeros((H, W, 4), np.uint8), 0
y0, y1 = base0 - asc - 8, base0 + (a.lines - 1) * a.line_height + desc + 12
for i in range(N):
    t = i / a.fps
    while bi + 1 < len(show) and show[bi + 1] <= t:
        bi += 1
    frame[y0:y1] = 0
    for w, x, base in placed[bi]:
        arr = cache[w["text"]][1 if w["start"] <= t < w["end"] else 0]
        px, py = int(round(x - 8)), int(round(base - 8 - asc))
        sub = frame[py:py + arr.shape[0], px:px + arr.shape[1]]
        m = arr[:, :, 3] > 0
        sub[m] = arr[m]
    proc.stdin.write(frame.tobytes())
proc.stdin.close()
proc.wait()
print(f"{len(pages)} pages, {N} frames -> {a.out}")
