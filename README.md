# elektron-models-teardown

Tools and findings from analysing the firmware of the Elektron Model:Samples
and Model:Cycles.

The headline result for most people is that a Model:Samples can run the
Model:Cycles OS and vice versa, by swapping one section between the two
firmware containers. That technique is not original here; it was published by
a Reddit user (see Credits) and the container tool that makes it possible is
mischa85's. What this repo adds is a map of what is actually inside these
images, so that the crossflash is a worked example rather than a magic recipe,
and so that further work has somewhere to start.

**No firmware binaries are distributed here.** Bring your own `.syx` from
Elektron. SHA-256 values for every artifact are recorded in `docs/` so you can
confirm you are looking at the same bytes.

---

## Safety

Flashing firmware can brick hardware and destroy data. Read this section.

- **Back up your +Drive first**, with Elektron Transfer. The crossflash puts a
  foreign OS on top of your existing projects and samples. Nobody has
  characterised what that does to them.
- **Only one direction is hardware-tested.** A Model:Samples has been flashed
  with the Cycles OS and returned to the Samples OS successfully. A physical
  Model:Cycles running the Samples OS has *not* been tested here. That is the
  riskier direction, since the Samples does sampling and may expect memory or
  storage the Cycles does not have. Do not assume symmetry.
- **Have a recovery path physically in hand before you start.** The
  Model:Samples startup menu can reflash the OS: hold `[FUNC]` while powering
  on, press `[TRIG 4]` for OS UPGRADE, then send the `.syx` over the device's
  MIDI In port. That path **requires a physical MIDI DIN interface — it does
  not work over USB.** If you do not own one, get one before flashing anything.
- Never power off during an upgrade. Some upgrades also rewrite the bootstrap,
  which happens on the first restart after the OS update.
- Nobody involved is responsible for your hardware or your data.

---

## Requirements

