#!/usr/bin/env python3
"""Pick the 1080p video format with the highest *measured* bitrate.

yt-dlp header bitrates can mislead. On one sermon, format 399 (AV1 1080p) was
listed around 290 kb/s but actually averaged ~2 Mbps, while format 137
(H.264 1080p DASH) measured 6.75 Mbps. HLS formats 614 and 270 are mirrors
of 248 (VP9) and 137; their advertised bitrates are only labels.

This script lists 1080p video-only formats, skips HLS when a DASH/https
copy exists, downloads a short probe of each remaining candidate, and
measures bits/s with ffprobe (file size / duration).

  python pipeline/pick_1080.py URL --start 41:04 --seconds 8
  python pipeline/pick_1080.py URL --start 41:04 --seconds 8 --json

Prints a table and, on the last line, BEST=<format_id>.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def parse_time(s: str) -> float:
    parts = [float(x) for x in s.split(":")]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    raise ValueError(f"bad time: {s}")


def fmt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - h * 3600 - m * 60
    if h:
        return f"{h}:{m:02d}:{s:06.3f}".rstrip("0").rstrip(".")
    return f"{m}:{s:06.3f}".rstrip("0").rstrip(".")


def is_hls(fmt: dict) -> bool:
    proto = (fmt.get("protocol") or "").lower()
    return "m3u8" in proto or "hls" in proto


def list_candidates(info: dict) -> list[dict]:
    formats = info.get("formats") or []
    pool = []
    for f in formats:
        if f.get("height") != 1080:
            continue
        if (f.get("vcodec") or "none") == "none":
            continue
        if (f.get("acodec") or "none") != "none":
            continue  # video-only; audio is added later
        pool.append(f)
    if not pool:
        # fall back to muxed 1080p
        for f in formats:
            if f.get("height") == 1080 and (f.get("vcodec") or "none") != "none":
                pool.append(f)
    dash = [f for f in pool if not is_hls(f)]
    return dash or pool


def probe_bitrate(url: str, format_id: str, start: str, end: str, tmp: Path) -> dict:
    out = tmp / f"probe_{format_id}.%(ext)s"
    cmd = [
        "yt-dlp",
        "-f",
        format_id,
        "--download-sections",
        f"*{start}-{end}",
        "--force-keyframes-at-cuts",
        "-o",
        str(out),
        "--no-part",
        url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return {"ok": False, "error": (r.stderr or r.stdout)[-500:]}
    files = list(tmp.glob(f"probe_{format_id}.*"))
    files = [p for p in files if p.suffix not in {".part", ".ytdl"}]
    if not files:
        return {"ok": False, "error": "no probe file written"}
    path = files[0]
    size = path.stat().st_size
    dur = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        text=True,
    ).strip()
    try:
        duration = float(dur)
    except ValueError:
        return {"ok": False, "error": f"ffprobe duration: {dur!r}"}
    if duration <= 0:
        return {"ok": False, "error": "zero duration"}
    bps = size * 8.0 / duration
    return {"ok": True, "path": str(path), "bytes": size, "duration": duration, "bps": bps}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--start", required=True, help="section start (seconds or HH:MM:SS)")
    ap.add_argument("--seconds", type=float, default=8.0, help="probe length (default 8)")
    ap.add_argument("--json", action="store_true", dest="as_json")
    a = ap.parse_args()

    info = json.loads(subprocess.check_output(["yt-dlp", "-J", "--no-download", a.url], text=True))
    cands = list_candidates(info)
    if not cands:
        raise SystemExit("no 1080p video formats found")

    start_s = parse_time(a.start)
    end = fmt_time(start_s + a.seconds)
    rows = []
    with tempfile.TemporaryDirectory(prefix="yt1080-") as td:
        tmp = Path(td)
        for f in cands:
            fid = str(f["format_id"])
            advertised = f.get("tbr") or f.get("vbr")
            print(
                f"probing {fid}  {f.get('vcodec')}  advertised tbr={advertised}  protocol={f.get('protocol')}",
                flush=True,
                file=sys.stderr,
            )
            m = probe_bitrate(a.url, fid, a.start, end, tmp)
            row = {
                "format_id": fid,
                "vcodec": f.get("vcodec"),
                "protocol": f.get("protocol"),
                "advertised_tbr_kbps": advertised,
                "ext": f.get("ext"),
                **m,
            }
            rows.append(row)
            if m.get("ok"):
                print(f"  measured {m['bps']/1e6:.2f} Mbps  ({m['bytes']} bytes in {m['duration']:.2f}s)", file=sys.stderr)
            else:
                print(f"  failed: {m.get('error')}", file=sys.stderr)

    ok = [r for r in rows if r.get("ok")]
    if not ok:
        raise SystemExit("all 1080p probes failed")
    best = max(ok, key=lambda r: r["bps"])
    if a.as_json:
        json.dump({"candidates": rows, "best": best["format_id"]}, sys.stdout, indent=2)
        print()
    else:
        print(file=sys.stderr)
        print(f"{'id':<8} {'codec':<12} {'proto':<16} {'advertised':>12} {'measured':>12}", file=sys.stderr)
        for r in rows:
            adv = f"{r['advertised_tbr_kbps']:.0f} kb/s" if r.get("advertised_tbr_kbps") else "-"
            meas = f"{r['bps']/1e6:.2f} Mbps" if r.get("ok") else "FAIL"
            print(f"{r['format_id']:<8} {str(r.get('vcodec') or '-'):<12} {str(r.get('protocol') or '-'):<16} {adv:>12} {meas:>12}", file=sys.stderr)
        print(file=sys.stderr)
        print(
            f"highest measured 1080p: {best['format_id']} at {best['bps']/1e6:.2f} Mbps "
            f"(ffprobe size/duration; advertised tbr is not trusted)",
            file=sys.stderr,
        )
        print(f"BEST={best['format_id']}")


if __name__ == "__main__":
    main()
