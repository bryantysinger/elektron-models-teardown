# Elektron Model:Samples / Model:Cycles OS 1.13 — Amp Decay Analysis

## Summary

This analysis identifies the **Amp Decay** parameter descriptor in the Model:Samples OS 1.13 firmware and a shared 128-entry coefficient table that is a very strong candidate for its decay mapping.

The coefficient table appears byte-for-byte in both Model:Samples and Model:Cycles. Every one of its 128 entries exactly matches an exponential coefficient generated from a 10 ms–2 s nonlinear time mapping at a 48 kHz sample rate:

$$
T(p)=0.010+1.990\left(\frac{p}{127}\right)^{2.5}\ \text{seconds}
$$

$$
C(p)=\operatorname{round}\left(2^{31}e^{-1/(48000T(p))}\right),
\qquad p\in[0,127]
$$

This establishes the table's mathematical meaning with high confidence. What remains unproven is the final instruction-level connection from the Amp Decay parameter to this table: its consumers access a runtime table bundle indirectly through ColdFire/EMAC code, and the available LLVM disassembler does not decode all of those instructions.

## Firmware layout used here

The findings below come from the OS 1.13 firmware images:

- `model-samples_OS1.13.zip`
- `model-cycles_OS1.13.zip`

For the main OS section (`section_3_MAIN_OS.bin`), file offset zero maps to firmware address:

```text
0x40000400
```

All addresses in this note are runtime firmware addresses unless explicitly described as file offsets.

## Amp Decay parameter descriptor

The Model:Samples parameter descriptor table begins at:

```text
0x40109048
```

It contains 50 entries of 56 bytes (`0x38`) each. Amp Decay is ordinal entry 26:

```text
0x40109048 + 26 * 0x38 = 0x401095F8
```

Interpreting the descriptor as fourteen big-endian 32-bit fields gives:

| Offset | Raw value | Interpretation |
|---:|---:|---|
| `+0x00` | `1` | Parameter group |
| `+0x04` | `19` | Group-local parameter index |
| `+0x08` | `0x00000000` | Minimum: 0 in Q8.8 |
| `+0x0C` | `0x00007F00` | Maximum: 127 in Q8.8 |
| `+0x10` | `0x00004000` | Default: 64 in Q8.8 |
| `+0x14` | `0` | Unidentified metadata |
| `+0x18` | `0x0050FFFF` | MIDI CC 80 packed with an unset/unused halfword |
| `+0x1C` | `154` (`0x9A`) | Likely combined NRPN-style or related transport ID |
| `+0x20` | `73` (`0x49`) | Global/internal parameter ID |
| `+0x24` | `0x00000600` | Flags or value-format metadata |
| `+0x28` | `30` | Sort/display order |
| `+0x2C` | `0x4012A563` | Pointer to `"Amp Decay"` |
| `+0x30` | `0x4012A56D` | Pointer to `"Amp"` |
| `+0x34` | `0x4012A571` | Pointer to `"DEC"` |

The meanings of the unidentified and transport-related fields are provisional, but the descriptor's identity is not: the three string pointers explicitly label it as Amp Decay.

## Parameter-table machinery

Generic descriptor helpers begin around `0x400594B0`. They calculate the address of an entry by multiplying its ordinal by 56 bytes. In the machine code, multiplication by 56 is expressed as:

```text
(index << 6) - (index << 3) = 64*index - 8*index = 56*index
```

The routine at `0x40059618` reads the descriptor's bounds and clamps an incoming parameter value before dispatching it. This confirms that the stored parameter representation is **Q8.8**, not an ordinary 8-bit value.

For Amp Decay:

- minimum: `0x0000` = 0
- maximum: `0x7F00` = 127
- default: `0x4000` = 64

Some valid ColdFire instructions, including `mvz.b`, appear as raw `.word` values in LLVM's M68k disassembly. This affects presentation but does not alter the descriptor arithmetic above.

## The long exponential coefficient table

An identical 128-entry, 512-byte Q31 table occurs at:

