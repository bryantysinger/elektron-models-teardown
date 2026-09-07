# Section 3 (MAIN OS) — map and findings

Everything here is derived from OS 1.13 on both devices, from the section
hashes recorded in `docs/hashes.md`. Addresses are load addresses, not file
offsets, unless stated.

Confidence is marked per claim. **Established** means verified more than one
way or confirmed against an independent fact. **Supported** means a single
line of evidence that looked solid. **Open** means do not build on it.

---

## Corrections to `README.md`

The README's section 3 paragraph is wrong in two places. Both were found this
session and both are the kind of error the project has made before, so they
are recorded rather than quietly fixed.

1. **The header is 16 bytes, not 4.** File offsets 0x00–0x03 hold
   `40 00 04 E8`, followed by twelve zero bytes. Code begins at file offset
   0x10.

2. **`46FC 2700` is not a reset entry.** The instruction at 0x40000410 opens
   an exception handler: it masks interrupts, snapshots `d0-a7` into a buffer
   whose pointer lives at 0x420DC6B0, restores them, and ends in `rte` at
   0x40000458. The real entry point is the address in the header, 0x400004E8.

The README also says section 3 is "based at 0x40000000". It is based at
0x40000400.

---

## Load address and entry

**Established.** File offset 0 maps to **0x40000400**. Scored the same way
`make base` does for section 2, over 2375 distinct `jsr abs.l` targets (all
with top byte 0x40, spanning 0x400005CC to 0x400F68D4): 0x40000400 scores
0.521 against 0.026 for the runner-up. Chance is around 0.02–0.05, so it
stands well clear. This holds for the Cycles image too; its descriptor
strings resolve correctly at the same base.

**Established.** The entry point is **0x400004E8**, the value in the header.
Two independent supports: it lands on a function boundary immediately after
an `rts`, and the function does what a reset entry does.

    400004e8  lea    %sp@(4),%a0
    400004ec  movel  %a0@,0x4013a720
    400004f2  moveal #0x48000000,%sp        ; stack at top of the SDRAM window
    400004fa  lea    0xfc04002d,%a0         ; GPIO config bytes
    4000051e  lea    0xec09000e,%a0         ; clears bit 11
    4000052c  jsr    %pc@(0x4000045c)       ; copy .data to SRAM
    40000530  jsr    %pc@(0x400004b2)       ; zero BSS
    40000542  movel  #0xa50ce100,%d0 ; movec %d0,%cacr
    4000054c  movel  #0x4007e020,%d0 ; movec %d0,%acr0
    40000556  jsr    0x400cabd4            ; main
    4000055c  halt

**Established.** `main` is at **0x400CABD4**.

### Memory map implied by startup

- ACR0 = 0x4007E020 makes 0x40000000–0x47FFFFFF cacheable. That is the SDRAM
  window; the stack starts at its top, 0x48000000, and grows down.
- Two initialised-data blobs are copied out of the image tail into the same
  64K SRAM the bootstrap uses: 0x401A05A0 to 0x80000000, and 0x401A24F0 to
  0x80008000. The second source runs to 0x401A7640, which is exactly the end
  of the image (0x40000400 + 0x1A7240).
- BSS is then zeroed from **0x401A05A0 to 0x4211F510**.

**This last point constrains any patch that wants to add code.** The image
tail is reused as BSS, so bytes appended past the end of the image get zeroed
during startup. Either patch in place using existing slack, or move the BSS
start. The BSS bounds are two immediates in the zero routine, at 0x400004BA
(start) and 0x400004C0 (end), which makes the second option more tractable
than it first appears.

---

## Code and data layout

**Established.** Call targets stop at 0x400F68D4, and string density jumps by
two orders of magnitude at file page 0xF. Code is roughly file 0x10 to
0xF6500; everything above is data, with the `.data` source images at the very
tail from file 0x1A01A0.

**Established.** The application is **C++ built with GCC, with RTTI left in**.
17,989 NUL-terminated printable runs, of which about 1,087 are mangled type
names and 407 are plain class names. There is a `ModelSeries` namespace with
`sound_struct`, `track_t`, `soundPool_t`, and versioned storage types
(`soundStorage_v1_t`/`v2_t`, `kitStorage_v1..v4_t`,
`patternStorage_v1..v4_t`, `projectStorage_v1..v6_t`). The view layer is named
in full: `MainScreenView`, `ParameterPageView`, `KeyboardView`,
`LFOSetupMenuView`, `RetrigPadsMenuView`, `SampleManager`, `SoundPool`,
`Track`, `LedHandler`, `MidiHandler`, `AnalogHandler`. Storage is
`MmcStreamReader`/`Writer`, `Lz4StreamCompressor`, `BackupFileImportAdapter`,
over a path-routed virtual filesystem (`/projects/*/.metadata`,
`/soundbanks/*/*`).

