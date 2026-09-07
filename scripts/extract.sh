#!/usr/bin/env bash
# Unpack an Elektron .syx firmware image into out/sections/<version>/
#
#   ./scripts/extract.sh fw/model-samples_OS1_13.syx
set -euo pipefail
cd "$(dirname "$0")/.."
source out/toolchain.env

SYX=${1:?usage: extract.sh <file.syx>}
TAG=$(basename "$SYX" .syx)
DEST=out/sections/$TAG
mkdir -p "$DEST"

echo "== report =="
"$EFT" -i "$SYX"

echo
echo "== extract -> $DEST =="
"$EFT" -i "$SYX" -o "$DEST"

echo
# Record hashes. Every finding you write down should be traceable to one of
# these, the way section_3_MAIN_OS.bin is for the Octatrack work.
( cd "$DEST" && shasum -a 256 ./* | tee SHA256SUMS )
