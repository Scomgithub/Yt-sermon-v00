#!/usr/bin/env python3
"""Full-frame colour wipe as a transparent ProRes 4444 overlay (sweeps on L->R, then off L->R, cubic in-out).

  python render_wipe.py --out wipe.mov --color "#E8242B" --dur 1.0
"""
import argparse, subprocess
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="wipe.mov"); ap.add_argument("--color", default="#E8242B")
ap.add_argument("--dur", type=float, default=1.0); ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--width", type=int, default=1080); ap.add_argument("--height", type=int, default=1920)
a = ap.parse_args()
W, H, F = a.width, a.height, int(round(a.dur * a.fps))
rgb = tuple(int(a.color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))


def ease(t):
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                      "-r", str(a.fps), "-i", "pipe:0", "-c:v", "prores_ks", "-profile:v", "4444",
                      "-pix_fmt", "yuva444p10le", a.out], stdin=subprocess.PIPE)
for i in range(F):
    t = (i + 0.5) / F
    f = np.zeros((H, W, 4), np.uint8)
    x0, x1 = (0, ease(t / 0.5) * W) if t < 0.5 else (ease((t - 0.5) / 0.5) * W, W)
    lo, hi = int(round(x0)), int(round(x1))
    f[:, lo:hi, :3] = rgb
    f[:, lo:hi, 3] = 255
    p.stdin.write(f.tobytes())
p.stdin.close()
p.wait()
print(f"{F} frames -> {a.out}")
