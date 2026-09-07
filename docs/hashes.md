# Artifact hashes

SHA-256 of sections extracted with `elektron-firmware-tool` from stock
Elektron firmware. No binaries are distributed; these let you confirm you
are working from the same bytes.

## Model:Samples OS 1.13

    97afe38b721d1396028662a4a3c30a131053779cae0069792b2a92b69b9db950  section_2_DSP.bin
    a351392c62ec1c6c3324a807baf46934690d54edfc76029a4b4882541cad1ab2  section_3_MAIN_OS.bin
    8215fd1050970a0d7c1c792fb911832374ca0a551f3ce9e523cb8e64a8810f0e  section_4_updater.raw
    fdb5e0ab55017edde7d3d65f4a22d3413c86ed3ae538ec19472ae1e931e93a98  section_5_meta.raw

## Model:Cycles OS 1.13

    bb9b81fdbd591813561ff5b172d304a59a7b5573b827fbbf9bcd1d9fa4c38152  section_2_DSP.bin
    cc99d4f0175d34d1e91d046e6ec85a5e8ab58ab9edbb3c24406acd48cb99ee98  section_3_MAIN_OS.bin
    8215fd1050970a0d7c1c792fb911832374ca0a551f3ce9e523cb8e64a8810f0e  section_4_updater.raw
    a6bd80a4233e69fdd5cfad115d3023f5badd97682d183eb96d0f493815e9d768  section_5_meta.raw

Note section 4 is identical across the two devices.

## Crossflash images

These are built locally, not distributed. Verify by extracting the rebuilt
container and hashing its sections:

| image | section 2 should be | section 3 should be |
|-------|--------------------|--------------------|
| `samples-running-cycles.syx` | Samples `97afe38b…` | Cycles `cc99d4f0…` |
| `cycles-running-samples.syx` | Cycles `bb9b81fd…` | Samples `a351392c…` |

Rebuilt containers are smaller than stock because the tool's aPLib packer
compresses better than Elektron's. Do not verify by diffing against the
original file.
