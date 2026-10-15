#!/usr/bin/env python3
"""Static 04b layout layers (1080x1920 PNGs) and a circular portrait.

  python make_layout.py --out remotion/public/layout                      # bg.png, blue.png, red_circle.png
  python make_layout.py --out work --portrait face.jpg --face-box x,y,size  # + portrait_color.png
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True); ap.add_argument("--portrait"); ap.add_argument("--face-box")
a = ap.parse_args()
W, H = 1080, 1920
BG, BLUE, RED = (246, 241, 229, 255), (31, 86, 214, 255), (232, 36, 43, 255)
CX, RED_R, RED_CY = W // 2, round(0.32 * W) / 2, round(0.55 * H)
PORT_D, BLUE_R = round(0.60 * round(0.32 * W)), round(0.30 * H)
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
Image.new("RGBA", (W, H), BG).save(out / "bg.png")
im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(im).ellipse((CX - BLUE_R, H - BLUE_R, CX + BLUE_R, H + BLUE_R), fill=BLUE); im.save(out / "blue.png")
im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(im).ellipse((CX - RED_R, RED_CY - RED_R, CX + RED_R, RED_CY + RED_R), fill=RED); im.save(out / "red_circle.png")
if a.portrait:
    src = Image.open(a.portrait).convert("RGB")
    if a.face_box:
        x, y, s = map(int, a.face_box.split(","))
    else:
        s = min(src.size); x, y = (src.width - s) // 2, (src.height - s) // 2
    face = src.crop((x, y, x + s, y + s)).resize((PORT_D, PORT_D), Image.Resampling.LANCZOS)
    mask = Image.new("L", (PORT_D, PORT_D), 0); ImageDraw.Draw(mask).ellipse((0, 0, PORT_D - 1, PORT_D - 1), fill=255)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); im.paste(face, (CX - PORT_D // 2, int(RED_CY - PORT_D // 2)), mask)
    im.save(out / "portrait_color.png")  # use with portrait.scale 1.1659 / dy -31.3 in props (the 04b look)
print("layers ->", out)