- `elektron-firmware-tool` (https://github.com/mischa85/elektron-firmware-tool),
  built. `scripts/setup.sh` will clone and build it if you do not have it.
- An m68k/ColdFire `objdump`. Any of `m68k-linux-gnu-objdump`,
  `m68k-elf-objdump`, or `m68k-unknown-elf-objdump` works. It must support the
  `m68k:547x` machine variant; `setup.sh` checks and warns if not.
- Python 3, bash, make.

## Setup

    ./scripts/setup.sh

Writes `out/toolchain.env` with the resolved tool paths. Set `OCTABAM=/path`
to reuse an existing `elektron-firmware-tool` build from an octabam checkout.

## Use

    cp ~/Downloads/model-samples_OS1_13.syx fw/
    make extract                    # unpack container, write SHA256SUMS
    make header                     # module header + opcode census
    make base                       # score candidate load addresses
    make disasm                     # objdump at the confirmed base
    make xref                       # call graph, internal vs external targets

`fw/` and `out/` are gitignored. Everything in `out/` is reproducible from a
`.syx` plus these scripts.

---

## What is in the firmware

An OS `.syx` is an **ELE3** container holding four sections. The section
*names* printed by `elektron-firmware-tool` come from a hardcoded id-to-name
table in its `format.h`, not from the file, so treat them as labels of
convenience rather than statements about content. In particular, section 2 is
labelled "DSP" and is not a DSP image on these devices.

| id | label   | Model:Samples 1.13 | Model:Cycles 1.13 | what it is |
|----|---------|--------------------|-------------------|------------|
| 5  | meta    | 15 B               | 15 B              | ASCII build timestamp |
| 2  | DSP     | 26602 B            | 26602 B           | bootstrap / upgrade agent (ColdFire) |
| 3  | MAIN OS | 1733184 B          | 1744192 B         | the application (ColdFire) |
| 4  | updater | 31752 B            | 31752 B           | **byte-identical across both devices** |

The container carries an **HMAC-SHA256** trailer, not just checksums. The key
material is embedded in the image itself: `elektron-firmware-tool` locates an
8-byte anchor, derives the key from the string that follows it, and can
therefore regenerate a valid MAC for a modified image. This is why repacking
works at all, and why it did not appear to work to people who tried years ago.

### Section 5 (meta)

15 bytes of ASCII, `YYMMDD HH:MM:SS`. The two OS 1.13 images read
`210525 16:34:28` (Samples) and `210525 16:37:28` (Cycles): the same build
tree, three minutes apart. These are one codebase with a build-time device
configuration, not two separate products.

### Section 2 (labelled "DSP") — the bootstrap

Not a DSP image and not audio code. A 4-byte big-endian payload length, then
the image loads at **0x80000400**. The first two longwords there are an m68k
reset pair: initial SP `0x80010000`, initial PC `0x8000116C`. The load address
is confirmed by the code itself: startup programs the ColdFire internal SRAM
base register with `(0x80000400 & 0xFFFF0000) | 0x235`, placing the SRAM at
0x80000000.

Roughly 21.5 KB of ColdFire code, about 4 KB of data, then a short code tail.
It contains **no MAC instructions**, two `mulsl`, one `muluw` and six `divuw`
in total, so it cannot be doing signal processing. Calls are overwhelmingly
indirect (268 through address registers against 89 absolute), and the dominant
peripheral is the ColdFire DSPI at `0xFC05C000` with a byte-at-a-time SPI read
loop. Startup configures external bus chip selects and a clock or PLL divider,
programs RAMBAR1, relocates a 342-byte position-independent block from
0x80006A8C to 0x8000F000, and fills all 256 exception vectors with a bare
`rte` at 0x80000410. The relocated block holds the SPI reader, which is why
the image has a code tail after its data region, and why references to
0x8000F000-0x8000F010 are internal rather than external.

Its string pool at `0x80006460` settles the question: `BOOTSTRAP UPGRADE`,
`CONNECT POWER ADAPTER`, `AND RESTART`, `DO NOT TURN OFF!`, `UPGRADING...`,
`READY TO RECEIVE`, `RECEIVING...`, `UPGRADE FAILED`, `CRC CHECK`,
`VERSION CHECK`, `LENGTH ERROR`, `COMPLETE`, `PLEASE RESTART ME`,
`UPGRADE ABORTED`, `PLEASE REBOOT`. This matches Elektron's own documentation,
which warns that some OS upgrades also upgrade the bootstrap on first restart.

The pool is preceded by a panel inventory: `ENCODER LEVEL`, `ENCODER A`..`H`,
`FUNCTION`, `TRACK`, `PATTERN`, `BANK`, `TEMPO`, `RECORD`, `PLAY`, `STOP`,
`PAGE`, `KICK`, `SNARE`, `TOM`, `CLAP`, `COWBELL`, `CLOSED HAT`, `OPEN HAT`,
`CYMBAL`, `MIDI A`..`H`. Purpose unconfirmed. Elektron state that TEST mode is
not available on these two devices, so if this is a factory test it is not
user-reachable.

**Device identity is a single byte at `0x80003899`**: `0x0F` on the
Model:Samples, `0x11` on the Model:Cycles.

The two devices' bootstraps differ in only **355 bytes across 49 runs**, and
almost all of it is mechanical: the device id byte, the device name string,
and a long run of single-byte differences every 4 bytes which are the low
bytes of 32-bit string-pool offsets, each shifted by one because `CYCLES` is
one character shorter than `SAMPLES`. A handful of bytes near `0x800036DD`
and `0x80005960` remain unexplained.

### Section 3 (MAIN OS) — the application

ColdFire, based at `0x40000000`. First code word after a 4-byte header is
`46FC 2700` (`move #0x2700,%sr`), a reset entry. This is where the sequencer,
UI, sound engines and the global delay and reverb live. Largely unexplored.

---

## Worked example: crossflashing

The device accepts a container whose device byte matches the **currently
running OS**, and identity comes from section 3. So you keep the container of
the OS you are running and replace only section 3.

    source out/toolchain.env

    # Samples -> Cycles. Samples container (0x0F), Cycles OS.
    $EFT -i fw/model-samples_OS1_13.syx \
         -c 3 out/sections/model-cycles_OS1_13/section_3_MAIN_OS.bin \
         -o out/samples-running-cycles.syx

    # Cycles -> Samples. Cycles container (0x11), Samples OS.
    # Use this once the unit is running the Cycles OS.
    $EFT -i fw/model-cycles_OS1_13.syx \
         -c 3 out/sections/model-samples_OS1_13/section_3_MAIN_OS.bin \
         -o out/cycles-running-samples.syx

Verify before flashing, by extracting the result and hashing:

    $EFT -i out/samples-running-cycles.syx -o /tmp/verify
    shasum -a 256 /tmp/verify/section_*.bin

Section 2 should hash to the source container's bootstrap and section 3 to the
donor OS. Expected values are in `docs/hashes.md`.

Rebuilt containers are **not** byte-identical to the originals. The tool's
aPLib packer compresses better than Elektron's, so the container shrinks. This
is normal; verify by extraction and hashing, not by diffing against stock.

Flash with Transfer (drag onto the DROP page, then press `[YES]` on the
device) or from the CONFIG menu's UPGRADE entry.

**Build both directions before you flash either.** You want the return image
to exist as a file, not as a procedure to reconstruct on a device that is
identifying as something else.

### Tested

Model:Samples hardware, OS 1.13, both ways: flashed to the Cycles OS, ran as
expected, then returned to the Samples OS. Both images verified by extraction
and hashing beforehand.

### Open question

Whether flashing rewrites section 2. If it does, a unit returned to the
Samples OS via `cycles-running-samples.syx` is carrying the Cycles bootstrap,
with `0x11` at `0x80003899`, even though everything user-facing says Samples.
Reflashing stock Samples firmware afterwards resolves it. Nobody has confirmed
the behaviour either way.

---

## Credits

- The crossflash technique was published by a Reddit user on r/Elektron.
- `elektron-firmware-tool` is by mischa85:
  https://github.com/mischa85/elektron-firmware-tool
- Section 2 analysis, load address, and the device-id and bootstrap findings
  are original to this repo.
