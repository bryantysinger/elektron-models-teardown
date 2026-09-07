# Section 2: the bootstrap

Technical detail behind the summary in `README.md`. Everything here is from
static analysis of Model:Samples OS 1.13 section 2, SHA-256
`97afe38b721d1396028662a4a3c30a131053779cae0069792b2a92b69b9db950`, 26602
bytes, disassembled with `m68k objdump -D -b binary -m m68k:547x
--adjust-vma=0x80000400` after stripping the 4-byte header.

Reproduce with:

    make extract
    make disasm

## Container header

Four bytes, big-endian: `0x000067E2` = 26594 = file size minus 8. The
remaining 26598 bytes are the payload.

Note this differs from the Octatrack, where section headers are 20 bytes. An
earlier version of this analysis assumed 20 here and derived a wrong load
address from it.

## Load address: 0x80000400

The payload loads at 0x80000400, i.e. file offset 4 maps to 0x80000400.

Confirmed three ways, in increasing strength.

**Statistically.** `make base` brute-forces the mapping by testing whether
absolute call targets land on function boundaries, scoring each candidate on
whether the target is preceded by `rts`/`nop`/`rte` and opens with a
recognisable prologue. 0x80000400 scores 0.682 with 44 of 45 targets inside
the image. The next distinct candidate scores 0.173. Chance is around
0.02-0.05.

**By inspection.** Sampled call targets are all preceded by `rts` and open
with real prologues: 0x800006BC with `lea %sp@(-20),%sp`, 0x800008E4 with
`moveq #33,%d1`, 0x80005A90 with `movel %a2,%sp@-`.

**From the code itself.** At 0x800011CA:

    203c 8000 0400   movel #0x80000400,%d0
    0280 ffff 0000   andil #0xffff0000,%d0
    0080 0000 0235   oril  #0x235,%d0
    4e7b 0c05        movec %d0,%rambar1

This programs RAMBAR1, the ColdFire internal SRAM base register, with
0x80000235: base 0x80000000 plus a valid bit and access-control bits. The
image references its own base as 0x80000400 and masks it to derive the SRAM
region base. This is the module telling us where it lives.

The 64K window implied by the initial SP (0x80010000) is therefore the
internal SRAM.

## Image layout

| range | content |
|-------|---------|
| 0x80000400 | initial SP, 0x80010000 |
| 0x80000404 | initial PC, 0x8000116C |
| 0x80000408 | 0x04000000, unidentified |
| 0x8000040C | 0x00000000, unidentified |
| 0x80000410 | a bare `rte`, used as the default exception vector |
| 0x80000412 | exception handler proper |
| 0x80000412 - ~0x80005B00 | code, 45 absolutely-called functions |
| ~0x80005B00 - ~0x80006A80 | data: index table, then string pool |
| 0x80006A8C - 0x80006BE2 | position-independent block, relocated at startup |

The code/data boundary was found by mapping `.short` density per 256-byte
page over the objdump output. Density is near zero below 0x80005A00 and near
total from 0x80005B00 onward.

## Startup sequence

`0x8000116C` is the reset PC. In order:

1. Read/modify/write a 16-bit register at 0xEC09000E, setting bit 12, with a
   `nop` after the write. Write 0xE000 to 0xEC09001A.
2. Read 0xFC0C0004, clear a field with `andil #0xFFFF83FF`, set
   `oril #0x1800`, write back. This looks like a clock or PLL divider field,
   though the specific register is not identified.
3. Clear bit 12 of 0xEC09000E again, then poll bit 4 of 0xFC0C0008 until set.
   A lock or ready bit.
4. Program RAMBAR1 as above.
5. Copy 0x80006A8C through 0x80006BE2, 342 bytes, to 0x8000F000.
6. Call the routine at 0x80001136.
7. Build a 256-entry exception vector table at the address held in
   0x80005ABC, filling all 1024 bytes with 0x80000410, the bare `rte`.

## The relocated block

