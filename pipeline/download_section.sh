#!/usr/bin/env bash
# Download a section of a YouTube video.
#
#   ./download_section.sh <url> <start> <end> <out.mp4>
#   ./download_section.sh --measure-1080 <url> <start> <end> <out.mp4>
#   ./download_section.sh --format 137 <url> <start> <end> <out.mp4>
#
# start/end as seconds or HH:MM:SS.
# yt-dlp's advertised bitrates can be wrong, and HLS formats 614/270 are
# mirrors of 248/137. --measure-1080 probes each distinct 1080p video-only
# stream for a few seconds and keeps the one with the highest ffprobe bitrate.
set -euo pipefail
usage() {
  echo "usage: $0 [--measure-1080] [--format ID] [--probe-seconds N] <url> <start> <end> <out.mp4>"
  echo "  --measure-1080    probe 1080p formats and pick the highest ffprobe bitrate"
  echo "  --format ID       use this video format id (plus best audio)"
  echo "  --probe-seconds N  length of each --measure-1080 probe (default 8)"
  exit "${1:-1}"
}
MEASURE=0
FORMAT=""
PROBE=8
while [[ $# -gt 0 ]]; do
  case "$1" in
    --measure-1080) MEASURE=1; shift ;;
    --format) [[ $# -ge 2 ]] || usage; FORMAT=$2; shift 2 ;;
    --probe-seconds) [[ $# -ge 2 ]] || usage; PROBE=$2; shift 2 ;;
    -h|--help) usage 0 ;;
    --) shift; break ;;
    -*) echo "unknown option: $1" >&2; usage ;;
    *) break ;;
  esac
done
[[ $# -eq 4 ]] || usage
URL=$1; START=$2; END=$3; OUT=$4
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$(dirname "$OUT")"

if [[ -z "$FORMAT" && "$MEASURE" -eq 1 ]]; then
  echo "measuring real 1080p bitrates (ffprobe on a ${PROBE}s probe; advertised tbr is not trusted)"
  BEST_LINE=$("$HERE/pick_1080.py" "$URL" --start "$START" --seconds "$PROBE")
  FORMAT=${BEST_LINE#BEST=}
  [[ -n "$FORMAT" && "$FORMAT" != "$BEST_LINE" ]] || { echo "could not pick a 1080p format" >&2; exit 1; }
  echo "using format $FORMAT"
fi

if [[ -n "$FORMAT" ]]; then
  YT_FMT="${FORMAT}+ba/b"
else
  # Default: best video up to 1080p plus best audio. Prefer --measure-1080
  # when quality matters: this selector follows yt-dlp's ranking, not measured bitrate.
  YT_FMT="bv*[height<=1080]+ba/b"
fi

yt-dlp -f "$YT_FMT" --download-sections "*${START}-${END}" --force-keyframes-at-cuts \
  --merge-output-format mp4 -o "$OUT" "$URL"
echo "wrote $OUT (file time 0 = $START in the video; format $YT_FMT)"
