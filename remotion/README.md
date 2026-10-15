# remotion-sermon

A reusable 1080x1920 / 30 fps sermon-clip template that reproduces the 04b layout (the original CapCut build).
It does not touch CapCut.

## Render a new clip (one command)

```sh
cd remotion
node scripts/build-props.mjs clips/<name>.config.json && npx remotion render SermonClip out/<name>.mp4 --props=clips/<name>.props.json --codec=h264 --crf=18
```

Preview interactively with `npx remotion studio` (it opens with `clips/default-props.json`).
A single frame: `npx remotion still SermonClip out/f.png --frame=1500 --props=clips/<name>.props.json`.

## Config (input to build-props.mjs)

```json
{
  "name": "my-clip",
  "audio": "/abs/footage_dfn_lufs.mp4",          // the final cut; its audio is used
  "words": "/abs/words.json",                     // faster-whisper output (segments[].words or words[])
  "script": "/abs/clip-script.md",                // clean caption text; paragraphs; the verse in "double quotes"
  "timeline": "/abs/words_timeline.json",         // optional: hand-fixed word timeline; skips the alignment
  "title": "Judul Klip Di Sini?",
  "speakerName": "PDT. NAMA PEMBICARA",
  "portrait": "/abs/portrait_color.png",          // full-frame 1080x1920 PNG with the circle face (as in the CapCut build)
  "cover": "/abs/cover.png",                      // full-frame cover, held 0.5 s then wiped
  "coverColor": "#E8242B",                        // wipe colour
  "spectrumVideo": "/abs/spectrum_bidi3.mov",     // optional; omit to draw live bars with visualizeAudio
  "verses": [{"startsWith": "Lorem", "ref": "Kitab 1:1–3"}],
  "soundtrack": {"path": "/abs/music.mp3", "gainDb": -18, "fadeIn": 1, "fadeOut": 2},   // or null
  "layout": {}                                    // optional overrides of the layout figures below
}
```

The script aligns clip-script.md to the whisper words (merges such as `kuanggap` = `aku`+`anggap` are handled;
unmatched words get interpolated times and are printed as warnings). A quoted span whose first word matches
`verses[].startsWith` gets the verse label and forced page breaks before and after it. Captions are laid out
exactly like `render_captions_momo.py`: Momo Trust Display 86 px, line height 86, GPOS kerning plus the `Al`
-30 override, greedy wrap at 960 px, 4 lines per page, a page shows from the end of the previous page's last word.

## Layout figures (scripts/build-props.mjs, `L`)

| layer | figure |
|---|---|
| timing | cover 0–1.0 s, wipe 0.5–1.5 s (cubic in-out, sweeps on then off L→R), layout from 1.0 s, audio/captions/spectrum from 1.5 s |
| background / blue shape / red circle | `public/layout/{bg,blue,red_circle}.png` (regenerate with `pipeline/make_layout.py`) |
| title | Archivo-Medium 34 px, tracking 6, no kerning, black, centred, baseline 138.5 |
| captions | first baseline 70+150+89+116.1+1.5 ≈ 426.6, line height 86, black, spoken word #E8242B |
| spectrum | 20 bars, width 16, pitch 34, x 33… and 729…, centre line 1302 moved up 223.7 px (≈1078) |
| portrait | full-frame PNG scaled 1.16593 about the canvas centre, moved up 31.3 px |
| speaker name | Archivo-SemiBold 30 px, tracking 7.6, white, centred, baseline 1668 |
| verse label | Archivo-Medium 34 px, GPOS kerning, no tracking, black, centred x 540, baseline 802.5 |

## Files

- `src/SermonClip.tsx` – the composition (layers in CapCut track order)
- `src/types.ts` – props schema
- `scripts/build-props.mjs` – config → props + assets in `public/clips/<name>/`
- `clips/example.config.json` / `example.props.json` – example with placeholder paths and dummy words (the props point at `public/clips/example/`, which is not in the repo; run build-props first)
