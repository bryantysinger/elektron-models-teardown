#!/usr/bin/env bash
# Disassemble a raw section as ColdFire.
#
#   ./scripts/disasm.sh out/sections/<tag>/section_2_DSP.bin 0x80000000 20
#
#   $1  raw section file
#   $2  load address of the first byte AFTER the header  (default 0x80000000)
#   $3  header bytes to strip                            (default 20)
#
# Output goes to out/disasm/<name>@<base>.asm so you can keep several base
# guesses side by side and diff them.
set -euo pipefail
cd "$(dirname "$0")/.."
source out/toolchain.env

SRC=${1:?usage: disasm.sh <section.bin> [base] [header_bytes]}
BASE=${2:-0x80000400}
HDR=${3:-4}
NAME=$(basename "$SRC" .bin)
mkdir -p out/disasm

BODY=out/disasm/$NAME.body.bin
dd if="$SRC" of="$BODY" bs=1 skip="$HDR" status=none

OUT="out/disasm/${NAME}@${BASE}.asm"
"$OBJDUMP" -D -b binary -m m68k:547x --adjust-vma="$BASE" "$BODY" > "$OUT"

echo "$OUT"
wc -l < "$OUT"
