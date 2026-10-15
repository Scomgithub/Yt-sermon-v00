# Yt-sermon

Turns a section of a recorded sermon on YouTube into a 1080x1920 vertical clip: audio-driven cuts,
noise reduction, matched loudness, word-by-word captions (the spoken word in red), an audio spectrum,
the speaker's portrait, a Bible-verse label and a cover + colour-wipe intro. The final video is rendered
with [Remotion](https://www.remotion.dev) from a JSON props file.

## Pipeline

| step | tool | script |
|---|---|---|
| 1. download the section | yt-dlp | `pipeline/download_section.sh <url> <start> <end> work/source.mp4` |
| 2. transcribe with word timestamps | faster-whisper | `pipeline/transcribe.py work/source.mp4 -o work/source.words.json --lang id` |
| 3. pick spans, cut in pauses, 20 ms audio crossfades | ffmpeg + numpy | `pipeline/cut_spans.py spans.json --source work/source.mp4 --out work/footage.mp4` |
| 4. noise reduction | DeepFilterNet3 | `pipeline/denoise.sh work/footage.mp4 work/footage_dfn.mp4` |
| 5. loudness (+ optional music bed) | ffmpeg ebur128 | `pipeline/loudness.py work/footage_dfn.mp4 work/footage_dfn_lufs.mp4 [--bed music.mp3]` |
| 6. re-transcribe the cut for caption timing | faster-whisper | `pipeline/transcribe.py work/footage_dfn_lufs.mp4 -o work/words.json` |
| 7. write the clean caption text | you | `work/clip-script.md` (paragraphs; the verse in "double quotes") |
| 8. render | Remotion | see Quick start |

Optional standalone renderers (overlays for an NLE such as CapCut): `pipeline/render_captions.py`
(caption sprites, Momo Trust Display with fontTools GPOS kerning), `pipeline/render_wipe.py`
(eased colour wipe), `pipeline/make_layout.py` (background, blue shape, red circle, circular portrait).

### Cutting

List spans in output order with source times taken from the word timestamps (`pipeline/spans.example.json`).
`cut_spans.py` moves every cut to the quietest 10 ms frame within ±120 ms (`--snap`), so cuts land in pauses
and whole words survive; each span carries 20 ms extra so the crossfade doesn't eat speech, and the last span
gets a short tail fade. Always re-listen at the joins and re-transcribe the result.

### Loudness targets

- Speech: **-25.9 LUFS**. The default `--method sp90` moves the 90th percentile of short-term loudness to
  -25.9, which tracks the speaker better than integrated loudness when the clip has pauses. Use
  `--method integrated` to set integrated loudness to -25.9 instead. Static gain only, no compression.
- Soundtrack bed (optional): about **-41 LUFS** integrated, faded in (1 s) and out (2 s), mixed under the speech.
- True peak: under **-1 dBTP** (a limiter is applied only if needed).

### Caption rules

- Captions follow the clean script text, not the raw transcript; fix casing and punctuation there.
- Always capitalize **Allah, Tuhan, Yesus, Kristus, Roh Kudus**, and **Maha** when it refers to God
  (e.g. Maha Kuasa).
- Bible quotations use the exact Alkitab TB wording, in double quotes; the verse reference label
  (e.g. `Pengkhotbah 5:17–19`) is shown above the portrait while the verse is read.
- Momo Trust Display 86 px, line height 86, font kerning (GPOS) with an `Al` -30 adjustment, centered,
  max width 960 px, 4 lines per page; only the word being spoken is red (#E8242B).

## Quick start

```sh
./setup.sh                      # ffmpeg, yt-dlp, faster-whisper, DeepFilterNet (.venv), Remotion deps
source .venv/bin/activate
mkdir work
pipeline/download_section.sh "https://www.youtube.com/watch?v=VIDEO_ID" 41:04 52:00 work/source.mp4
python pipeline/transcribe.py work/source.mp4 -o work/source.words.json
# write work/spans.json from the transcript, then:
python pipeline/cut_spans.py work/spans.json --source work/source.mp4 --out work/footage.mp4
pipeline/denoise.sh work/footage.mp4 work/footage_dfn.mp4
python pipeline/loudness.py work/footage_dfn.mp4 work/footage_dfn_lufs.mp4
python pipeline/transcribe.py work/footage_dfn_lufs.mp4 -o work/words.json
# write work/clip-script.md; make a portrait and a cover (pipeline/make_layout.py --portrait ...)
```

## Render

Copy `remotion/clips/example.config.json` to `remotion/clips/<name>.config.json`, fill in the paths, then:

```sh
cd remotion
node scripts/build-props.mjs clips/<name>.config.json && npx remotion render SermonClip out/<name>.mp4 --props=clips/<name>.props.json --codec=h264 --crf=18
```

`npx remotion studio` previews the template. See `remotion/README.md` for the config fields and layout figures.

## Licenses

Code: MIT (`LICENSE`). Fonts: SIL OFL 1.1 (`fonts/`). You are responsible for having the rights to the
sermon footage you process.
