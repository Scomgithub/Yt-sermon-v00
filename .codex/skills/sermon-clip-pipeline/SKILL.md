---
name: sermon-clip-pipeline
description: >-
  Use when turning a YouTube sermon into a 9:16 captioned reel with the
  Yt-sermon-v00 Remotion template.
---
# Sermon clip pipeline

Read this repository's `README.md` first and run `./setup.sh`. The work needs ffmpeg, yt-dlp, Python (faster-whisper, DeepFilterNet, rembg, onnxruntime, OpenCV), Node 18+ and Remotion. Paths below are repo-relative. Do not commit sermon media, model weights, or non-shareable fonts.

For the cover still, also load `sermon-clip-cover`. For hooklines and social captions, load `sermon-reel-hook-and-caption`.

## Steps
1. Download the requested section with the highest *real* 1080p bitrate: `pipeline/download_section.sh --measure-1080 <url> <start> <end> work/source.mp4`. yt-dlp header bitrates can mislead (one AV1 1080p stream advertised ~290 kb/s but averaged ~2 Mbps, while H.264 format 137 measured 6.75 Mbps). HLS formats 614/270 are mirrors of 248/137. Measure with ffprobe on a short probe; pin a known winner with `--format`. File time 0 is `<start>` in the source video.
2. Transcribe with word timestamps (`pipeline/transcribe.py`, faster-whisper medium). Check sync against the waveform; re-transcribe the region if timing drifts.
3. Break the transcript into major beats and send them, uncut, for the owner to pick.
4. Draft the reel script from the chosen beat(s). On every revision send the whole script, never a list of what was kept or cut. Get approval before cutting.
5. Write a catchphrase that is a question viewers really ask themselves, not a summary. Open the video with the punchline line that answers it. See `sermon-reel-hook-and-caption`.
6. Make a 9:16 cover still from the high-resolution download (frame grab, optional Real-ESRGAN, rembg cutout, white sticker outline). See `sermon-clip-cover`. The clip opens on this cover, then a 1-second eased colour wipe in the cover's colour.
7. Cut spans (`pipeline/cut_spans.py`, listen at the joins, keep the last spoken word fully audible), denoise (`pipeline/denoise.sh`, DeepFilterNet), set loudness (`pipeline/loudness.py`).
8. Build props and render: `cd remotion && node scripts/build-props.mjs clips/<name>.config.json && npx remotion render SermonClip out/<name>.mp4 --props=clips/<name>.props.json --codec=h264 --crf=18`.

## Rules
- Speech at -25.9 LUFS; optional soundtrack bed about -41 LUFS (range -38 to -44), always faded in and out; peaks below -1 dBTP. Clean the voice with DeepFilterNet before the loudness step.
- Captions: fix periods, commas and casing; capitalize Allah, Tuhan, Yesus, Kristus, Roh Kudus, and Maha when it refers to God.
- Intro: cover first, then a 1-second eased color wipe in the cover's background color into the normal layout.
- Scripture: keep the speaker's lead-in line ("Mari kita membaca..."). Verse text at the top in quotes, worded exactly as Alkitab TB (check the published text). One passage reference for the whole reading, centered above the red circle in the small title font, removed when the reading ends.
- The last spoken word must be heard in full.
- Never post the clip to social media.
