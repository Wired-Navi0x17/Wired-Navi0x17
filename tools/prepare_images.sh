#!/usr/bin/env bash
# Builds the small image derivatives that build.py embeds into the SVGs.
# GitHub blocks external resources inside SVGs, so every picture is inlined as
# base64. Keeping these derivatives small keeps each SVG light.
#
# Requires ImageMagick 7 (`magick`). Run from the repo root:
#   bash tools/prepare_images.sh
set -euo pipefail

SRC=assets/source
OUT=assets/img
mkdir -p "$OUT"

# Hero portrait (tall, centre of the hero card)
magick "$SRC/lainPfp.jpg" -resize 360x -strip -quality 80 "$OUT/portrait.jpg"

# Framed thumbnails on the right side of the hero (2:1-ish crops, first frame)
magick "$SRC/lain-wired.gif[0]"  -resize 260x -gravity center -crop 260x150+0+10 +repage -strip -quality 78 "$OUT/thumb-wired.jpg"
magick "$SRC/lain-glitch.gif[0]" -resize 260x -gravity center -crop 260x150+0-10 +repage -strip -quality 78 "$OUT/thumb-glitch.jpg"
magick "$SRC/navi-logo.gif[0]"   -resize 150x -gravity center -background black -extent 260x150 -strip -quality 80 "$OUT/thumb-navi.jpg"

# Three slanted slices inside the dossier box
magick "$SRC/lainPfp.jpg"         -gravity north -crop 901x1100+0+80 +repage -resize 110x -gravity center -crop 110x130+0+0 +repage -strip -quality 76 "$OUT/slice-1.jpg"
magick "$SRC/lain-wired.gif[0]"   -gravity center -crop 300x360+40+0 +repage -resize 110x -gravity center -crop 110x130+0+0 +repage -strip -quality 76 "$OUT/slice-2.jpg"
magick "$SRC/lain-glitch.gif[0]"  -gravity center -crop 240x290+0+0 +repage -resize 110x -gravity center -crop 110x130+0+0 +repage -strip -quality 76 "$OUT/slice-3.jpg"

# Film strip on the hero's left edge
magick "$SRC/lain_vertical.gif[0]" -resize 40x -strip "$OUT/strip.png"

# Navi emblem for the system card
magick "$SRC/navi-logo.gif[0]" -resize 120x120 -strip "$OUT/navi.png"

ls -l "$OUT"
