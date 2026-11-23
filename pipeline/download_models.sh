#!/usr/bin/env bash
# Download Real-ESRGAN x4plus ONNX weights into pipeline/models/.
# The weights are a format conversion of the official RealESRGAN_x4plus.pth
# (xinntao/Real-ESRGAN, BSD-3-Clause). They are not committed to the repo.
#
# Input contract the upscaler expects:
#   input  "input"  float32 [1, 3, H, W], RGB in 0..1, dynamic H/W
#   output float32 [1, 3, 4H, 4W], RGB in ~0..1
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=pipeline/models/RealESRGAN_x4plus.onnx
# Official-weight ONNX export with the I/O contract above.
URL="${REALESRGAN_ONNX_URL:-https://huggingface.co/relax123666/clearpic-models/resolve/main/RealESRGAN_x4plus.onnx}"
mkdir -p "$(dirname "$DEST")"
if [[ -f "$DEST" ]]; then
  echo "already present: $DEST ($(wc -c < "$DEST") bytes)"
  exit 0
fi
echo "downloading $URL"
if command -v curl >/dev/null; then
  curl -L --fail --retry 3 -o "$DEST.partial" "$URL"
else
  wget -O "$DEST.partial" "$URL"
fi
mv "$DEST.partial" "$DEST"
echo "wrote $DEST ($(wc -c < "$DEST") bytes)"
