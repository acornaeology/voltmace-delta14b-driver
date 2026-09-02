# Disassembly Guide

How to produce annotated, verified disassemblies of the Voltmace Delta 14B driver programs.

For project overview and build instructions, see [README.md](README.md). For architecture details, see [CLAUDE.md](CLAUDE.md). For terminology, see [GLOSSARY.md](GLOSSARY.md).

Unlike the sibling ROM projects, these are **load-and-run programs**: a `*RUN` file that loads into main memory at `&1900`, not a sideways or parasite ROM. Each file is a 6502 driver plus a tokenised BBC BASIC front-end held under a rotate-left-one-bit protection. There is no address slice — the *whole file* must reassemble byte-for-byte.


## Prerequisites

- [uv](https://docs.astral.sh/uv/) for Python dependency management
- [beebasm](https://github.com/stardot/beebasm) (v1.10+) for assembly verification
- The program binary for the version being disassembled, plus its DFS load/exec addresses (from the `.inf`) and MD5/SHA-256 hashes (`md5 <file>`, `shasum -a 256 <file>`)
- [oaknut-basic](https://pypi.org/project/oaknut-basic/) (a project dependency) for (de)tokenising the BASIC front-end


## Quick reference: CLI tools

The disassembly tooling is [fantasm](https://acornaeology.github.io/fantasm/), invoked as `uv run fantasm <command>`. The most-used commands here:

| Command | Description | Example |
|---------|-------------|---------|
| `disassemble` | Run the dasmos driver to generate `.asm`, `.json`, and the incbin `.dat` | `fantasm disassemble keypad` |
| `verify` | Reassemble with beebasm and byte-compare the whole file | `fantasm verify keypad` |
| `lint` | Validate annotation addresses against the disassembly | `fantasm lint keypad versions/voltmace-delta-14b-driver-keypad/disassemble/disasm_voltmace_delta_14b_driver_keypad.py` |
| `asm extract` | Extract assembly by address range or label | `fantasm asm extract keypad &0A00 &0B00` |
| `audit summary/detail` | Subroutine annotation audit | `fantasm audit summary keypad` |
| `cfg depth/leaves/roots` | Call-graph queries | `fantasm cfg depth keypad` |

`fantasm` accepts hex addresses in several formats (`&0A00`, `$0A00`, `0x0A00`).


## Producing a version disassembly

### Step 1: Directory structure

Each program is modelled as its own fantasm "version" (ids `keypad`, `joystik`):

```
versions/voltmace-delta-14b-driver-<id>/
  binary/
    voltmace-delta-14b-driver-<id>        # the program binary (no extension)
    binary.json                           # title, size, load/exec, md5, sha256
  basic/
    voltmace-delta-14b-driver-<id>.bas    # detokenised BASIC front-end (editable source)
  disassemble/
    __init__.py                           # empty
    disasm_voltmace_delta_14b_driver_<id>.py
  output/                                 # generated .asm, .json, and .dat
```

The `binary/` layout (neutral directory, no file extension, `binary.json` metadata) is set by the `[binary]` section of `fantasm.toml` — these are program binaries, not ROM images. Add the id to `acornaeology.json` (`versions`) and to `fantasm.toml` (`[[versions.entry]]`).

### Step 2: Recover the BASIC front-end

The BASIC is tokenised and rotate-left-one-bit encoded. Decode it (rotate each byte left one bit), apply any loader repair (e.g. KEYPAD's first-line length byte), detokenise with `oaknut-basic detokenise`, and save the text under `basic/`. Confirm it round-trips: `oaknut-basic tokenise <bas> --crunch greedy` must reproduce the decoded tokens exactly. **Use `--crunch greedy`** — the original was built with a greedier-than-ROM tokeniser (see [GLOSSARY.md](GLOSSARY.md)); the default ROM crunch will not reproduce these files.

### Step 3: Build the driver script

Load the whole file at `&1900`, declare the load-time relocation with `d.add_move(...)`, mark entry points, carry the BASIC region with `d.include_binary(...)`, and regenerate the `.dat` from the `.bas` in the script's tail (tokenise → any loader-repair reversal → rotate right one bit), cross-checked against `ir.write_included_binaries(...)`.

### Step 4: Iterate

```sh
uv run fantasm disassemble <id>
uv run fantasm verify <id>
```

Fix errors until verification passes, then annotate.


## dasmos driver script reference

The driver configures a `dasmos.Disassembler`. The full driver-API guide is at <https://acornaeology.github.io/dasmos/driver_api.html>.

### Core API calls

**`d = dasmos.Disassembler.create(cpu="6502", ...)`** — Construct the disassembler. These are NMOS 6502 programs, so `cpu="6502"`.

**`d.load(filepath, base_address)`** — Load the program image at its load address (`0x1900`).

**`d.program(load_addr=..., exec_addr=..., reload_addr=...)`** — Record the DFS load-and-run metadata so the beebasm `save` directive emits exec/reload addresses.

**`d.add_move(dest_runtime, src_binary, length)`** — Declare a relocated block (the driver is stored at `&1900` but runs at `&0A00`); returns a `Move` passed as `move=` to annotations of the relocated code.

**`d.label(address, name)`** / **`d.comment(address, text)`** / **`d.subroutine(address, title=, description=)`** / **`d.entry(address)`** — Name addresses, comment instructions, banner subroutines, and mark entry points.

**`d.byte/word/string(address, length)`** — Classify data regions.

**`d.include_binary(runtime_addr, length, path)`** — Carry a data region as an external file (`incbin "<path>"`) instead of inline `equb`; the region still owns its bytes for the round-trip oracle. Pair with `ir.write_included_binaries(dir)` for the canonical payload.

**`ir = d.disassemble()` then `ir.render("beebasm" | "json")`** — Produce the rendered assembly or structured JSON.


## Annotation guidelines

### Comments raise the level of abstraction

Inline comments must describe **intent in domain terms**, not restate the mnemonic. Prefer "Deliver the keystroke into the keyboard buffer as if typed" over "OSBYTE &99: insert into buffer". Name an OS call's reason code only when it adds information the mnemonic cannot (the A/X selector), and lead with the effect. For every comment, ask whether it says more than the instruction already does; if not, cut it.

### Subroutine descriptions

- **Title**: a standalone phrase summarising the routine's purpose.
- **Description**: behaviour, entry/exit conditions, side effects.
- **Calling convention**: `on_entry` / `on_exit` register and flag details.

### Hex notation

- **Acorn notation** (`&XXXX`) in documentation and human-readable output.
- **Python notation** (`0xXXXX`) in driver scripts and tools.


## Key gotchas

1. **Whole-file verification, no slice.** The program loads at `&1900` and the entire file must reassemble; `d.load` the whole thing and account for every byte as code or data.

2. **NMOS 6502.** These are Model B programs — pass `cpu="6502"` (not `65C02`).

3. **Relocation.** The driver is stored at `&1900` but written to run at `&0A00` (offset −`&F00`); use `d.add_move` and annotate at the runtime address. The relocator deliberately skips page `&0B` to preserve the MOS soft-key buffer, so that page's file image is inert filler.

4. **The BASIC is carried as text.** The `.bas` is the source of truth; the driver regenerates the `incbin` `.dat` from it at build time. Any KEYPAD-style loader repair (the first-line length byte stored as 0) must be reversed in that regeneration.

5. **Reassembling by hand needs the right working directory.** The listing's `incbin` is relative, so run beebasm from the version's `output/` directory (fantasm's `verify` already does this).

6. **Auto-labels can collide** across a relocated block and its in-place copy; add explicit labels to resolve beebasm duplicate-label errors.


## Tools reference

| Tool | Source | Purpose |
|------|--------|---------|
| README generator | `generate_readme.py` | Render `README.md` from `acornaeology.json` and `README.md.j2` |
| BASIC (de)tokeniser | [oaknut-basic](https://pypi.org/project/oaknut-basic/) | Recover and re-encode the BASIC front-end (`--crunch greedy`) |
