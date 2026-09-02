# CLAUDE.md

This file provides guidance when working with code in this repository.

## Project overview

Annotated disassemblies of the driver software for the **Voltmace Delta 14B** joystick/keypad handset system on the BBC Microcomputer. Unlike the sibling ROM projects, these are **load-and-run programs**: `*RUN` files extracted from a DFS disc that load into main memory at `&1900`, each pairing a 6502 driver with a tokenised BBC BASIC front-end held under a rotate-left-one-bit protection. The disc ships two programs — **KEYPAD** and **JOYSTIK** — modelled as fantasm "versions" with ids `keypad` and `joystik`.

## Build commands

Requires [uv](https://docs.astral.sh/uv/) and [beebasm](https://github.com/stardot/beebasm) (v1.10+).

```sh
uv sync
uv run fantasm disassemble keypad   # run the dasmos driver; also regenerates the incbin .dat from the .bas
uv run fantasm verify keypad        # reassemble with beebasm and byte-compare the WHOLE file
uv run fantasm lint keypad versions/voltmace-delta-14b-driver-keypad/disassemble/disasm_voltmace_delta_14b_driver_keypad.py
```

Verification is the correctness check: the generated assembly must reassemble to a byte-identical copy of the *entire* original file (no ROM slice).

## Architecture

### Tooling: fantasm + dasmos + oaknut-basic

- [dasmos](https://github.com/acornaeology/dasmos) — the programmable 6502 disassembler, driven by the per-version script under `versions/*/disassemble/`.
- [fantasm](https://acornaeology.github.io/fantasm/) — the CLI/analysis layer (`disassemble`, `verify`, `lint`, …); project layout and per-version metadata live in `fantasm.toml`.
- [oaknut-basic](https://pypi.org/project/oaknut-basic/) — (de)tokenises the BASIC front-end. Re-tokenise with `--crunch greedy` (these programs were built with a greedier-than-ROM tokeniser; the default crunch will not reproduce them).

### The disassembly driver

`versions/<id>/disassemble/disasm_voltmace_delta_14b_driver_<id>.py` loads the whole file at `&1900`, declares the load-time relocation (`d.add_move` — the driver is stored at `&1900` but runs at `&0A00`), marks entry points, carries the BASIC region with `d.include_binary(...)`, and records the DFS load/exec with `d.program(...)`. Its tail regenerates the `incbin` `.dat` from the editable `basic/*.bas` (greedy tokenise → reverse any loader repair → rotate right one bit) and cross-checks it against `ir.write_included_binaries()`.

### The BASIC front-end

The tokenised BASIC is stored ROL-1 encoded. It is kept in the repo as detokenised text under `basic/*.bas` (the source of truth) and re-encoded to the original bytes at build time, emitted via `incbin`. KEYPAD's first BASIC line has its length byte stored as 0 and patched to `&16` by the loader; the build reverses that.

### Version layout

```
versions/voltmace-delta-14b-driver-<id>/
  binary/  <prefix>-<id> + binary.json   # the program binary (no extension) + metadata
  basic/   <id>.bas                       # detokenised BASIC front-end
  disassemble/  disasm_*.py               # dasmos driver
  output/  *.asm, *.json, *.dat           # generated
```

These are program binaries, not ROM images, so the version artefacts live under a neutral `binary/` directory (no file extension, matching the DFS names KEYPAD/JOYSTIK) with a `binary.json` metadata file, configured via the `[binary]` section of `fantasm.toml` (fantasm 1.0+).

### Docs

- `README.md` — generated from `acornaeology.json` + `README.md.j2` by `generate_readme.py` (a pre-commit hook and CI keep it current).
- `DISASSEMBLY.md` — workflow guide. `GLOSSARY.md` — domain terms.

## Key technical context

- NMOS 6502 (`cpu="6502"`), BBC Model B. Load `&1900`; KEYPAD exec `&3906`, JOYSTIK exec `&1909`.
- Whole-file byte-identity is the bar (no slice).
- Inline comments describe **intent in domain terms**, never a paraphrase of the mnemonic.
- The driver relocates to `&0A00`, skipping page `&0B` to preserve the soft-key buffer, then decrypts and auto-runs the BASIC.
