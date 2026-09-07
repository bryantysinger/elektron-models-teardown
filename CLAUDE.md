# CLAUDE.md

Orientation for Claude (or any AI assistant) helping someone work in this
repo. Read `README.md` first for the findings; this file is about how to
work here without producing confident nonsense.

## What this repo is

Static analysis of Elektron Model:Samples and Model:Cycles firmware. The
user brings their own `.syx`; nothing binary is committed. Work is
disassembly, diffing, and hypothesis testing against hardware the user owns.

Layout: `scripts/` drives the pipeline, `tools/modmap.py` does structural
analysis, `docs/` holds findings, `fw/` and `out/` are gitignored.

## The one rule that matters most

**This repo can brick people's hardware.** Before suggesting anything that
ends in a flash, confirm the user has backed up their +Drive and owns a
physical MIDI DIN interface, because the startup-menu recovery path
(`[FUNC]` on power-on, then `[TRIG 4]`) does not work over USB. Never
present the untested direction (Samples OS on physical Cycles hardware) as
equivalent to the tested one. When you do not know what a flash will do to
user data, say so rather than reasoning your way to reassurance.

## Traps this project has already fallen into

These are real errors made during the original analysis, each of which
produced a confident wrong claim. Expect to be tempted by all of them.

**Section names are not evidence.** `elektron-firmware-tool` writes
`section_2_DSP.bin`, and the file name is generated as
`"section_" + id + "_" + lookup(id)` from a hardcoded switch in its
`format.h`. The only thing that came out of the firmware is the integer 2.
Section 2 is not a DSP image on these devices. Do not let a filename stand
in for an identification.

**objdump will happily disassemble data.** A linear sweep over a region that
mixes code and data emits plausible-looking instructions from constants. The
original analysis found six `macw` instructions and nearly concluded the
module used the MAC unit; all six were inside the data block and were false
decodes. Before drawing conclusions from an instruction's presence, check
where it sits relative to the code/data boundary. `tools/modmap.py` and a
`.short`-density map by page are the cheap way to find that boundary.

**Do not assume a load address; score it.** `make base` brute-forces the
mapping by testing whether absolute call targets land on function
boundaries (preceded by `rts`/`nop`, opening with a recognisable prologue).
A correct base stands far clear of the field; 0x80000400 scored 0.68 against
0.17 for the runner-up. Two earlier guesses read straight off the header
both scored at chance and were wrong. If nothing stands clear, say so.

**Read all of `strings`, not the first screen.** The original analysis ran
`strings -n 5 | head -60`, saw junk from the code region, and recorded "no
meaningful strings". The string pool that identifies the entire module sat
further down. That single omission led to several turns of speculation about
peripheral registers when the answer was in plain ASCII.

**Peripheral identification from usage patterns is weak evidence.** The DSPI
at `0xFC05C000` is well supported because the register offsets used (`+0x2C`
status, `+0x34` push, `+0x38` pop) and the poll-then-read idiom match the
documented layout. The other peripheral windows in this image are guesses
from access patterns and are labelled as such. Keep that distinction.

**Diff before you disassemble.** The 355-byte diff between the two devices'
section 2 images taught more in one command than the full disassembly did.
When two related binaries exist, diff them first.

## Confidence levels in the current findings

Established, verified more than one way:
- Section 2 loads at 0x80000400 behind a 4-byte big-endian length header.
- Section 2 is a bootstrap/upgrade agent (string pool, and it matches
  Elektron's documented bootstrap-upgrade behaviour).
- Device id is one byte at 0x80003899, 0x0F Samples / 0x11 Cycles.
- Section 4 is byte-identical across both devices.
- Section 5 is an ASCII build timestamp; both 1.13 builds are three minutes
  apart.
- The crossflash works on Samples hardware, both directions, OS 1.13.

Supported but single-source:
- The DSPI identification.
- Section 3 based at 0x40000000.

Unresolved, do not assert:
- Whether flashing rewrites section 2.
- What the panel-name string list is for (Elektron say TEST mode is not
  available on these devices).
- The bytes near 0x800036DD and 0x80005960 that differ between devices.
- Anything about section 3's internals, including where the delay and
  reverb live.

## Working style that has worked here

Run diagnostics yourself rather than handing the user commands, when the
data is reachable. Grep, decode, hash, and plot in your own sandbox and show
the output. Hand over a command only when the target genuinely is not
reachable from where you are.

Check each finding against the binary before building on it. Addresses and
offsets carried forward from an earlier message in the conversation are a
common source of compounding error; re-derive them.

When a finding is surprising, say it is surprising and ask the user to sanity
check it against their hardware experience before treating it as settled.
The user owns the devices; you do not.

State corrections plainly when you get something wrong. Several findings in
`README.md` exist only because an earlier confident claim was challenged.

## Useful next questions

- Align the two section 3 images at function granularity. They are 11008
  bytes apart in size so byte diffing fails, but they came off one build tree
  minutes apart, so shared framework code should align. Divergence localises
  the sound engines; the global delay and reverb are present on both devices
  and should sit in the common region.
- Map MAC density across section 3 to find the audio code. Arithmetic is
  sparse enough elsewhere in this firmware that it should stand out.
- Determine whether the startup-menu upgrade path checks the device id
  independently of the running OS. That decides how recoverable a bad flash
  is.
