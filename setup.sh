#!/usr/bin/env bash
# Installs ffmpeg, yt-dlp, faster-whisper, DeepFilterNet, rembg, onnxruntime and OpenCV
# (Python venv in .venv), Remotion Node deps, and the Real-ESRGAN x4plus ONNX weights.
# macOS (Homebrew) or Debian/Ubuntu (apt). Node 18+ is required for Remotion.
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname)" == "Darwin" ]]; then
  command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
  brew install ffmpeg python@3.11 node
  PY=$(brew --prefix python@3.11)/bin/python3.11
elif command -v apt-get >/dev/null; then
  sudo apt-get update
  sudo apt-get install -y ffmpeg python3 python3-venv python3-pip nodejs npm
  PY=python3
else
  echo "Unsupported OS: install ffmpeg, Python 3.10+ and Node 18+ manually."; exit 1
fi
NODE_MAJOR=$(node -p 'process.versions.node.split(".")[0]')
[ "$NODE_MAJOR" -ge 18 ] || echo "WARNING: Node $NODE_MAJOR found; Remotion needs 18+ (on Debian/Ubuntu use NodeSource or nvm)."
"$PY" -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r pipeline/requirements.txt
pipeline/download_models.sh
mkdir -p remotion/public/fonts
cp fonts/*/*.ttf remotion/public/fonts/
(cd remotion && npm ci)
echo "Done. Activate the Python tools with: source .venv/bin/activate"
