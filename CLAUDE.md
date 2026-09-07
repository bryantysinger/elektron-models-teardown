# CLAUDE.md

Orientation for Claude (or any AI assistant) helping someone work in this
repo. Read `README.md` first for the findings, then `docs/section3-map.md` if
the work touches section 3; this file is about how to work here without
producing confident nonsense.

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

**There is no debug channel.** `ModelSamplesSysexRpc` turned out to be a
filesystem protocol (`MidiRpcFsSampleOpenFileForRead`, `WriteFileV2`,
`ReadDir`, `GetFileInfoFromHashAndSize`), which is Transfer's sample
transport. It offers no memory read or write. So every firmware experiment
costs a real flash cycle on hardware. Weigh what you ask the user to test
accordingly, and prefer static work that can be done in your own sandbox.

## Traps this project has already fallen into

These are real errors made during analysis, each of which produced a
confident wrong claim. Expect to be tempted by all of them.

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
0.17 for the runner-up, and 0x40000400 scored 0.521 against 0.026. Two
earlier guesses read straight off the header both scored at chance and were
wrong. If nothing stands clear, say so.

**Do not assume a header length either.** Section 2 has a 4-byte header;
section 3 has a 16-byte one whose first longword is an entry-point address,
not a length. `scripts/disasm.sh` defaults to 4 and is wrong for section 3.
The README carried the 4-byte claim, and an "obvious" reset entry read off
the wrong offset, for as long as nobody checked.

**Do not assume a struct starts at its first pointer field.** The parameter
descriptor table was first read with entries aligned on the long-name
pointer, which put every numeric field on the wrong parameter and produced a
plausible-looking but entirely wrong set of ranges and ids. The correct
alignment came from the indexing idiom in the code (`lsll #3` / `lsll #6` /
`subl`, i.e. index * 56, off base 0x40109048), and was confirmed when the CC
numbers then matched the standard controllers (74 cutoff, 71 resonance, 10
pan, 7 volume). Find the access site before trusting a layout.

**Byte-diffing two builds of the same tree does not work here.** Absolute
operands differ throughout, so raw n-gram overlap sat around 0.4-0.6 even
for identical logic and the signal was unreadable. Normalise first: reduce
each instruction to mnemonic plus register operands with numeric literals
replaced by a placeholder, then compare sequences of ten. That turned mush
into a clean split between shared and device-specific code.

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
section 2 images taught more in one command than the full disassembly did,
and the normalised instruction diff of section 3 located both engines in a
single pass after hours of unproductive tracing. When two related binaries
exist, diff them first.

## Confidence levels in the current findings

Established, verified more than one way:
- Section 2 loads at 0x80000400 behind a 4-byte length header.
- Section 2 is a bootstrap/upgrade agent (string pool, and it matches
  Elektron's documented bootstrap-upgrade behaviour).
- Device id is one byte at 0x80003899, 0x0F Samples / 0x11 Cycles.
- Section 4 is byte-identical across both devices.
- Section 5 is an ASCII build timestamp; both 1.13 builds are three minutes
  apart.
- The crossflash works on Samples hardware, both directions, OS 1.13.
- Section 3 loads at 0x40000400 behind a 16-byte header; entry point
  0x400004E8; `main` at 0x400CABD4.
- Section 3 is C++ with RTTI intact; the parameter descriptor table is at
  0x40109048 (Samples) / 0x4010DDEC (Cycles), 56 bytes per entry.
- The audio core at 0x40054000-0x40058600 is shared between devices; the
  Samples-specific engine is at 0x400A1000-0x400A7FFF.
- The per-voice gain at 0x400A7262 is a target-seeking ramp over a
  persistent state variable, not a monotonic decay.

Supported but single-source:
- The DSPI identification.
- The per-voice struct being 92 bytes with gain at +0x10 and flags at
  +0x28/+0x29. Inferred from one call site plus a matching stride in the
  mixer, not from a traced pointer.

Unresolved, do not assert:
- Whether flashing rewrites section 2.
- Where Amp Decay is consumed. It is not at the per-voice gain site.
- What the routine at 0x400575E4 is. It converts a 0-127 parameter into a
  rate and a deadline via tables at 0x40108940 and 0x40108B40, with 127
  meaning never. Could be the amp envelope or parameter slewing. Trig Length
  and Amp Decay are both 0-127 with an infinite maximum, so the 127 special
  case does not discriminate between them.
- Whether the section 3 UI test suite is reachable on a shipping unit.
- The bytes near 0x800036DD and 0x80005960 that differ between devices.
- Nothing in `docs/section3-map.md` has been verified against hardware.

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
`README.md` and `docs/section3-map.md` exist only because an earlier
confident claim was challenged.

## Useful next questions

- Find where Amp Decay is consumed. It is not at the per-voice gain site, so
  the decay is imposed on the gain target from somewhere upstream. Whatever
  writes that target is the code any envelope work has to sit alongside.
- Resolve 0x400575E4 one way or the other, by tracing what fills the 0-127
  field its caller passes in.
- Determine whether the startup-menu upgrade path checks the device id
  independently of the running OS. That decides how recoverable a bad flash
  is, and with no debug channel it is the safety margin the whole project
  rests on.
- Locate the global delay and reverb within the shared audio core. They are
  present on both devices, so they sit in the region the device diff marks
  as common.