Step 5 above matters for reading the disassembly. The 342 bytes at
0x80006A8C are copied to 0x8000F000 and executed from there, so references to
0x8000F004, 0x8000F008, 0x8000F00C and 0x8000F010 are *not* external. They
are offsets 4, 8, 12 and 16 into the relocated copy.

`jsr 0x8000f010` therefore calls the copy of the code at 0x80006A9C, and
0x8000F004 through 0x8000F00C are data slots in the block's 16-byte header.

An earlier version of this analysis recorded these as hardware registers or a
mailbox shared with MAIN OS. They are neither.

Relocating this block is the standard technique for code that must keep
running while the memory it normally executes from is being reprogrammed.

## The SPI reader

The relocated block's main routine reads bytes over the ColdFire DSPI at
0xFC05C000. The identification is solid, because the register offsets and the
field positions the code uses match the documented DSPI layout.

Entry at 0x80006A9C sets bits 10 and 11 of MCR (0xFC05C000), the transmit and
receive FIFO clear bits. The read loop at 0x80006B3C:

    2239 fc05 c02c   movel 0xfc05c02c,%d1     ; SR
    e889             lsrl  #4,%d1
    760f             moveq #15,%d3
    c283             andl  %d3,%d1
    67f2             beqs  0x80006b40          ; spin until RXCTR != 0
    2239 fc05 c038   movel 0xfc05c038,%d1     ; POPR
    1181 0800        moveb %d1,%a0@(0,%d0:l)  ; store byte to caller's buffer

Bits 7:4 of SR are RXCTR, the receive FIFO counter, so the shift-and-mask is
a wait for data. It then pushes the next command word to PUSHR
(0xFC05C034), choosing between two values:

- `0x80020000` for every byte but the last: bit 31 (CONT) set, chip select
  held asserted.
- `0x08020000` for the last byte: bit 27 (EOQ) set, CONT clear, releasing the
  chip select.

`0x00020000` in both is the peripheral chip select field. After the loop it
spins on bit 28 of SR, the end-of-queue flag, before returning.

## Instruction census

Over the code region. `make disasm` then count.

Calls, 446 total:

| form | count |
|------|-------|
| `jsr %a2@` | 97 |
| `jsr` absolute | 89 |
| `jsr %pc@(...)` | 83 |
| `jsr %a3@` | 74 |
| `jsr %a4@` | 37 |
| `jsr %a5@` | 36 |
| `jsr %a0@` | 24 |
| `jsr %fp@` | 6 |

268 of 446 calls go through an address register. This is a dispatch-table
architecture.

Arithmetic, in its entirety: two `mulsl`, one `muluw`, six `divuw`, and no
MAC instructions at all. Shifts: 55 `lsrl`, 52 `lsll`, 44 `asrl`.

**objdump reports six `macw` instructions. All six are false.** They sit at
0x80006274, 0x80006284, 0x80006318, 0x8000631C, 0x80006982 and 0x80006A04,
every one inside the data region, and are decodes of data words rather than
instructions. This nearly produced a wrong conclusion that the module used
the MAC unit. Check any instruction against the code/data boundary before
drawing inferences from it.

Most frequent opcodes: 1447 `movel`, 446 `jsr`, 444 `moveq`, 437 `pea`, 405
`lea`, 325 `moveb`, 251 `addql`, 236 `moveal`, 218 `cmpl`, 174 `clrl`, 152
`rts`. The `pea` count alongside the indirect call count is consistent with
passing structure pointers to dispatched handlers.

ISA_B instructions are present (93 `mvzb`, 36 `mvsb`, 14 `mvzw`, 6 `mvsw`),
which is why the `m68k:547x` machine variant is required. A plain 68000
objdump will decode these wrongly.

## Peripheral windows

By reference count in the disassembly:

