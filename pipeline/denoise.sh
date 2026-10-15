#!/usr/bin/env bash
# DeepFilterNet3 noise reduction on a video's audio; video stream copied.
#   ./denoise.sh work/footage.mp4 work/footage_dfn.mp4
set -euo pipefail
IN=$1; OUT=$2
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
ffmpeg -v error -y -i "$IN" -vn -ac 1 -ar 48000 "$TMP/audio.wav"
if command -v deep-filter >/dev/null; then deep-filter -o "$TMP/out" "$TMP/audio.wav"          # Rust binary
elif command -v deep-filter-py >/dev/null; then deep-filter-py -m DeepFilterNet3 -o "$TMP/out" "$TMP/audio.wav"
elif command -v deepFilter >/dev/null; then deepFilter -m DeepFilterNet3 -o "$TMP/out" "$TMP/audio.wav"  # pip deepfilternet
else python3 -m df.enhance -m DeepFilterNet3 -o "$TMP/out" "$TMP/audio.wav"; fi
DEN=$(ls "$TMP"/out/*.wav | head -1)
ffmpeg -v error -y -i "$IN" -i "$DEN" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -shortest -movflags +faststart "$OUT"
echo "wrote $OUT"
