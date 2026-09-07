#!/usr/bin/env python3
"""
modmap.py - structural analysis of an Elektron ColdFire section.

Subcommands
-----------
  header  <section.bin>
        Dump the 20-byte module header and give a rough code/data split.

  base    <section.bin> [--header N]
        Score candidate load addresses. Uses the fact that in compiled
        ColdFire code most called functions are immediately preceded by the
        rts/nop tail of the previous one, and most start with a recognisable
        prologue. Statistical only; treat the winner as a hypothesis to be
        confirmed by an actual disassembly, not as an answer.

  xref    <disasm.asm>
        Parse objdump output and report call targets, call counts, and which
        referenced addresses fall outside the disassembled range (those are
        resident firmware, hardware registers, or shared RAM).
"""
import argparse
import collections
import re
import struct
import sys

# Words that plausibly begin a ColdFire function.
PROLOGUE = {
    0x4E56,  # link.w a6,#d
    0x4FEF,  # lea d16(sp),sp
    0x48D7, 0x48E7,  # movem.l ->(sp)
    0x4CD7, 0x4CDF,  # movem.l (sp)->
    0x2F00, 0x2F01, 0x2F02, 0x2F03, 0x2F0A, 0x2F0B,  # move.l dn/an,-(sp)
    0x4E71,  # nop (alignment)
}
# Words that plausibly end one.
EPILOGUE = {0x4E75, 0x4E71, 0x4E73, 0x4E74}


def words(buf, off):
    return struct.unpack_from(">H", buf, off)[0] if 0 <= off < len(buf) - 1 else -1


def cmd_header(args):
    raw = open(args.section, "rb").read()
    f = struct.unpack_from(">5I", raw, 0)
    print(f"file size            : {len(raw)} (0x{len(raw):x})")
    print(f"[0] declared length  : 0x{f[0]:08x} ({f[0]})  file-8 = {len(raw)-8}")
    for i in range(1, 5):
        print(f"[{i}]                  : 0x{f[i]:08x}")
    print()
    hist = collections.Counter()
    for i in range(20, len(raw) - 1, 2):
        hist[words(raw, i)] += 1
    for op, name in ((0x4E75, "rts"), (0x4E71, "nop"), (0x4E73, "rte"),
                     (0x4E56, "link a6"), (0x4E5E, "unlk a6"),
                     (0x4EB9, "jsr abs.l"), (0x4EBA, "jsr d16(pc)"),
                     (0x4E90, "jsr (a0)"), (0x4FEF, "lea d16(sp),sp")):
        print(f"  {op:04x} {name:16s} {hist[op]}")


def cmd_base(args):
    raw = open(args.section, "rb").read()
    hdr = args.header
    targets = sorted({
        struct.unpack_from(">I", raw, i + 2)[0]
        for i in range(hdr, len(raw) - 5, 2)
        if words(raw, i) == 0x4EB9
    })
    if not targets:
        sys.exit("no jsr abs.l candidates found")

    scores = []
    # Candidate bases: any value that would place at least half the targets
    # inside the file. Step by 2 (instructions are word-aligned).
    lo = min(targets) - (len(raw) - hdr)
    hi = max(targets)
    for base in range(lo & ~1, hi + 2, 2):
        delta = hdr - base
        inside = [t + delta for t in targets if 0 <= t + delta < len(raw) - 1]
        if len(inside) < len(targets) * 0.5:
            continue
        s = sum((words(raw, o - 2) in EPILOGUE) + (words(raw, o) in PROLOGUE)
                for o in inside)
        scores.append((s / (2 * len(inside)), len(inside), base))
    scores.sort(reverse=True)
    print(f"{len(targets)} jsr abs.l candidates")
    print(f"{'score':>6}  {'inside':>6}  base")
    for s, n, b in scores[:15]:
        print(f"{s:6.3f}  {n:6d}  0x{b:08x}")
    print()
    print("Chance level is roughly 0.02-0.05. A base that is actually correct")
    print("should stand well clear of the field. If nothing does, the section")
    print("is probably relocated at load time, or these are not real jsrs.")


CALL = re.compile(r"^\s*([0-9a-f]+):\s.*\b(jsr|bsr\w*|jmp|bra\w*)\b.*?0x([0-9a-f]+)")


def cmd_xref(args):
    lo, hi = None, 0
    calls = collections.Counter()
    sites = collections.defaultdict(list)
    for line in open(args.asm):
        m = re.match(r"^\s*([0-9a-f]+):\s+[0-9a-f]", line)
        if m:
            a = int(m.group(1), 16)
            lo = a if lo is None else min(lo, a)
            hi = max(hi, a)
        m = CALL.match(line)
        if m:
            t = int(m.group(3), 16)
            calls[t] += 1
            sites[t].append(int(m.group(1), 16))
    print(f"disassembled range   : 0x{lo:08x} - 0x{hi:08x}")
    inside = {t: n for t, n in calls.items() if lo <= t <= hi}
    outside = {t: n for t, n in calls.items() if not (lo <= t <= hi)}
    print(f"branch/call targets  : {len(calls)} distinct "
          f"({len(inside)} internal, {len(outside)} external)")
    print()
    print("most-called internal targets (likely shared helpers):")
    for t, n in sorted(inside.items(), key=lambda kv: -kv[1])[:20]:
        print(f"  0x{t:08x}  {n:3d} calls")
    if outside:
        print()
        print("external targets (resident firmware / hardware / shared RAM):")
        for t, n in sorted(outside.items()):
            print(f"  0x{t:08x}  {n:3d} refs  from {[hex(s) for s in sites[t][:4]]}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("header"); a.add_argument("section"); a.set_defaults(fn=cmd_header)
    b = sub.add_parser("base"); b.add_argument("section")
    b.add_argument("--header", type=int, default=4); b.set_defaults(fn=cmd_base)
    c = sub.add_parser("xref"); c.add_argument("asm"); c.set_defaults(fn=cmd_xref)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
