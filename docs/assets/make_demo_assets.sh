#!/usr/bin/env bash
# Rebuild the README demo assets from the promo film.
#
#   docs/assets/demo.mp4         the full film, 1280x720, h264 crf 28 (limit 12 MB)
#   docs/assets/demo.gif         a 9-second highlight, 800 px wide (limit 3 MB)
#   docs/assets/demo-poster.png  one still from the highlight
#
# Usage: docs/assets/make_demo_assets.sh [path/to/film.mp4]
# Override the highlight with GIF_START / GIF_DUR / POSTER_AT (seconds), e.g.
#   GIF_START=31 GIF_DUR=9 POSTER_AT=36.5 docs/assets/make_demo_assets.sh
#
# The default window (31 s to 40 s of the 72.5 s draft) runs from the empty
# waterfall through the "一元不差" stamp to "拆到这里为止". If the film is
# re-cut, look at the frames again and move GIF_START.

set -euo pipefail

SRC="${1:-path/to/film.mp4}"
OUT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GIF_START="${GIF_START:-31}"
GIF_DUR="${GIF_DUR:-9}"
POSTER_AT="${POSTER_AT:-36.5}"
GIF_FPS="${GIF_FPS:-12}"
GIF_WIDTH=800
GIF_MAX_BYTES=$((3 * 1024 * 1024))
MP4_MAX_BYTES=$((12 * 1024 * 1024))

[ -f "$SRC" ] || { echo "film not found: $SRC" >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg is not on PATH" >&2; exit 1; }

PALETTE="$(mktemp -t aib-palette).png"
trap 'rm -f "$PALETTE"' EXIT

echo "mp4: $SRC -> demo.mp4"
ffmpeg -y -v error -i "$SRC" \
  -vf "scale=1280:720:flags=lanczos" \
  -c:v libx264 -crf 28 -preset slow -pix_fmt yuv420p -movflags +faststart -an \
  "$OUT/demo.mp4"

echo "gif: ${GIF_START}s + ${GIF_DUR}s at ${GIF_FPS} fps, ${GIF_WIDTH}px"
GIF_FILTERS="fps=${GIF_FPS},scale=${GIF_WIDTH}:-1:flags=lanczos"
ffmpeg -y -v error -ss "$GIF_START" -t "$GIF_DUR" -i "$SRC" \
  -vf "${GIF_FILTERS},palettegen=max_colors=128:stats_mode=diff" "$PALETTE"
ffmpeg -y -v error -ss "$GIF_START" -t "$GIF_DUR" -i "$SRC" -i "$PALETTE" \
  -lavfi "${GIF_FILTERS}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  -loop 0 "$OUT/demo.gif"

echo "poster: frame at ${POSTER_AT}s"
ffmpeg -y -v error -ss "$POSTER_AT" -i "$SRC" -frames:v 1 \
  -vf "scale=1280:720:flags=lanczos" "$OUT/demo-poster.png"

size() { stat -f %z "$1" 2>/dev/null || stat -c %s "$1"; }
status=0
for f in demo.mp4 demo.gif demo-poster.png; do
  printf '%-18s %9d bytes\n' "$f" "$(size "$OUT/$f")"
done
[ "$(size "$OUT/demo.gif")" -le "$GIF_MAX_BYTES" ] || { echo "demo.gif is over 3 MB; lower GIF_FPS or GIF_DUR" >&2; status=1; }
[ "$(size "$OUT/demo.mp4")" -le "$MP4_MAX_BYTES" ] || { echo "demo.mp4 is over 12 MB" >&2; status=1; }
exit $status
