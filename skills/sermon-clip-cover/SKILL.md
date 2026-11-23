---
name: sermon-clip-cover
description: >-
  Use when making the 9:16 sermon-clip cover: grab a frame from the high-res
  stream, optionally upscale with Real-ESRGAN, cut out the speaker, and add a
  smooth white sticker outline.
---
# Sermon clip cover

Use after a hookline is chosen and the section has been downloaded. Paths are repo-relative. Do not commit sermon media, model weights, or non-shareable fonts. Do not post the result.

## 1. Grab a frame from the high-resolution stream

Use the file from `pipeline/download_section.sh --measure-1080` (highest *real* 1080p bitrate, measured with ffprobe; do not trust yt-dlp's advertised tbr). Pick a clear, friendly speaking frame. File time 0 is the section start.

```sh
ffmpeg -y -ss <time-in-file> -i work/source.mp4 -frames:v 1 work/frames/speaker.png
```

## 2. Optional Real-ESRGAN upscale, then cutout

Preserve likeness: use Real-ESRGAN x4plus (ONNX, CPU). Do **not** use an image-generation "upscaler"; those change the face and are rejected.

Weights are not in the repo. `./setup.sh` calls `pipeline/download_models.sh`, or run that script on its own. The upscaler expects `RealESRGAN_x4plus.onnx` with input name `input`, shape `[1, 3, H, W]`, RGB float32 in 0..1.

```sh
python pipeline/upscale_esrgan.py work/frames/speaker.png \
  --crop x0,y0,x1,y1 \
  -o work/frames/speaker_esrgan.png \
  --cutout work/frames/speaker_cut.png
```

`--cutout` runs rembg `isnet-general-use` on the **original** HQ crop (default `--cutout-source original`) and applies that alpha to the ESRGAN colours. rembg on the 4x image can leak background and miss hands — do not make that the default.

## 3. Cover with a smooth white sticker outline

The outline is a sticker, not a tight path that eats into the person: fill holes in the mask, erode about 4 px, dilate with a circular kernel (~28 px, about 29 px measured on a typical silhouette), Gaussian-blur and re-threshold at 4x, then downscale. The mask is extended past a hard bottom crop so no white lip runs along that edge. Stray specks are dropped.

```sh
python pipeline/make_cover.py --rgb work/frames/speaker_esrgan.png \
  --cut work/frames/speaker_cut.png -o work/cover.png \
  --line "First hook line" --line "accent|#E8242B" \
  --speaker-name "PDT. NAME" --title-font /path/to/ArchivoBlack-Regular.ttf
```

`--title-font` should be a heavy face such as Archivo Black (SIL OFL, not bundled). Without an outline, use `pipeline/make_cover_no_outline.py` with the same flags.

If you already have a 4x rembg that leaked, pass it as `--cut` and the original-frame rembg as `--guide` (with `--guide-crop` when the guide is still a full frame) so new leaks are clipped to that silhouette.

## 4. In-video portrait

The circular portrait in the layout can be rebuilt from the same sharpened frame (ESRGAN colours, HQ rembg alpha) with `pipeline/make_layout.py --portrait ... --face-box x,y,size`. Prefer a sharper frame when you swap it; keep the same framing.

## 5. How it plays in the clip

The finished video shows the cover first, then a 1-second eased colour wipe in the cover's colour into the normal layout. Point `cover` and `coverColor` at this still in the Remotion config.
