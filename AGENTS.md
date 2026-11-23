# Agent instructions

This repository turns a YouTube sermon section into a 9:16 captioned reel. Read `README.md` first and run `./setup.sh`.

## Skills

Canonical skills live in `skills/<name>/SKILL.md`. Identical copies (not symlinks) are in `.claude/skills/`, `.cursor/skills/`, `.codex/skills/` and `.agents/skills/` (the path Codex actually reads). After you edit a skill, run `scripts/sync-skills.sh`. Check with `scripts/sync-skills.sh --check`.

Load the matching skill before you start:

- `sermon-clip-pipeline` — download, transcribe, cut, denoise, loudness, captions, render
- `sermon-clip-cover` — frame grab, optional Real-ESRGAN, rembg cutout, white sticker cover
- `sermon-reel-hook-and-caption` — cover hooklines and Instagram / TikTok / Threads captions

## Standing rules

- Speech at -25.9 LUFS; optional soundtrack bed about -41 LUFS (range -38 to -44) with fades; peaks below -1 dBTP. Clean speech with DeepFilterNet.
- Download the highest *real* 1080p bitrate (`pipeline/download_section.sh --measure-1080`); do not trust yt-dlp header bitrates.
- Captions: fix punctuation and casing; capitalize Allah, Tuhan, Yesus, Kristus, Roh Kudus, and Maha when it refers to God.
- Verse wording must match Alkitab TB exactly. Verse text at the top in quotes; one passage label for the whole reading, centered above the red circle.
- The clip opens on the cover, then a 1-second eased colour wipe in the cover's colour.
- The last spoken word must be heard in full.
- Work files stay local. The repo already ships the ESRGAN weights, the OFL fonts, and one example clip.
- Never post the clip to social media.
