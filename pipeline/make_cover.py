#!/usr/bin/env python3
"""9:16 cover with a thick, smooth white sticker outline around the speaker.

  python pipeline/make_cover.py --rgb work/frames/speaker_esrgan.png \
      --cut work/frames/speaker_cut.png -o work/cover.png \
      --line "First line" --line "accent|#E8242B" --speaker-name "PDT. NAME" \
      --title-font /path/to/ArchivoBlack-Regular.ttf

Prefer Real-ESRGAN colours in --rgb and rembg alpha from the original HQ
frame in --cut. rembg on the 4x image can leak background and miss hands.
If you do have a 4x rembg, pass it as --cut and the original-frame rembg as
--guide (with --guide-crop if the guide is still a full frame).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image

from cover_lib import (
    DEFAULT_NAME_FONT,
    THICKNESS,
    add_cover_cli,
    compose_cover,
    make_speaker_layer,
    parse_box,
    parse_lines,
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_cover_cli(ap)
    ap.add_argument("--guide", help="optional approved silhouette (HQ-frame rembg) used to clip leaks")
    ap.add_argument("--guide-crop", help="x0,y0,x1,y1 crop for --guide when it is a full frame")
    ap.add_argument("--thickness", type=int, default=THICKNESS, help="outline width in cover pixels (default 28)")
    ap.add_argument("--no-hand-gap-clean", action="store_true", help="skip the raised-finger gap cleanup")
    ap.add_argument("--no-left-clip", action="store_true", help="allow the outline to reach the left edge")
    ap.add_argument("--debug-dir", help="write subject/outline debug PNGs here")
    a = ap.parse_args()

    crop = parse_box(a.crop) if a.crop else None
    cut = Image.open(a.cut)
    if crop:
        cut = cut.crop(crop)
    if a.rgb:
        rgb = Image.open(a.rgb)
        if crop:
            rgb = rgb.crop(crop)
    else:
        rgb = cut.convert("RGB")

    speaker = make_speaker_layer(
        rgb,
        cut,
        guide_path=Path(a.guide) if a.guide else None,
        guide_crop=parse_box(a.guide_crop) if a.guide_crop else None,
        thickness=a.thickness,
        clean_hand_gaps=not a.no_hand_gap_clean,
        clip_left=not a.no_left_clip,
        debug_dir=Path(a.debug_dir) if a.debug_dir else None,
    )
    cover = compose_cover(
        speaker,
        lines=parse_lines(a.lines),
        speaker_name=a.speaker_name or None,
        title_font=Path(a.title_font) if a.title_font else None,
        name_font=Path(a.name_font) if a.name_font else DEFAULT_NAME_FONT,
        decorations=not a.no_decorations,
    )
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cover.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