There are **no `_Z` function symbols**, so this gives type names only, not
function names.

**Established, and it answers a README open question.** The UI test suite the
bootstrap's panel-name list seemed to imply is present in section 3:
`UITestView`, `EncoderTestView`, `Automation_ui_test`, with strings including
`UI TEST (ENCODER)`, `PRESS SHOWN PAD 3 TIMES`, `TESTING COMPLETE`, `TURN
POWER OFF`. Whether it is reachable on a shipping unit is still unknown, but
the code exists.

**Established.** `ModelSamplesSysexRpc` is a **filesystem** protocol, not a
memory debugger. Its message types are `MidiRpcFsSampleOpenFileForRead`,
`WriteFileV1`/`V2`, `ReadDir`, `RenameFile`, `DeleteFile`,
`GetFileInfoFromHashAndSize`, and so on. That is Transfer's sample transport.
It does not offer peek or poke, so it cannot be used as a debug channel, and
every firmware experiment costs a real flash cycle.

---

## The parameter descriptor table

**Established.** A table of 56-byte descriptors, at **0x40109048** on the
Samples and **0x4010DDEC** on the Cycles. Found by following the pointers from
the parameter name strings; confirmed by the access idiom, which appears at
34 sites and computes index × 56 as `d*64 - d*8`:

    4000b2f6  lea    0x40109048,%a0
    4000b302  movel  %d1,%d2
    4000b304  lsll   #3,%d2         ; d2 = i*8
    4000b306  lsll   #6,%d1         ; d1 = i*64
    4000b308  subl   %d2,%d1        ; d1 = i*56

### Entry layout

| offset | field |
|--------|-------|
| +0x00 | group id (device-specific enumeration) |
| +0x04 | index within group |
| +0x08 | min, 8.8 fixed |
| +0x0C | max, 8.8 fixed |
| +0x10 | default, 8.8 fixed |
| +0x14 | flag (0 or 1; meaning unknown) |
| +0x18 | two 16-bit ids, 0xFFFF for unassigned |
| +0x1C | another id (0x94–0x1C0 range) |
| +0x20 | global parameter id, stable across devices |
| +0x24 | display format word |
| +0x28 | sort key |
| +0x2C | pointer to long name |
| +0x30 | pointer to group name |
| +0x34 | pointer to short name |

**Established.** The high half of +0x18 is the **MIDI CC number**. Confirmed
against the standard assignments: Filter Cutoff 74, Filter Reso 71, Pan 10,
Volume+Dist 7. Amp Decay is CC 80.

Values are 8.8 fixed point. Sample Pitch runs 40 to 88 around a default of 64,
which is the +/- 24 semitone range.

### Amp Decay

    0x401095f8  Amp Decay / Amp / DEC
      group 1, index 19, min 0, max 127, default 64
      CC 80, global id 0x49, sort key 30

### The global parameter id space

**Established.** The id at +0x20 is identical across both devices for every
shared parameter, so it is a Model-series-wide enumeration rather than a
per-device one. On the Samples:

    0x3C Filter Cutoff   0x3D Filter Reso    0x49 Amp Decay
    0x4A Volume +Dist    0x4B Delay Send     0x4C Reverb Send
    0x4D Pan             0x50 LFO Speed .. 0x57 Depth
    0x5A Delay Time      0x5D Delay Fdbk     0x65 Reverb Size
    0x68 Reverb Tone     0x6E Sample Pitch   0x6F Loop Mode
    0x70 Flip Mode

Unused ids: **0x3E–0x48** (eleven consecutive, sitting between the filter
parameters and Amp Decay), 0x4E–0x4F, 0x58–0x59, 0x5B–0x5C, 0x5E–0x64,
0x66–0x67, 0x69–0x6D.

Both tables also carry literal dead slots whose long name resolves to `Error`
or to nothing, at ids 0x0C, 0x0D, 0x0E among others.

Sort keys go in steps of ten (Sample Pitch 10, Amp Decay 30, Filter Cutoff 60,
Filter Reso 70, Delay Send 80, Reverb Send 90, Volume+Dist 100, Pan 110), so
20, 40 and 50 are free in the ordering.

