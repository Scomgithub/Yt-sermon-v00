#!/usr/bin/env python3
"""Loudness step: speech gain, optional soundtrack bed, true-peak limit.

  python loudness.py work/footage_dfn.mp4 work/footage_dfn_lufs.mp4
  python loudness.py in.mp4 out.mp4 --method integrated --speech -25.9
  python loudness.py in.mp4 out.mp4 --bed music.mp3 --bed-lufs -41 --bed-fade-in 1 --bed-fade-out 2

Speech (static gain, no dynamics processing):
  --method sp90 (default): the 90th percentile of EBU R128 short-term loudness S is moved to --speech
                (-25.9). Tracks perceived speaker level better than integrated when the clip has pauses.
  --method integrated: integrated loudness is moved to --speech.
Soundtrack bed: looped/trimmed to the clip, measured alone, gained to --bed-lufs integrated (about -41),
faded in/out, then mixed under the speech. Final true peak is held under --tp (-1 dBTP) with a limiter
only if needed. Video is stream-copied.
"""
import argparse, re, subprocess, json
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("input"); ap.add_argument("output")
ap.add_argument("--method", choices=["sp90", "integrated"], default="sp90")
ap.add_argument("--speech", type=float, default=-25.9)
ap.add_argument("--bed"); ap.add_argument("--bed-lufs", type=float, default=-41.0)
ap.add_argument("--bed-fade-in", type=float, default=1.0); ap.add_argument("--bed-fade-out", type=float, default=2.0)
ap.add_argument("--tp", type=float, default=-1.0)
a = ap.parse_args()


def measure(path, af=None):
    chain = (af + "," if af else "") + "ebur128=peak=true"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af", chain, "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    S = [float(x) for x in re.findall(r" S:\s*(-?[\d.]+)", r)]
    S = [x for x in S if x > -70]
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1])
    TP = float(re.findall(r"Peak:\s+(-?[\d.]+)", r)[-1])
    return {"I": I, "S_p90": float(np.percentile(S, 90)) if S else I, "TP": TP}


def dur(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]))


m0 = measure(a.input)
g = a.speech - (m0["S_p90"] if a.method == "sp90" else m0["I"])
D = dur(a.input)
fc = f"[0:a]volume={g:.2f}dB[sp]"
inputs = ["-i", a.input]
mix = "[sp]"
if a.bed:
    mb = measure(a.bed, f"atrim=0:{D:.3f}")
    gb = a.bed_lufs - mb["I"]
    inputs += ["-stream_loop", "-1", "-i", a.bed]
    fc += (f";[1:a]atrim=0:{D:.3f},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo,"
           f"volume={gb:.2f}dB,afade=t=in:d={a.bed_fade_in},afade=t=out:st={max(0, D - a.bed_fade_out):.3f}:d={a.bed_fade_out}[bed]"
           f";[sp]aformat=sample_rates=48000:channel_layouts=stereo[sp2];[sp2][bed]amix=inputs=2:normalize=0:duration=first[mix]")
    mix = "[mix]"
tmp = a.output + ".tmp.wav"
subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", mix, "-ar", "48000", tmp], check=True)
m1 = measure(tmp)
lim = ""
if m1["TP"] > a.tp:
    lim = f"alimiter=limit={10 ** ((a.tp - 0.3) / 20):.4f}:level=disabled:attack=1:release=50"
af = ["-af", lim] if lim else []
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.input, "-i", tmp, "-map", "0:v?", "-map", "1:a", "-c:v", "copy",
                *af, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", a.output], check=True)
subprocess.run(["rm", "-f", tmp])
m2 = measure(a.output)
print(json.dumps({"method": a.method, "target": a.speech, "speech_gain_db": round(g, 2), "before": m0, "after": m2,
                  "limited": bool(lim)}, indent=1))
