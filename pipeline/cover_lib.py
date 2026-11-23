#!/usr/bin/env python3
"""Shared cover-layout and white-sticker-outline helpers.

The outline is built at 4x, then downscaled: holes in the rembg mask are filled,
the subject is eroded ~4 px so the white stroke does not eat into the person,
a circular dilation grows a ~28 px sticker, a heavy Gaussian blur plus
re-threshold rounds jaggies, and the mask is virtually extended past a hard
bottom crop so no white lip runs along that edge.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 1080, 1920
RED = (232, 36, 43)
CREAM = (246, 241, 229)
YEL = (244, 196, 14)
BLACK = (0, 0, 0)
BOUND = 928

# Sticker outline in cover pixels. 2–3% of 1080 is 22–32 px; 28 sits in the middle
# and measures about 29 px on a typical speaker silhouette.
THICKNESS = 28
SCALE = 4  # supersample for a smooth, anti-aliased outer edge
CLOSE_RADIUS = 16  # fill small concave gaps; not a large raised-arm opening
ROUND_SIGMA = 6  # heavy blur before re-threshold, rounds stair-steps
AA_SIGMA = 1.1  # final outline AA in cover pixels
SUBJECT_ERODE = 4  # drop rembg fringe; the white outline covers this
SUBJECT_ROUND_SIGMA = 1.5
SUBJECT_AA_SIGMA = 0.8
GUIDE_DILATE = 8  # cover pixels of slack around an approved silhouette
LEFT_CLIP_SLACK = 3  # allow this many px beyond THICKNESS on the left edge
LEFT_CLIP_STRIP = 90

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NAME_FONT = REPO_ROOT / "fonts/Archivo/Archivo-SemiBold.ttf"
DEFAULT_TITLE_FONT = DEFAULT_NAME_FONT


def parse_color(s: str) -> tuple[int, int, int]:
    s = s.strip()
    named = {"black": BLACK, "red": RED, "cream": CREAM, "yellow": YEL, "white": (255, 255, 255)}
    if s.lower() in named:
        return named[s.lower()]
    if s.startswith("#") and len(s) == 7:
        return int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16)
    parts = [int(x) for x in s.replace(" ", "").split(",")]
    if len(parts) != 3:
        raise ValueError(f"color must be #RRGGBB or r,g,b: {s}")
    return parts[0], parts[1], parts[2]


def parse_box(s: str) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = (int(x) for x in s.replace(" ", "").split(","))
    return x0, y0, x1, y1


def parse_lines(items: list[str]) -> list[tuple[str, tuple[int, int, int]]]:
    """Each item is 'text' (black) or 'text|#RRGGBB' / 'text|red'."""
    out = []
    for raw in items or []:
        if "|" in raw:
            text, color = raw.rsplit("|", 1)
            out.append((text, parse_color(color)))
        else:
            out.append((raw, BLACK))
    return out


def _ellipse(radius: int) -> np.ndarray:
    k = max(1, int(radius) * 2 + 1)
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))


def _keep_large_and_fill_holes(binary: np.ndarray, min_area: int, keep_largest_only: bool = True) -> np.ndarray:
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    clean = np.zeros_like(binary)
    if n <= 1:
        return clean
    if keep_largest_only:
        main = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        if stats[main, cv2.CC_STAT_AREA] >= min_area:
            clean[labels == main] = 255
    else:
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] >= min_area:
                clean[labels == i] = 255
    inv = 255 - clean
    n2, lab2, _, _ = cv2.connectedComponentsWithStats(inv, connectivity=8)
    h, w = clean.shape
    filled = clean.copy()
    for i in range(1, n2):
        ys, xs = np.where(lab2 == i)
        if ys.size == 0:
            continue
        if ys.min() <= 0 or xs.min() <= 0 or ys.max() >= h - 1 or xs.max() >= w - 1:
            continue
        filled[lab2 == i] = 255
    return filled


def remove_hand_gap_gunk(mask: np.ndarray, rgb: np.ndarray, scale: int = SCALE) -> np.ndarray:
    """Clear leftover stage-black between raised fingers.

    Find the raised-hand skin, close/hull it to cover the finger gaps, then drop
    any dark pixels in that region that are reachable from the background.
    The rest of the body (hair, dark shirt) is left alone.
    """
    r = rgb[:, :, 0].astype(np.int16)
    g = rgb[:, :, 1].astype(np.int16)
    b = rgb[:, :, 2].astype(np.int16)
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    skin = (
        (r > 60) & (r > g) & (r > b) & ((r - g) > 8) & (luma > 50) & (mask > 0)
    ).astype(np.uint8) * 255
    skin = cv2.morphologyEx(skin, cv2.MORPH_CLOSE, _ellipse(3 * scale))
    n, lab, st, _ = cv2.connectedComponentsWithStats(skin, connectivity=8)
    best, best_x = None, -1
    min_area = 2000 * scale * scale
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] >= min_area:
            cx = st[i, cv2.CC_STAT_LEFT] + st[i, cv2.CC_STAT_WIDTH] / 2.0
            if cx > best_x:
                best_x, best = cx, i
    if best is None:
        return mask
    hand = (lab == best).astype(np.uint8) * 255
    # The skin CC often leaks down the dark shirt. Clip it at the wrist:
    # after the palm's widest row, take the following width minimum.
    row_counts = hand.sum(axis=1)
    ys = np.where(row_counts > 0)[0]
    if ys.size == 0:
        return mask
    y_top = int(ys.min())
    peak_end = min(int(y_top + 250 * scale), int(ys.max()) + 1)
    peak_y = y_top + int(np.argmax(row_counts[y_top:peak_end]))
    search_end = min(peak_y + 100 * scale, int(ys.max()) + 1)
    wrist_y = peak_y + int(np.argmin(row_counts[peak_y:search_end]))
    hand[wrist_y + 1 :, :] = 0

    closed = cv2.morphologyEx(hand, cv2.MORPH_CLOSE, _ellipse(25 * scale))
    hull = np.zeros_like(hand)
    cnts, _ = cv2.findContours(hand, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cnts:
        if c.size == 0:
            continue
        cv2.drawContours(hull, [cv2.convexHull(c)], -1, 255, -1)
    region = ((closed > 0) | (hull > 0)).astype(np.uint8)

    perm = (((luma < 110) & (region > 0)) | (mask == 0)).astype(np.uint8) * 255
    n, lab, _, _ = cv2.connectedComponentsWithStats(perm, connectivity=8)
    bg_labels = np.unique(lab[mask == 0])
    reachable = np.isin(lab, bg_labels)
    out = mask.copy()
    out[reachable] = 0
    return out


def load_guide_mask(
    path: Path,
    size: tuple[int, int],
    crop: tuple[int, int, int, int] | None = None,
    dilate: int = 0,
    scale: int = SCALE,
) -> np.ndarray:
    """Approved silhouette (e.g. rembg on the original HQ frame), resized to the working mask."""
    g = Image.open(path).convert("RGBA")
    if crop:
        g = g.crop(crop)
    g = g.resize(size, Image.Resampling.BILINEAR)
    binary = (np.array(g.split()[-1]) >= 128).astype(np.uint8) * 255
    if dilate:
        binary = cv2.dilate(binary, _ellipse(dilate * scale))
    return binary


def clean_subject_mask(
    alpha: np.ndarray,
    rgb: np.ndarray,
    guide: np.ndarray | None = None,
    scale: int = SCALE,
    clean_hand_gaps: bool = True,
) -> np.ndarray:
    """Binary subject mask at supersampled res: no specks, holes filled, fringe eroded.

    If a guide silhouette is given (rembg of the original HQ frame), union it
    with the provided alpha after clipping new leaks to a dilated copy of the
    guide. rembg on a 4x ESRGAN image can leak background and miss hands;
    prefer the original-frame alpha as --cut, and use --guide only when you
    also have a 4x rembg you want to restrain.
    """
    binary = (alpha >= 128).astype(np.uint8) * 255
    if guide is not None:
        loose = cv2.dilate(guide, _ellipse(GUIDE_DILATE * scale))
        binary = cv2.bitwise_or(cv2.bitwise_and(binary, loose), guide)
    min_area = 800 * scale * scale
    filled = _keep_large_and_fill_holes(binary, min_area)
    filled = cv2.morphologyEx(filled, cv2.MORPH_CLOSE, _ellipse(2 * scale))
    if clean_hand_gaps:
        filled = remove_hand_gap_gunk(filled, rgb, scale=scale)
        filled = _keep_large_and_fill_holes(filled, min_area)
    eroded = cv2.erode(filled, _ellipse(SUBJECT_ERODE * scale))
    rounded = cv2.GaussianBlur(eroded, (0, 0), SUBJECT_ROUND_SIGMA * scale)
    return (rounded >= 128).astype(np.uint8) * 255


def build_outline_alpha(
    subject_mask: np.ndarray,
    thickness: int = THICKNESS,
    scale: int = SCALE,
) -> np.ndarray:
    """Dilated, heavily rounded white-sticker mask with a soft AA edge.

    The body is hard-cropped at the bottom of the red panel. We virtually
    extend the mask downward before dilating/blurring, then crop back, so no
    white lip runs along that cut and the side outlines meet the panel edge.
    """
    h, w = subject_mask.shape
    t = thickness * scale
    close_r = CLOSE_RADIUS * scale
    pad = t + close_r + int(8 * ROUND_SIGMA * scale)

    padded = cv2.copyMakeBorder(subject_mask, 0, pad, 0, 0, cv2.BORDER_CONSTANT, value=0)
    bottom_on = subject_mask[-1] > 127
    if np.any(bottom_on):
        padded[h : h + pad, bottom_on] = 255

    dist = cv2.distanceTransform(255 - padded, cv2.DIST_L2, 5)
    dilated = ((padded > 0) | (dist <= t)).astype(np.uint8) * 255
    closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, _ellipse(close_r))
    rounded = cv2.GaussianBlur(closed, (0, 0), ROUND_SIGMA * scale)
    hard = (rounded >= 100).astype(np.uint8) * 255
    aa = cv2.GaussianBlur(hard, (0, 0), AA_SIGMA * scale)
    aa = aa[:h, :w]
    if np.any(bottom_on):
        aa[-1, bottom_on] = 255
    return aa


def clip_left_outline_overshoot(
    outline: np.ndarray,
    subject: np.ndarray,
    thickness: int = THICKNESS,
    scale: int = SCALE,
) -> np.ndarray:
    """Stop close/round from pushing a white hook past the left edge (e.g. near an elbow)."""
    dist = cv2.distanceTransform((subject < 128).astype(np.uint8) * 255, cv2.DIST_L2, 5)
    maxd = (thickness + LEFT_CLIP_SLACK) * scale
    aa = 2.0 * scale
    strip = LEFT_CLIP_STRIP * scale
    falloff = np.clip((maxd + aa - dist[:, :strip]) / aa, 0.0, 1.0)
    out = outline.copy()
    out[:, :strip] = (out[:, :strip].astype(np.float32) * falloff).astype(np.uint8)
    return out


def subject_alpha_aa(subject_mask: np.ndarray, scale: int = SCALE) -> np.ndarray:
    aa = cv2.GaussianBlur(subject_mask, (0, 0), SUBJECT_AA_SIGMA * scale)
    bottom_on = subject_mask[-1] > 127
    if np.any(bottom_on):
        aa[-1, bottom_on] = 255
    return aa


def defringe_rgb(rgb: np.ndarray, alpha: np.ndarray, radius: int = 3) -> np.ndarray:
    """Replace contaminated edge pixels with interior color so no dark halo shows on white."""
    solid = (alpha >= 128).astype(np.uint8)
    interior = cv2.erode(solid, _ellipse(radius))
    edge = (solid > 0) & (interior == 0)
    if not np.any(edge):
        return rgb
    inpaint_mask = edge.astype(np.uint8) * 255
    canvas = rgb.copy()
    canvas[interior == 0] = 0
    painted = cv2.inpaint(
        canvas,
        (inpaint_mask | ((interior == 0) & (solid == 0)).astype(np.uint8) * 255),
        radius + 2,
        cv2.INPAINT_TELEA,
    )
    out = rgb.copy()
    out[edge] = painted[edge]
    return out


def downscale_u8(arr: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    return np.array(Image.fromarray(arr).resize(size, Image.Resampling.LANCZOS))


def enhance_speaker_rgb(rgb: np.ndarray) -> np.ndarray:
    im = Image.fromarray(rgb)
    im = ImageEnhance.Contrast(im).enhance(1.08)
    im = ImageEnhance.Color(im).enhance(1.1)
    im = im.filter(ImageFilter.UnsharpMask(2, 80, 2))
    return np.array(im)


def make_speaker_layer(
    rgb_src: Image.Image,
    cut: Image.Image,
    *,
    guide_path: Path | None = None,
    guide_crop: tuple[int, int, int, int] | None = None,
    thickness: int = THICKNESS,
    scale: int = SCALE,
    clean_hand_gaps: bool = True,
    clip_left: bool = True,
    debug_dir: Path | None = None,
) -> Image.Image:
    """1080xBOUND RGBA: white sticker under the cleaned subject, transparent elsewhere."""
    rgb_src = rgb_src.convert("RGB")
    cut = cut.convert("RGBA")
    sw, sh = W * scale, BOUND * scale

    hi_rgb = np.array(rgb_src.resize((sw, sh), Image.Resampling.LANCZOS))
    hi_alpha = np.array(cut.split()[-1].resize((sw, sh), Image.Resampling.LANCZOS))
    guide = load_guide_mask(guide_path, (sw, sh), crop=guide_crop, dilate=0, scale=scale) if guide_path else None
    subject_mask = clean_subject_mask(hi_alpha, hi_rgb, guide=guide, scale=scale, clean_hand_gaps=clean_hand_gaps)
    outline_hi = build_outline_alpha(subject_mask, thickness=thickness, scale=scale)
    if clip_left:
        outline_hi = clip_left_outline_overshoot(outline_hi, subject_mask, thickness=thickness, scale=scale)
    subj_hi = subject_alpha_aa(subject_mask, scale=scale)

    outline_1x = downscale_u8(outline_hi, (W, BOUND))
    subj_1x = downscale_u8(subj_hi, (W, BOUND))

    rgb = np.array(rgb_src.resize((W, BOUND), Image.Resampling.LANCZOS))
    rgb = defringe_rgb(rgb, subj_1x, radius=3)
    rgb = enhance_speaker_rgb(rgb)

    layer = np.zeros((BOUND, W, 4), dtype=np.uint8)
    src_a = subj_1x.astype(np.float32) / 255.0
    dst_a = outline_1x.astype(np.float32) / 255.0
    out_alpha = src_a + dst_a * (1.0 - src_a)
    with np.errstate(divide="ignore", invalid="ignore"):
        for c in range(3):
            src = rgb[..., c].astype(np.float32)
            dst = 255.0
            comp = (src * src_a + dst * dst_a * (1.0 - src_a)) / np.maximum(out_alpha, 1e-6)
            layer[..., c] = np.clip(comp, 0, 255).astype(np.uint8)
    layer[..., 3] = np.clip(out_alpha * 255.0, 0, 255).astype(np.uint8)

    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)
        Image.fromarray(downscale_u8(subject_mask, (W, BOUND))).save(debug_dir / "debug_subject_mask.png")
        Image.fromarray(outline_1x).save(debug_dir / "debug_outline_mask.png")
        Image.fromarray(layer, "RGBA").save(debug_dir / "debug_speaker_layer.png")

    sub_bin = (subj_1x >= 128).astype(np.uint8)
    out_bin = (outline_1x >= 128).astype(np.uint8)
    dist = cv2.distanceTransform((1 - sub_bin).astype(np.uint8) * 255, cv2.DIST_L2, 5)
    kernel = np.ones((3, 3), np.uint8)
    outer = (out_bin == 1) & (cv2.dilate(1 - out_bin, kernel) == 1)
    outer[-3:, :] = 0
    edge_d = dist[outer]
    if edge_d.size:
        print(
            f"outline thickness px: mean={edge_d.mean():.1f} median={np.median(edge_d):.1f} "
            f"p10={np.percentile(edge_d, 10):.1f} p90={np.percentile(edge_d, 90):.1f}  target={thickness}"
        )
    return Image.fromarray(layer, "RGBA")


def make_speaker_layer_no_outline(
    cut: Image.Image,
    rgb_src: Image.Image | None = None,
) -> Image.Image:
    """1080xBOUND RGBA speaker, no sticker outline."""
    cut = cut.convert("RGBA")
    p = cut.resize((W, BOUND), Image.Resampling.LANCZOS)
    if rgb_src is not None:
        rgb = rgb_src.convert("RGB").resize((W, BOUND), Image.Resampling.LANCZOS)
    else:
        rgb = p.convert("RGB")
    rgb = Image.fromarray(enhance_speaker_rgb(np.array(rgb)))
    return Image.merge("RGBA", (*rgb.split(), p.split()[-1]))


def compose_cover(
    speaker: Image.Image,
    *,
    lines: list[tuple[str, tuple[int, int, int]]] | None = None,
    speaker_name: str | None = None,
    title_font: Path | None = None,
    name_font: Path | None = None,
    panel_color: tuple[int, int, int] = RED,
    bg_color: tuple[int, int, int] = CREAM,
    badge_color: tuple[int, int, int] = YEL,
    decorations: bool = True,
) -> Image.Image:
    """Full 1080x1920 cover: cream ground, coloured top panel, speaker, optional type."""
    cv = Image.new("RGBA", (W, H), bg_color + (255,))
    d = ImageDraw.Draw(cv)
    d.rectangle((0, 0, W, BOUND), fill=panel_color)
    sp = speaker.convert("RGBA")
    if sp.size != (W, BOUND):
        sp = sp.resize((W, BOUND), Image.Resampling.LANCZOS)
    cv.alpha_composite(sp, (0, 0))
    d = ImageDraw.Draw(cv)
    if decorations:
        d.ellipse((540 - 97, 932 - 97, 540 + 97, 932 + 97), fill=badge_color)

    if lines:
        font_path = str(title_font or DEFAULT_TITLE_FONT)
        size = 140
        f = ImageFont.truetype(font_path, size)
        while max(d.textlength(t, font=f) for t, _ in lines) > 980 and size > 40:
            size -= 2
            f = ImageFont.truetype(font_path, size)
        lh = int(size * 1.02)
        top = 1090
        for i, (t, c) in enumerate(lines):
            w = d.textlength(t, font=f)
            d.text(((W - w) / 2, top + i * lh), t, font=f, fill=c)
        print("title font size", size)

    if speaker_name:
        fn = ImageFont.truetype(str(name_font or DEFAULT_NAME_FONT), 30)
        tr = 7.6
        tw = sum(d.textlength(ch, font=fn) for ch in speaker_name) + tr * (len(speaker_name) - 1)
        x = (W - tw) / 2
        for ch in speaker_name:
            d.text((x, 1668), ch, font=fn, fill=BLACK, anchor="ls")
            x += d.textlength(ch, font=fn) + tr
    if decorations:
        d.ellipse((984 - 56, 1790 - 56, 984 + 56, 1790 + 56), fill=panel_color)
    return cv.convert("RGB")


def add_cover_cli(ap) -> None:
    """Common CLI flags for the two cover scripts."""
    ap.add_argument("-o", "--out", required=True, help="1080x1920 cover PNG")
    ap.add_argument("--rgb", help="opaque colour source (prefer the Real-ESRGAN crop)")
    ap.add_argument("--cut", required=True, help="RGBA cutout; alpha is the silhouette")
    ap.add_argument("--crop", help="x0,y0,x1,y1 crop applied to --rgb/--cut when they are full frames")
    ap.add_argument("--line", action="append", default=[], dest="lines",
                    help="cover line, optionally 'text|#RRGGBB' or 'text|red'. Repeatable.")
    ap.add_argument("--speaker-name", default="")
    ap.add_argument("--title-font", help="headline font (Archivo Black recommended; not bundled)")
    ap.add_argument("--name-font", default=str(DEFAULT_NAME_FONT))
    ap.add_argument("--no-decorations", action="store_true", help="skip the yellow and corner circles")