**Supported, not established.** The 0x3E–0x48 block reads like reservation for
a filter envelope that was cut or that exists on a sibling device. That is a
guess from position and size only.

### Neither device exposes an attack

**Established.** The Cycles common block is Swing, Amp Decay, Volume+Dist,
Delay Send, Reverb Send, Pan, then the LFO and FX parameters. Its
machine-specific parameters are Algorithm, Pitch, Punch, Gate, and
Color/Shape/Sweep/Contour per machine. It has no filter parameters at all.
`Amp Decay` is the only envelope parameter on either device, so there is no
sibling build that already exposes an attack and no diff that hands us the
code.

---

## Device diff: where the engines live

Raw byte differencing is useless here because absolute operands differ
everywhere. What works is normalising each instruction to its mnemonic and
register operands, replacing numeric literals with a placeholder, and then
looking for 10-instruction sequences present in the Samples image and absent
from the Cycles image. 19,367 of 308,800 Samples instructions are unique under
that test.

**Established.**

- **0x40054000–0x40058600 is shared.** Essentially zero Samples-only code
  across almost the whole range, despite it holding the largest MAC cluster in
  the image (627 accumulator-touching lines in 0x40055000–0x40057FFF). This is
  the common audio framework: mixer, delay, reverb, parameter application.
- **0x400A1000–0x400A7FFF is the Samples-specific engine.** 77% to 100%
  Samples-only, and it holds the second MAC cluster (about 150 accumulator
  ops). Sample playback, the filter, and the per-voice gain all live here.
- Other substantially Samples-only regions, not investigated:
  0x40088000, 0x400DA000–0x400DB000, 0x400EF000, 0x400F4000–0x400F6000.

A useful consistency check fell out of this. The two densest MAC clusters
inside the sampler engine, at 0x400A5C9A and 0x400A5FD8, turn out to be
**filter coefficient computation** (squaring, reciprocal, two table lookups,
results written toward 0x8000CFD0), not voice rendering. Filter Cutoff and
Filter Reso are Samples-only parameters, so filter code landing in the
Samples-only region is exactly what the diff should produce.

---

## Gain paths

### Track mixer

**Established.** A six-iteration loop at 0x400A6A3C–0x400A6A9A, one pass per
track, taking voice pointers from a list at 0x80001B20 to 0x80001B38. A
per-track value is clamped to [0, 0x300000], scaled by 0x555556 (one third) so
that the maximum maps to index 8192, and used to look up a linear gain.

**Established.** The table at **0x4011C61C** is exponential:
value / 2^31 = 2^((i − 8192) / 2048), giving 0.0625 at i=0, 0.125 at 2048,
0.25 at 4096, 0.5 at 6144 and 1.0 at 8192. That is 24 dB of range at 2048
steps per octave.

**Established.** A second exponential table at **0x4012061C** uses the same
resolution: value / 2^30 = 2^(i/2048 − 1).

### Per-voice amplitude — the important one

**Established.** The per-voice gain is applied at **0x400A7262–0x400A7348**.

    400a7266  movel  #2147483647,%d5    ; target defaults to full scale
    400a726c  movel  %a3@(16),%d7       ; current gain, persisted per voice
    400a7278  tstb   %a3@(40)           ; if set -> target = 0
    400a728e  tstb   %a3@(41)           ; if set -> target = current/4
    400a72a0  movel  %d5,%a3@(16)       ; write back
    ...
    400a730a  subl   %d7,%d5            ; delta = target - current
    400a730c  asrl   #5,%d5             ; step = delta / 32
    400a731a: (loop, 16 iterations)
    400a7322    macl   %d7,%d1,...,%acc2  ; sample * gain
    400a732a    addl   %d5,%d7            ; gain += step
    400a732c    macl   %d7,%d6,%acc3      ; sample * gain
    400a7334    addl   %d5,%d7            ; gain += step
    400a7340    (satsl, store two output samples)
    400a7348  bnes   0x400a731a

Sixteen iterations of two samples each, so a 32-sample block.

**Established.** The voice object is **92 bytes** (`lea %a3@(92),%a3` at
0x400A7356), which matches the 92-byte stride off 0x8000CBFC seen in the
mixer, so these are the same structs. Known fields:

| offset | field |
|--------|-------|
| +0x10 | current gain, 32-bit, persists across blocks |
| +0x28 | flag: force target to zero |
| +0x29 | flag: force target to current/4 |

