#!/usr/bin/env python3
"""9:16 cover with the speaker cutout and no sticker outline.

  python pipeline/make_cover_no_outline.py --cut work/frames/speaker_cut.png \
      --crop 700,104,1300,619 -o work/cover.png \
      --line "First line" --speaker-name "PDT. NAME"

Pass --rgb when the colours should come from a Real-ESRGAN crop and --cut
holds the rembg of the original HQ frame (likeness-preserving upscale).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image

from cover_lib import (
    DEFAULT_NAME_FONT,
    add_cover_cli,
    compose_cover,
    make_speaker_layer_no_outline,
    parse_box,
    parse_lines,
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_cover_cli(ap)
    a = ap.parse_args()

    crop = parse_box(a.crop) if a.crop else None
    cut = Image.open(a.cut)
    if crop:
        cut = cut.crop(crop)
    rgb = None
    if a.rgb:
        rgb = Image.open(a.rgb)
        if crop:
            rgb = rgb.crop(crop)

    speaker = make_speaker_layer_no_outline(cut, rgb_src=rgb)
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
