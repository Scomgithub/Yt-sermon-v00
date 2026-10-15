#!/usr/bin/env python3
"""Transcribe with word timestamps (faster-whisper).

  python transcribe.py work/footage.mp4 -o work/words.json --lang id --model medium
  python transcribe.py work/source.mp4 --start 130 --end 520 -o work/region.json   # a region only

Output: {"source", "model", "language", "segments":[{start,end,text}], "words":[{word,start,end,prob}]}
Times are relative to the input file (the region offset is added back).
"""
import argparse, json, subprocess, tempfile, os
from faster_whisper import WhisperModel

ap = argparse.ArgumentParser()
ap.add_argument("input"); ap.add_argument("-o", "--out", required=True)
ap.add_argument("--lang", default="id"); ap.add_argument("--model", default="medium")
ap.add_argument("--start", type=float, default=0.0); ap.add_argument("--end", type=float)
ap.add_argument("--device", default="auto"); ap.add_argument("--compute-type", default="int8")
ap.add_argument("--prompt", default=None, help="initial prompt, e.g. names and Bible books")
a = ap.parse_args()

with tempfile.TemporaryDirectory() as td:
    wav = os.path.join(td, "a.wav")
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(a.start)]
    if a.end: cmd += ["-to", str(a.end)]
    subprocess.run(cmd + ["-i", a.input, "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
    model = WhisperModel(a.model, device=a.device, compute_type=a.compute_type)
    segs, info = model.transcribe(wav, language=a.lang, word_timestamps=True, vad_filter=False,
                                  initial_prompt=a.prompt, beam_size=5)
    out = {"source": os.path.basename(a.input), "model": f"faster-whisper-{a.model}", "language": a.lang,
           "offset": a.start, "segments": [], "words": []}
    for s in segs:
        out["segments"].append({"start": round(s.start + a.start, 3), "end": round(s.end + a.start, 3), "text": s.text.strip()})
        for w in s.words or []:
            out["words"].append({"word": w.word.strip(), "start": round(w.start + a.start, 3),
                                 "end": round(w.end + a.start, 3), "prob": round(w.probability, 3)})
json.dump(out, open(a.out, "w"), ensure_ascii=False, indent=1)
print(f"{len(out['words'])} words -> {a.out}")
