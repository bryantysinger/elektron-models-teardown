#!/usr/bin/env bash
# One-time environment setup. Idempotent: safe to re-run.
#
#   ./scripts/setup.sh
#
# Does three things:
#   1) finds (or builds) elektron-firmware-tool
#   2) finds an m68k/ColdFire objdump
#   3) writes out/toolchain.env with the resolved paths
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
mkdir -p out vendor

OCTABAM=${OCTABAM:-$HOME/git_repos/octabam}

echo "== 1) elektron-firmware-tool =="
EFT=""
# Prefer an already-built copy in your octabam checkout so there is one binary,
# one patch state, and one thing to keep current.
if [ -x "$OCTABAM/vendor/elektron-firmware-tool/elektron-firmware-tool" ]; then
  EFT="$OCTABAM/vendor/elektron-firmware-tool/elektron-firmware-tool"
  echo "   reusing octabam build: $EFT"
else
  if [ ! -d vendor/elektron-firmware-tool ]; then
    git clone https://github.com/mischa85/elektron-firmware-tool vendor/elektron-firmware-tool
  else
    git -C vendor/elektron-firmware-tool pull --ff-only || true
  fi
  # The octabam patch only touches the ELEK (Octatrack) container path and adds
  # EFT_EMIT_CONTAINER. Model:Samples images are ELE3, so the patch is optional
  # here; apply it anyway if available so one binary serves both projects.
  if [ -f "$OCTABAM/tools/elektron-firmware-tool.patch" ]; then
    if git -C vendor/elektron-firmware-tool apply --check \
         "$OCTABAM/tools/elektron-firmware-tool.patch" 2>/dev/null; then
      git -C vendor/elektron-firmware-tool apply \
         "$OCTABAM/tools/elektron-firmware-tool.patch"
      echo "   octabam patch applied"
    else
      echo "   octabam patch already applied or not applicable"
    fi
  fi
  make -C vendor/elektron-firmware-tool
  EFT="$ROOT/vendor/elektron-firmware-tool/elektron-firmware-tool"
fi

echo "== 2) m68k / ColdFire objdump =="
OBJDUMP=""
for cand in m68k-linux-gnu-objdump m68k-elf-objdump m68k-unknown-elf-objdump; do
  if command -v "$cand" >/dev/null 2>&1; then OBJDUMP=$(command -v "$cand"); break; fi
done
if [ -z "$OBJDUMP" ]; then
  cat <<'EOF'
   [!] No m68k objdump found.
       Try one of:
         brew install m68k-elf-binutils     # gives m68k-elf-objdump
         brew search m68k                   # if that formula name is wrong
       Verify it knows ColdFire:
         m68k-elf-objdump --info | grep 547
EOF
  exit 1
fi
echo "   $OBJDUMP"
if ! "$OBJDUMP" --info 2>/dev/null | grep -q '547'; then
  echo "   [!] this objdump does not list an m68k:547x variant; ColdFire MAC/EMAC"
  echo "       and ISA_B instructions may disassemble wrongly."
fi

cat > out/toolchain.env <<EOF
EFT=$EFT
OBJDUMP=$OBJDUMP
EOF
echo
echo "wrote out/toolchain.env"
