SYX  ?= fw/model-samples_OS1_13.syx
TAG   = $(notdir $(basename $(SYX)))
SEC   = out/sections/$(TAG)
BASE ?= 0x80000400

.PHONY: setup extract header base disasm xref clean

setup:
	./scripts/setup.sh

extract: out/toolchain.env
	./scripts/extract.sh $(SYX)

header:
	python3 tools/modmap.py header $(SEC)/section_2_DSP.bin

base:
	python3 tools/modmap.py base $(SEC)/section_2_DSP.bin

disasm:
	./scripts/disasm.sh $(SEC)/section_2_DSP.bin $(BASE)

xref:
	python3 tools/modmap.py xref out/disasm/section_2_DSP@$(BASE).asm

out/toolchain.env:
	./scripts/setup.sh

clean:
	rm -rf out/disasm