| window | refs | identification |
|--------|------|----------------|
| 0xFC05C0xx | 103 | DSPI. Confirmed, see above. |
| 0xEC0940xx | 75 | external bus. Unidentified. |
| 0xFC0B80xx | 42 | unidentified |
| 0xEC0740xx | 20 | external bus. Unidentified. |
| 0xFC0400xx | 12 | unidentified |
| 0xFC03C0xx | 10 | unidentified |
| 0xEC0900xx | 10 | touched by the startup sequence |
| 0xFC0700xx | 8 | unidentified |
| 0xFC04C0xx | 8 | unidentified |
| 0xFC08C0xx | 7 | read by the exception handler at 0x80000412 |

Only the DSPI is identified with confidence. The rest are recorded because
the access patterns are worth someone else's attention, not because we know
what they are. 0xFC0xxxxx is consistent with a ColdFire IPSBAR peripheral
window and 0xEC0xxxxx with FlexBus chip-select space, but the specific part
has not been determined.

## Data region

An index table of 32-bit values spanning 0x00 to 0x34 begins around
0x80005B00. Purpose unconfirmed; the range is consistent with panel control
indices given the string list below.

A string pool begins at 0x80006460, addressed through a table of 32-bit
offsets at 0x80006573 onward. Contents in order:

`SAMPLES`, `ENCODER LEVEL`, `ENCODER A` through `ENCODER H`, `FUNCTION`,
`TRACK`, `PATTERN`, `BANK`, `TEMPO`, `RECORD`, `PLAY`, `STOP`, `PAGE`,
`KICK`, `SNARE`, `TOM`, `CLAP`, `COWBELL`, `CLOSED HAT`, `OPEN HAT`,
`CYMBAL`, `MIDI A` through `MIDI H`, then `BOOTSTRAP UPGRADE`,
`CONNECT POWER ADAPTER`, `AND RESTART`, `DO NOT TURN OFF!`, `UPGRADE FAILED`,
`CRC CHECK`, `VERSION CHECK`, `LENGTH ERROR`, `COMPLETE`,
`PLEASE RESTART ME`, `UPGRADE ABORTED`, `PLEASE REBOOT`, `UPGRADING...`,
`DO NOT TURN OFF`, `READY TO RECEIVE`, `PLEASE CONNECT`, `RECEIVING...`.

The upgrade strings identify the module. They match Elektron's documented
behaviour that some OS upgrades also upgrade the bootstrap, on first restart,
and must not be interrupted.

The panel inventory is unexplained. Elektron state that TEST mode is not
available on the Model:Samples or Model:Cycles, so if this is a factory test
it is not user-reachable.

## Differences between the two devices

Both bootstraps are 26602 bytes. 355 bytes differ, in 49 runs.

| location | Samples | Cycles | reading |
|----------|---------|--------|---------|
| 0x800036DD | 0x0A | 0x0C | unexplained |
| 0x800036E5 | 0x0A | 0x0C | unexplained |
| **0x80003899** | **0x0F** | **0x11** | **device id** |
| 0x8000596B, 0x80005979, 0x80005993, 0x800059A1, 0x800059B7, 0x800059BB, 0x800059CD | various ±1 | | unexplained, in the data region |
| 0x80006460, 119 B | `SAMPLES\0ENCO...` | `CYCLES\0ENCOD...` | device name, shifts the pool |
| 0x800064D8, 62 B | | | continuation of the same shift |
| 0x80006517, 84 B | | | continuation of the same shift |
| 0x80006573 - 0x8000663B | low byte, each 1 higher | | string-pool offsets |

The long tail of single-byte differences spaced 4 bytes apart is the offset
table. `CYCLES` is one character shorter than `SAMPLES`, so every string
after it moves down by one and every offset decrements. That accounts for
most of the 355 bytes.

Genuine behavioural difference between the two bootstraps therefore amounts
to the device id byte plus nine unexplained bytes.

## Open questions

- What the values at 0x80000408 (0x04000000) mean.
- What the panel-name string list is for.
- The nine unexplained differing bytes near 0x800036DD and 0x80005960.
- Whether flashing an OS rewrites section 2, and if so under what version
  condition. This determines whether a crossflashed unit is carrying the
  other device's bootstrap.
- Whether the startup-menu upgrade path checks the device id independently of
  the running OS. This determines how recoverable a bad flash is.
