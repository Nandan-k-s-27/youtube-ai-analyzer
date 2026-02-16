#!/usr/bin/env bash
set -euo pipefail

echo "[build] Installing Python dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt

if command -v ffmpeg >/dev/null 2>&1; then
  echo "[build] System ffmpeg found: $(command -v ffmpeg)"
  exit 0
fi

echo "[build] System ffmpeg not found. Downloading static ffmpeg..."
FFMPEG_DIR=".render/ffmpeg"
mkdir -p "$FFMPEG_DIR"

TMP_ARCHIVE="/tmp/ffmpeg-release-amd64-static.tar.xz"
curl -L "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz" -o "$TMP_ARCHIVE"

tar -xJf "$TMP_ARCHIVE" -C /tmp
EXTRACT_DIR="$(find /tmp -maxdepth 1 -type d -name 'ffmpeg-*-amd64-static' | head -n 1)"

if [ -z "$EXTRACT_DIR" ]; then
  echo "[build] Failed to extract ffmpeg static package"
  exit 1
fi

cp "$EXTRACT_DIR/ffmpeg" "$FFMPEG_DIR/ffmpeg"
cp "$EXTRACT_DIR/ffprobe" "$FFMPEG_DIR/ffprobe"
chmod +x "$FFMPEG_DIR/ffmpeg" "$FFMPEG_DIR/ffprobe"

echo "[build] Static ffmpeg installed at: $FFMPEG_DIR"
"$FFMPEG_DIR/ffmpeg" -version | head -n 1 || true