**This is the headline result for the attack project.** The voice does not
start at unity and multiply monotonically downward. There is a persistent
amplitude state variable, a settable target, and a per-sample linear
interpolator, all already present.

**The limit on that, stated plainly.** The step is recomputed every block as
(target − current)/32 over exactly 32 samples, so the gain always reaches its
target within one block, about 0.67 ms at 48 kHz. This is a de-click smoother,
not an envelope generator. It supplies the multiply, the state and the ramp
arithmetic. It does not supply timing.

---

## Attack feasibility: current assessment

Better than the worst case, still not easy.

**What is already in place.** A per-voice amplitude variable that persists
across blocks, a per-sample multiply into the render loop, ramp arithmetic,
and a target that the code already overrides from two different places. None
of that has to be created.

**What would have to be added.** Envelope timing: a per-voice attack counter
and a target derived from it rather than from the constant 0x7FFFFFFF. The
right place for that is the per-block setup around 0x400A7262, not the
16-iteration inner loop where all four accumulators and most of the register
file are committed. Per-block code has room.

**What is still unknown and could still sink it.** Where Amp Decay acts. It is
not at the gain site; nothing there reads a 0–127 parameter. The decay is
imposed on the target from somewhere upstream, and until that is found we
cannot say whether an attack can coexist with it or whether the two would
fight over the same state.

**Plumbing, which is in better shape than expected.** Adding a parameter to
the descriptor table is a data edit inside an existing structure: reserved
global ids exist, dead descriptor slots exist, and sort keys have insertion
room. The hard parts remain the DSP and the storage-versioning question
(`soundStorage_v2_t` and friends are versioned, and there is error text for
projects newer than the device supports, so widening a struct breaks existing
projects and Transfer; finding spare bytes inside v2 is the path that does
not).

**Test loop.** There is no debug channel. The RPC is filesystem only. Every
experiment is a flash cycle on hardware, with the physical MIDI DIN recovery
path as the only backstop. This is the main practical constraint on the whole
project.

---

## Open, do not assert

- Where Amp Decay is consumed.
- What the log-domain gain exponent read at 0x400A72AE carries in the general
  case. In the path traced it is written zero at 0x400A7274 and never written
  again, so it is constant there. Either this is a specialised path with the
  general case handled by the sibling clusters at 0x400A5FD8 and 0x400A61E0,
  or it is fed from elsewhere in the enclosing function.
- The routine at **0x400575E4**, in shared code, single caller at 0x400580BE.
  It converts a 0–127 parameter into a rate from a reciprocal-shaped table at
  0x40108940 (25451, 16967, 12725, 10180, ... which fits 25451/(1 + k/2)) and
  a duration from a table at 0x40108B40 (168750 × k early, reaching
  345,600,000 = 168750 × 2048), with a special case where 127 yields -1,
  meaning never. It writes a rate to an object at +12 and a deadline at +4. It
  could be the amp envelope or it could be parameter slewing. **Unresolved.**
  Note that Trig Length and Amp Decay are both 0–127 with an infinite maximum,
  so the 127 special case does not discriminate between them.
- The meaning of the descriptor fields at +0x14 and +0x1C.
- Whether flashing rewrites section 2 (pre-existing open question).

---

## Toolchain note

`scripts/setup.sh` reports a false negative on binutils 2.42. It greps
`objdump --info` for `547`, but on that version `--info` lists BFD targets,
not architectures; the architecture list including `m68k:547x` is in
`--help`. The disassembly is fine, the warning is spurious. Worth fixing the
check.

On Debian and Ubuntu the toolchain is `apt install binutils-m68k-linux-gnu`,
which provides `m68k-linux-gnu-objdump`.

---

## Reproducing

    cp model-samples_OS1_13.syx model-cycles_OS1_13.syx fw/
    ./scripts/setup.sh
    ./scripts/extract.sh fw/model-samples_OS1_13.syx
    ./scripts/extract.sh fw/model-cycles_OS1_13.syx
    m68k-linux-gnu-objdump -D -b binary -m m68k:547x \
      --adjust-vma=0x40000400 --start-address=0x40000410 \
      --stop-address=0x400f7000 \
      out/sections/model-samples_OS1_13/section_3_MAIN_OS.bin \
      > out/disasm/ms_code.asm

Note the base is 0x40000400 and the first code byte is at 0x40000410, i.e. the
header is 16 bytes. `scripts/disasm.sh` defaults to stripping 4, which is
correct for section 2 and wrong for section 3.