| Product | Firmware address | Section 3 file offset |
|---|---:|---:|
| Model:Samples | `0x40106D5C` | `0x0010695C` |
| Model:Cycles | `0x4010BA2C` | `0x0010B62C` |

The two tables are byte-identical. Each entry is a positive signed Q31 fractional coefficient. All 128 values match the equations below exactly as integers:

$$
T(p)=0.010+1.990\left(\frac{p}{127}\right)^{2.5}
$$

$$
C(p)=\operatorname{round}\left(2^{31}\exp\left[-\frac{1}{48000T(p)}\right]\right)
$$

The exact match across every entry is strong evidence for all of the following:

1. The control range is 0–127.
2. The time mapping is nonlinear, with exponent 2.5.
3. The designed time-constant range is 10 ms–2 s.
4. The coefficient calculation assumes a 48 kHz update or sample rate.
5. The stored values are Q31 exponential multipliers.

Representative values are:

| Parameter `p` | Designed time constant `T(p)` | Stored coefficient |
|---:|---:|---:|
| 0 | 0.010000 s | `0x7FBBCDED` |
| 32 | 0.073419 s | `0x7FF6B3FD` |
| 64 | 0.368751 s | `0x7FFE2615` |
| 96 | 0.998611 s | `0x7FFF50FF` |
| 127 | 2.000000 s | `0x7FFFA89E` |

Because the coefficient is quantized to Q31, converting the last stored value back to a time constant produces approximately `1.9999557 s`, rather than exactly 2 seconds.

### Interpreting the time constant

If this coefficient is repeatedly applied as an ordinary one-pole exponential multiplier, `T` is the mathematical time constant: after `T` seconds, the signal has fallen to $e^{-1}$, or about 36.8% of its initial value.

Time to fall by 60 dB is:

$$
t_{-60\,\mathrm{dB}}=\ln(1000)T\approx6.907755T
$$

| Parameter `p` | Approximate −60 dB time |
|---:|---:|
| 0 | 69.1 ms |
| 32 | 507 ms |
| 64 | 2.547 s |
| 96 | 6.898 s |
| 127 | 13.815 s |

These are mathematical values for an unconstrained exponential. The audible envelope length may differ if the firmware uses a cutoff threshold, changes stages, scales the coefficient, or terminates the envelope explicitly.

## Neighboring table bundle

The long table belongs to a larger bundle of control/DSP tables. In Model:Samples, the source bundle begins at `0x40106950` and is installed during initialization through the runtime pointer at `0x8000AE20`, near code at `0x40056EEC`.

The corresponding Model:Cycles source bundle begins at `0x4010B620`; related initialization code appears around `0x40057FAA`.

Useful offsets within the bundle are:

| Bundle offset | Model:Samples address | Model:Cycles address | Characterization |
|---:|---:|---:|---|
| `+0x20C` | `0x40106B5C` | `0x4010B82C` | Monotonic 128-entry Q31 curve from 0 to 1; likely amplitude/control shaping, exact role unknown |
| `+0x40C` | `0x40106D5C` | `0x4010BA2C` | 10 ms–2 s exponential coefficient table; strong Amp Decay candidate |
| `+0x60C` | `0x40106F5C` | `0x4010BC2C` | Fast 0.1 ms–100 ms coefficient table |

The fast table also has an exact 128-entry formula:

$$
T_{\mathrm{fast}}(p)=0.0001+0.0999\left(\frac{p}{127}\right)^2
$$

$$
C_{\mathrm{fast}}(p)=\operatorname{round}\left(2^{31}\exp\left[-\frac{1}{48000T_{\mathrm{fast}}(p)}\right]\right)
$$

Its 0.1 ms–100 ms range makes it a plausible attack, smoothing, or de-clicking control, but it has not yet been assigned to a named parameter.

Direct literal references to `0x40106D5C` are absent because consumers access the bundle through `0x8000AE20` and add offsets at runtime. That indirection is the main obstacle to proving the final parameter-to-table connection.

