# Yt-sermon

Turns a section of a recorded sermon on YouTube into a 1080x1920 vertical clip: audio-driven cuts,
noise reduction, matched loudness, word-by-word captions (the spoken word in red), an audio spectrum,
the speaker's portrait, a Bible-verse label and a cover + colour-wipe intro. The final video is rendered
with [Remotion](https://www.remotion.dev) from a JSON props file.

## Pipeline

| step | tool | script |
|---|---|---|
| 1. download the section | yt-dlp | `pipeline/download_section.sh [--measure-1080] <url> <start> <end> work/source.mp4` |
| 2. transcribe with word timestamps | faster-whisper | `pipeline/transcribe.py work/source.mp4 -o work/source.words.json --lang id` |
| 3. pick spans, cut in pauses, 20 ms audio crossfades | ffmpeg + numpy | `pipeline/cut_spans.py spans.json --source work/source.mp4 --out work/footage.mp4` |
| 4. noise reduction | DeepFilterNet3 | `pipeline/denoise.sh work/footage.mp4 work/footage_dfn.mp4` |
| 5. loudness (+ optional music bed) | ffmpeg ebur128 | `pipeline/loudness.py work/footage_dfn.mp4 work/footage_dfn_lufs.mp4 [--bed music.mp3]` |
| 6. re-transcribe the cut for caption timing | faster-whisper | `pipeline/transcribe.py work/footage_dfn_lufs.mp4 -o work/words.json` |
| 7. write the clean caption text | you | `work/clip-script.md` (paragraphs; the verse in "double quotes") |
| 8. cover still (optional upscale + cutout + sticker outline) | rembg + Real-ESRGAN + OpenCV | see [Cover](#cover) |
| 9. render | Remotion | see Quick start |

Optional standalone renderers (overlays for an NLE such as CapCut): `pipeline/render_captions.py`
(caption sprites, Momo Trust Display with fontTools GPOS kerning), `pipeline/render_wipe.py`
(eased colour wipe), `pipeline/make_layout.py` (background, blue shape, red circle, circular portrait).

### Download: pick the real 1080p bitrate

yt-dlp's advertised bitrates can be wrong, and HLS formats are often mirrors of the DASH
ones. On one sermon, format 399 (AV1 1080p) was listed around 290 kb/s but actually
averaged about 2 Mbps, while format 137 (H.264 1080p DASH) measured 6.75 Mbps. HLS 614
and 270 were the same video as 248 (VP9) and 137. There is not always a 1440p or 4K
stream.

`pipeline/download_section.sh --measure-1080` probes each distinct 1080p video-only
format for a few seconds and keeps the one with the highest bitrate as measured by
ffprobe (file size / duration), then muxes it with the best audio. Pin a known winner
with `--format 137`. The default selector (no flag) still follows yt-dlp's own ranking.

### Cutting

List spans in output order with source times taken from the word timestamps (`pipeline/spans.example.json`).
`cut_spans.py` moves every cut to the quietest 10 ms frame within ±120 ms (`--snap`), so cuts land in pauses
and whole words survive; each span carries 20 ms extra so the crossfade doesn't eat speech, and the last span
gets a short tail fade. Always re-listen at the joins and re-transcribe the result. The last spoken word must
be heard in full.

### Loudness targets

- Speech: **-25.9 LUFS**. The default `--method sp90` moves the 90th percentile of short-term loudness to
  -25.9, which tracks the speaker better than integrated loudness when the clip has pauses. Use
  `--method integrated` to set integrated loudness to -25.9 instead. Static gain only, no compression.
- Soundtrack bed (optional): about **-41 LUFS** integrated (range -38 to -44), faded in (1 s) and out (2 s),
  mixed under the speech.
- True peak: under **-1 dBTP** (a limiter is applied only if needed).

### Caption rules

- Captions follow the clean script text, not the raw transcript; fix casing and punctuation there.
- Always capitalize **Allah, Tuhan, Yesus, Kristus, Roh Kudus**, and **Maha** when it refers to God
  (e.g. Maha Kuasa).
- Bible quotations use the exact Alkitab TB wording, in double quotes; the verse reference label
  (e.g. `Pengkhotbah 5:17–19`) is shown above the portrait while the verse is read. One passage
  label for the whole reading, centred above the red circle, then removed when the reading ends.
- Momo Trust Display 86 px, line height 86, font kerning (GPOS) with an `Al` -30 adjustment, centered,
  max width 960 px, 4 lines per page; only the word being spoken is red (#E8242B).

### Cover

Grab a clear speaking frame from the high-resolution download (file time 0 is the section start):

```sh
ffmpeg -y -ss 18 -i work/source.mp4 -frames:v 1 work/frames/speaker.png
```

Optional likeness-preserving upscale, then a rembg cutout. Real-ESRGAN x4plus (ONNX, CPU) is the
upscaler to use; image-generation "upscalers" change the face and are rejected. Run rembg on the
**original** HQ frame and apply that alpha to the ESRGAN colours — rembg on the 4x image can leak
background and miss hands. Weights are not in the repo (`pipeline/download_models.sh`).

```sh
python pipeline/upscale_esrgan.py work/frames/speaker.png \
  --crop 700,104,1300,619 -o work/frames/speaker_esrgan.png \
  --cutout work/frames/speaker_cut.png
```

Build the 9:16 cover with a smooth white sticker outline (~28 px, composited at 4x then
downscaled: fill holes, erode ~4 px, circular dilate, Gaussian blur, re-threshold; no white
lip along the bottom crop edge):

```sh
python pipeline/make_cover.py --rgb work/frames/speaker_esrgan.png \
  --cut work/frames/speaker_cut.png -o work/cover.png \
  --line "First line" --line "accent line|#E8242B" \
  --speaker-name "PDT. NAME" --title-font /path/to/ArchivoBlack-Regular.ttf
```

`--title-font` should be a heavy face such as Archivo Black (SIL OFL, not bundled here).
Without an outline, use `pipeline/make_cover_no_outline.py` with the same flags. The circular
in-video portrait can be rebuilt from the same sharpened frame with `pipeline/make_layout.py --portrait ...`.

The finished clip opens on this cover, then a 1-second eased colour wipe in the cover's colour.

## Quick start

```sh
./setup.sh                      # ffmpeg, yt-dlp, faster-whisper, DeepFilterNet, rembg, ESRGAN weights, Remotion deps
source .venv/bin/activate
mkdir work
pipeline/download_section.sh --measure-1080 "https://www.youtube.com/watch?v=VIDEO_ID" 41:04 52:00 work/source.mp4
python pipeline/transcribe.py work/source.mp4 -o work/source.words.json
# write work/spans.json from the transcript, then:
python pipeline/cut_spans.py work/spans.json --source work/source.mp4 --out work/footage.mp4
pipeline/denoise.sh work/footage.mp4 work/footage_dfn.mp4
python pipeline/loudness.py work/footage_dfn.mp4 work/footage_dfn_lufs.mp4
python pipeline/transcribe.py work/footage_dfn_lufs.mp4 -o work/words.json
# write work/clip-script.md; make a cover (see Cover) and a portrait (pipeline/make_layout.py --portrait ...)
```

## Render

Copy `remotion/clips/example.config.json` to `remotion/clips/<name>.config.json`, fill in the paths, then:

```sh
cd remotion
node scripts/build-props.mjs clips/<name>.config.json && npx remotion render SermonClip out/<name>.mp4 --props=clips/<name>.props.json --codec=h264 --crf=18
```

`npx remotion studio` previews the template. See `remotion/README.md` for the config fields and layout figures.

## Agent skills

Canonical recipes live in `skills/<name>/SKILL.md`. Identical copies (not symlinks) are kept in
`.claude/skills/`, `.cursor/skills/`, `.codex/skills/` and `.agents/skills/` (the path Codex
actually reads). After editing a canonical skill, run `scripts/sync-skills.sh`. Check copies
with `scripts/sync-skills.sh --check`. `AGENTS.md` and `CLAUDE.md` point at these skills.

| skill | use when |
|---|---|
| `sermon-clip-pipeline` | turning a YouTube sermon into a 9:16 captioned reel with this template |
| `sermon-clip-cover` | grabbing a frame, optional ESRGAN, rembg cutout, and the white sticker cover |
| `sermon-reel-hook-and-caption` | writing cover hooklines and Instagram / TikTok / Threads captions |

Do not commit sermon media, model weights, or non-shareable fonts. Do not post the clip to
social media from this pipeline.

## Licenses

Code: MIT (`LICENSE`). Fonts: SIL OFL 1.1 (`fonts/`). Real-ESRGAN weights (downloaded separately)
are BSD-3-Clause, [xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN). You are
responsible for having the rights to the sermon footage you process.
