#!/usr/bin/env bash
# Download a section of a YouTube video.
#   ./download_section.sh <url> <start> <end> <out.mp4>
# start/end as seconds or HH:MM:SS. Example: ./download_section.sh https://youtu.be/VIDEO 41:04 52:00 work/source.mp4
set -euo pipefail
[ $# -eq 4 ] || { echo "usage: $0 <url> <start> <end> <out.mp4>"; exit 1; }
URL=$1; START=$2; END=$3; OUT=$4
mkdir -p "$(dirname "$OUT")"
yt-dlp -f "bv*[height<=1080]+ba/b" --download-sections "*${START}-${END}" --force-keyframes-at-cuts \
  --merge-output-format mp4 -o "$OUT" "$URL"
echo "wrote $OUT (file time 0 = $START in the video)"
