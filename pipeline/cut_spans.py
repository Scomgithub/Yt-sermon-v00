#!/usr/bin/env python3
"""Cut spans from a source video, snap each cut to the quietest point nearby, join with short audio crossfades.

  python cut_spans.py spans.in.json --source work/source.mp4 --out work/footage.mp4 [--snap 0.12] [--xfade 0.02]

spans.in.json: [{"label": "HOOK", "start": 496.30, "end": 503.10}, ...]   (source seconds, in output order)
Optional per span: "snap": false to keep the exact points, "fade_out": 0.04 for a tail fade.

Snapping: each start/end moves to the minimum 10 ms RMS frame within +/- --snap seconds, so cuts land in
pauses instead of on consonants. Check words at the edges afterwards (re-transcribe footage.mp4).
Writes footage.mp4 (1080x1920, source letterboxed) and spans.json (source and output times per span).
"""
import argparse, json, subprocess
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("spans"); ap.add_argument("--source", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--snap", type=float, default=0.12); ap.add_argument("--xfade", type=float, default=0.02)
ap.add_argument("--width", type=int, default=1080); ap.add_argument("--height", type=int, default=1920)
ap.add_argument("--fps", default="30000/1001"); ap.add_argument("--vcodec", default="libx264")
ap.add_argument("--spans-out", default=None)
a = ap.parse_args()
SR = 16000
spans = json.load(open(a.spans))


def rms_window(t0, t1):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", f"{max(0, t0):.3f}", "-t", f"{t1 - max(0, t0):.3f}",
                                   "-i", a.source, "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"])
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    hop = SR // 100
    n = len(x) // hop
    return max(0, t0), np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)


def snap(t):
    if a.snap <= 0:
        return t
    t0, r = rms_window(t - a.snap, t + a.snap)
    if len(r) == 0:
        return t
    return round(t0 + (int(np.argmin(r)) + 0.5) / 100, 3)


cuts = []
for s in spans:
    st, en = (snap(s["start"]), snap(s["end"])) if s.get("snap", True) else (s["start"], s["end"])
    cuts.append({**s, "start": st, "end": en})
    print(f"{s['label']:>12}: {s['start']:.3f}-{s['end']:.3f} -> {st:.3f}-{en:.3f}")

W, H, X = a.width, a.height, a.xfade
v, au = [], []
for i, c in enumerate(cuts):
    s, e = c["start"], c["end"]
    v.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS,scale={W}:{H}:force_original_aspect_ratio=decrease,"
             f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]")
    ee = e + (X if i < len(cuts) - 1 else 0)  # each span carries X extra so the crossfade does not eat speech
    fo = c.get("fade_out", 0.04 if i == len(cuts) - 1 else 0)
    fade = f",afade=t=out:st={ee - s - fo:.3f}:d={fo}" if fo else ""
    au.append(f"[0:a]atrim=start={s}:end={ee},asetpts=PTS-STARTPTS{fade}[a{i}]")
fc = ";".join(v + au) + ";" + "".join(f"[v{i}]" for i in range(len(cuts))) + f"concat=n={len(cuts)}:v=1:a=0[vo]"
prev = "a0"
for i in range(1, len(cuts)):
    fc += f";[{prev}][a{i}]acrossfade=d={X}:c1=tri:c2=tri[x{i}]"
    prev = f"x{i}"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.source, "-filter_complex", fc, "-map", "[vo]", "-map", f"[{prev}]",
                "-r", a.fps, "-c:v", a.vcodec, "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                "-ar", "48000", "-movflags", "+faststart", a.out], check=True)
t, out = 0.0, []
for c in cuts:
    d = c["end"] - c["start"]
    out.append({"label": c["label"], "source_start": c["start"], "source_end": c["end"],
                "output_start": round(t, 3), "output_end": round(t + d, 3)})
    t += d
json.dump({"source": a.source.split("/")[-1], "audio_crossfade_s": X, "spans": out, "total_s": round(t, 3)},
          open(a.spans_out or a.out.rsplit(".", 1)[0] + ".spans.json", "w"), indent=1)
print(f"total {t:.3f}s -> {a.out}")
