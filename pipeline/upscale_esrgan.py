#!/usr/bin/env python3
"""CPU Real-ESRGAN x4 (ONNX) of a speaker crop, with an optional rembg cutout.

  python pipeline/upscale_esrgan.py work/frames/speaker.png \
      --crop 700,104,1300,619 -o work/frames/speaker_esrgan.png \
      --cutout work/frames/speaker_cut.png

The cutout (default --cutout-source original) runs rembg isnet-general-use on
the original HQ crop and applies that alpha to the ESRGAN colours. rembg on
the 4x image can leak background and miss hands. Do not replace this step
with an image-generation "upscaler": those change the speaker's likeness.

The ONNX weights are not in the repo. Run pipeline/download_models.sh, or
pass --model /path/to/RealESRGAN_x4plus.onnx.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cover_lib import parse_box

DEFAULT_MODEL = Path(__file__).resolve().parent / "models" / "RealESRGAN_x4plus.onnx"
SCALE = 4
DEFAULT_TILE = 128
DEFAULT_OVERLAP = 24
DEFAULT_PAD = 20


def padded_box(crop: tuple[int, int, int, int], frame_w: int, frame_h: int, pad: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = crop
    return (
        max(0, x0 - pad),
        max(0, y0 - pad),
        min(frame_w, x1 + pad),
        min(frame_h, y1 + pad),
    )


def upscale_tiled(rgb: np.ndarray, session: ort.InferenceSession, tile: int, overlap: int) -> np.ndarray:
    """rgb uint8 HxWx3 -> uint8 (4H)x(4W)x3."""
    h, w, _ = rgb.shape
    pre = overlap
    pad_h = (8 - (h + 2 * pre) % 8) % 8
    pad_w = (8 - (w + 2 * pre) % 8) % 8
    padded = np.pad(
        rgb,
        ((pre, pre + pad_h), (pre, pre + pad_w), (0, 0)),
        mode="reflect",
    )
    ph, pw, _ = padded.shape
    out = np.zeros((ph * SCALE, pw * SCALE, 3), dtype=np.float32)
    weight = np.zeros((ph * SCALE, pw * SCALE), dtype=np.float32)

    def window(th: int, tw: int) -> np.ndarray:
        wy = np.hanning(th)
        wx = np.hanning(tw)
        wy = np.clip(wy, 0.05, 1.0)
        wx = np.clip(wx, 0.05, 1.0)
        return np.outer(wy, wx).astype(np.float32)

    ys = list(range(0, max(1, ph - overlap), max(1, tile - overlap)))
    xs = list(range(0, max(1, pw - overlap), max(1, tile - overlap)))
    if ys[-1] + tile < ph:
        ys.append(ph - tile)
    if xs[-1] + tile < pw:
        xs.append(pw - tile)
    ys = sorted(set(max(0, min(y, max(0, ph - tile))) for y in ys))
    xs = sorted(set(max(0, min(x, max(0, pw - tile))) for x in xs))
    tiles = [(y, x) for y in ys for x in xs]
    print(f"input {w}x{h} padded {pw}x{ph} tiles {len(tiles)} tile={tile} overlap={overlap}")

    inp_name = session.get_inputs()[0].name
    t0 = time.time()
    for i, (y, x) in enumerate(tiles, 1):
        y1, x1 = min(y + tile, ph), min(x + tile, pw)
        # If the last tile is shorter than TILE, still run it (dynamic input).
        tile_im = padded[y:y1, x:x1]
        inp = tile_im.astype(np.float32).transpose(2, 0, 1)[None] / 255.0
        pred = session.run(None, {inp_name: inp})[0][0]  # 3, 4H, 4W
        pred = np.clip(pred.transpose(1, 2, 0), 0, 1)
        th, tw, _ = pred.shape
        win = window(th, tw)
        oy, ox = y * SCALE, x * SCALE
        out[oy : oy + th, ox : ox + tw] += pred * win[..., None]
        weight[oy : oy + th, ox : ox + tw] += win
        if i == 1 or i == len(tiles) or i % 5 == 0:
            print(f"  tile {i}/{len(tiles)} elapsed {time.time() - t0:.1f}s", flush=True)

    weight = np.maximum(weight, 1e-6)
    result = out / weight[..., None]
    top = pre * SCALE
    left = pre * SCALE
    result = result[top : top + h * SCALE, left : left + w * SCALE]
    return (np.clip(result, 0, 1) * 255.0 + 0.5).astype(np.uint8)


def rembg_cut(im: Image.Image) -> Image.Image:
    from rembg import new_session, remove

    print("rembg isnet-general-use")
    t1 = time.time()
    session = new_session("isnet-general-use")
    cut = remove(im, session=session)
    if not isinstance(cut, Image.Image):
        cut = Image.fromarray(cut)
    print(f"  rembg in {time.time() - t1:.1f}s")
    return cut.convert("RGBA")


def apply_alpha(rgb: Image.Image, alpha_src: Image.Image) -> Image.Image:
    a = alpha_src.convert("RGBA").split()[-1]
    if a.size != rgb.size:
        a = a.resize(rgb.size, Image.Resampling.LANCZOS)
    return Image.merge("RGBA", (*rgb.convert("RGB").split(), a))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="source frame (PNG/JPEG), typically a 1080p still")
    ap.add_argument("-o", "--out", required=True, help="exact (unpadded) 4x RGB crop")
    ap.add_argument("--crop", help="x0,y0,x1,y1 region to upscale; default is the full frame")
    ap.add_argument("--pad", type=int, default=DEFAULT_PAD, help="extra pixels around the crop for context")
    ap.add_argument("--model", default=os.environ.get("REALESRGAN_ONNX", str(DEFAULT_MODEL)))
    ap.add_argument("--tile", type=int, default=DEFAULT_TILE)
    ap.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP)
    ap.add_argument("--threads", type=int, default=min(8, os.cpu_count() or 8))
    ap.add_argument("--cutout", help="write an RGBA PNG of the exact crop with rembg alpha")
    ap.add_argument(
        "--cutout-source",
        choices=["original", "upscaled"],
        default="original",
        help="rembg the original HQ crop (default) or the 4x ESRGAN image (discouraged)",
    )
    a = ap.parse_args()

    model = Path(a.model)
    if not model.is_file():
        raise SystemExit(
            f"ESRGAN ONNX not found: {model}\n"
            f"Run pipeline/download_models.sh, or pass --model /path/to/RealESRGAN_x4plus.onnx"
        )

    src = Image.open(a.input).convert("RGB")
    crop = parse_box(a.crop) if a.crop else (0, 0, src.width, src.height)
    box = padded_box(crop, *src.size, a.pad)
    print("padded crop box", box, "size", box[2] - box[0], "x", box[3] - box[1])
    pad_crop = src.crop(box)

    print("loading", model)
    so = ort.SessionOptions()
    so.intra_op_num_threads = a.threads
    session = ort.InferenceSession(str(model), sess_options=so, providers=["CPUExecutionProvider"])
    t0 = time.time()
    up = upscale_tiled(np.array(pad_crop), session, tile=a.tile, overlap=a.overlap)
    del session
    up_im = Image.fromarray(up, "RGB")
    print("upscaled", up_im.size, f"in {time.time() - t0:.1f}s")

    # Exact cover-region crop at 4x (no pad).
    x0, y0, x1, y1 = crop
    px0, py0, _, _ = box
    cx0 = (x0 - px0) * SCALE
    cy0 = (y0 - py0) * SCALE
    cx1 = (x1 - px0) * SCALE
    cy1 = (y1 - py0) * SCALE
    exact_rgb = up_im.crop((cx0, cy0, cx1, cy1))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    exact_rgb.save(out)
    print("wrote", out, exact_rgb.size)

    if a.cutout:
        if a.cutout_source == "upscaled":
            print("warning: rembg on the 4x image can leak background and miss hands; prefer --cutout-source original")
            cut_pad = rembg_cut(up_im)
            exact_cut = cut_pad.crop((cx0, cy0, cx1, cy1))
            # Keep ESRGAN colours; use only the 4x rembg alpha.
            exact_cut = apply_alpha(exact_rgb, exact_cut)
        else:
            cut_pad = rembg_cut(pad_crop)
            # Crop to the exact region at 1x, then resize alpha onto the 4x RGB.
            ex0, ey0 = x0 - px0, y0 - py0
            ex1, ey1 = x1 - px0, y1 - py0
            exact_cut_1x = cut_pad.crop((ex0, ey0, ex1, ey1))
            exact_cut = apply_alpha(exact_rgb, exact_cut_1x)
        cut_path = Path(a.cutout)
        cut_path.parent.mkdir(parents=True, exist_ok=True)
        exact_cut.save(cut_path)
        print("wrote", cut_path, exact_cut.size)


if __name__ == "__main__":
    main()