## The earlier 960-tick lead

An earlier investigation centered on code at `0x400575E4`. The surrounding function actually starts at `0x400574EC`, and one caller is at `0x400580BE`; `0x400575E4` is an internal block rather than a function entry.

This code does **not** appear to implement Amp Decay. It operates on a six-entry timing/event state, resets a countdown to 960, and consults a 960-byte pulse-mask table at `0x401081C0`. Its structure is much more consistent with a retrigger or gate scheduler.

The value 960 is significant as an internal timing-cycle resolution and is plausibly 960 PPQN. If interpreted that way:

- one quarter note = 960 internal ticks;
- one sixteenth note = 240 ticks;
- 24 exposed microtiming positions per sixteenth would equal 10 internal ticks per UI microtiming unit;
- the exposed microtiming grid would therefore behave like 96 PPQN even though the internal clock is 960 PPQN.

The exact relationship between one traversal of the 960-byte table and musical quarter-note time has not yet been proven, so the PPQN interpretation should remain qualified.

The pulse-mask lanes have dominant event spacings of 120, 96, 80, 60, 48, 40, 30, and 24 ticks. Across a 960-tick cycle, those correspond to 8, 10, 12, 16, 20, 24, 32, and 40 pulses. This reinforces a rhythmic retrigger interpretation and rules the routine out as the Amp Decay implementation.

## Confidence assessment

### Established directly from the firmware

- The Amp Decay descriptor is at `0x401095F8` in Model:Samples.
- Its parameter range and default are stored in Q8.8 form as 0, 127, and 64.
- Generic parameter code calculates 56-byte descriptor addresses and clamps values to descriptor bounds.
- Both exponential tables match their stated formulas exactly for all 128 entries.
- The long table is byte-identical in Model:Samples and Model:Cycles.
- The equations embed a 48 kHz rate.
- The tables are reached indirectly through a runtime table-bundle pointer.
- The 960-count routine is timing/event machinery, not Amp Decay.

### Strong inference

- The shared 10 ms–2 s table is the Amp Decay mapping, or a generic decay coefficient table used by Amp Decay.

Its range, shape, size, numerical encoding, and placement among control/DSP curves all fit this role exceptionally well. Calling it definitively Amp Decay still requires the consumer trace described below.

### Still open

- The exact ColdFire/EMAC instruction path connecting global parameter ID `0x49` (or group/index `(1,19)`) to bundle offset `+0x40C`.
- The exact envelope recurrence, scaling, stage transitions, and termination threshold.
- Whether the table is exclusive to Amp Decay or shared by other envelope controls.
- The precise musical duration represented by one 960-entry scheduler-table traversal.

## Recommended next steps

1. Use a ColdFire-aware GNU M68k disassembler or an appropriate Ghidra processor module that can decode the EMAC/A-line instructions missed by LLVM.
2. Trace reads through runtime bundle pointer `0x8000AE20`, focusing on offsets `+0x20C`, `+0x40C`, and `+0x60C`.
3. Follow parameter ID `0x49`, or group/index `(1,19)`, from the generic setter into per-voice DSP state updates.
4. On hardware, measure Amp Decay at parameter values 0, 32, 64, 96, and 127. Compare the measured envelope with both the predicted time constants and the predicted −60 dB times.
5. Determine whether envelope termination or stage transitions account for any systematic difference between the mathematical exponential and the audible duration.

## Bottom line

The firmware gives a precise candidate decay law:

$$
\boxed{T(p)=0.010+1.990(p/127)^{2.5}\ \text{seconds}}
$$

with its per-sample Q31 multiplier calculated at 48 kHz as:

$$
\boxed{C(p)=\operatorname{round}\left(2^{31}e^{-1/(48000T(p))}\right)}
$$

The formula is proven against every value in an identical table present in both OS 1.13 firmwares. The remaining task is mechanical attribution: decoding the indirect ColdFire/EMAC consumer path well enough to show conclusively that Amp Decay selects bundle offset `+0x40C`.
