#!/usr/bin/env bash
# Rebuild the README demo video from the promo film.
#
#   docs/assets/demo.mp4   the full film, 1280x720, h264 crf 28 (limit 12 MB)
#
# Usage: docs/assets/make_demo_assets.sh path/to/film.mp4
#        AIB_FILM=path/to/film.mp4 docs/assets/make_demo_assets.sh
# The film is made outside this repository, so there is no default path.

set -euo pipefail

SRC="${1:-${AIB_FILM:-}}"
OUT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MP4_MAX_BYTES=$((12 * 1024 * 1024))

[ -n "$SRC" ] || { echo "usage: $0 path/to/film.mp4   (or set AIB_FILM)" >&2; exit 2; }
[ -f "$SRC" ] || { echo "film not found: $SRC" >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg is not on PATH" >&2; exit 1; }

echo "mp4: $SRC -> demo.mp4"
ffmpeg -y -v error -i "$SRC" \
  -vf "scale=1280:720:flags=lanczos" \
  -c:v libx264 -crf 28 -preset slow -pix_fmt yuv420p -movflags +faststart -an \
  "$OUT/demo.mp4"

size=$(stat -f %z "$OUT/demo.mp4" 2>/dev/null || stat -c %s "$OUT/demo.mp4")
printf '%-12s %9d bytes\n' demo.mp4 "$size"
[ "$size" -le "$MP4_MAX_BYTES" ] || { echo "demo.mp4 is over 12 MB" >&2; exit 1; }
