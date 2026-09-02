# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

`versions/<id>/disassemble/disasm_voltmace_delta_14b_driver_<id>.py` loads the whole file at `&1900`, declares the load-time relocation (`d.add_move` — the resident driver is stored at `&1900` but runs at `&0A00`), marks entry points, carries the BASIC region with `d.include_binary(...)`, and records the DFS load/exec with `d.program(...)`. Its tail regenerates the `incbin` `.dat` from the editable `basic/*.bas` (greedy tokenise → reverse any loader repair → rotate right one bit) and cross-checks it against `ir.write_included_binaries()`.

**KEYPAD and JOYSTIK differ in shape — read both scripts before generalising.** In KEYPAD the resident driver is stored *plain* in the main image and disassembled inline via `add_move`; only the BASIC is encoded, and the loader is a *tail* (exec `&3906`). In JOYSTIK the loader is a *head* (exec `&1909`), and the resident driver ships as **two 256-byte variants** (`&1A00`/`&1B00`, both running at `&0A00`) that live *inside* the ROL-encoded region. The JOYSTIK script disassembles each variant as its own dasmos instance, renders it to both `.asm` **and** `.json` (`…-driver-a/-b.*`), assembles it back with beebasm, then concatenates `driver A + driver B + tokenised BASIC` and ROR-encodes the lot into the `incbin` `.dat`. So JOYSTIK's `output/` holds **three** disassembly JSONs (main plus two variants); KEYPAD's holds one.

### The BASIC front-end

The tokenised BASIC is stored ROL-1 encoded. It is kept in the repo as detokenised text under `basic/*.bas` (the source of truth) and re-encoded to the original bytes at build time, emitted via `incbin`. The first BASIC line has its length byte stored as 0 and patched by the loader (`&16` for KEYPAD, `&17` for JOYSTIK); the build reverses that (forces token offset 3 back to 0) before rotating.

### Version layout

```
versions/voltmace-delta-14b-driver-<id>/
  binary/  KEYPAD|JOYSTIK + .inf + binary.json  # program binary (DFS name, no ext) + DFS sidecar + metadata
  basic/   <id>.bas                       # detokenised BASIC front-end
  disassemble/  disasm_*.py               # dasmos driver
  output/  *.asm, *.json, *.dat           # generated
```

These are program binaries, not ROM images, so the version artefacts live under a neutral `binary/` directory (no file extension, matching the DFS names KEYPAD/JOYSTIK) with a `binary.json` metadata file, configured via the `[binary]` section of `fantasm.toml` (fantasm 1.0+).

### Coupling to the website

The sibling static-site generator [acornaeology.github.io](https://github.com/acornaeology/acornaeology.github.io) publishes these pages by cloning this repo and rendering each version's committed `output/*.json` plus `binary/binary.json`. Several `binary.json` fields drive that site, so keep them accurate when adding or renaming artefacts:

- `title` — the disassembly's display name (also used in `README.md`).
- `memory_map_groups` — display titles for the memory-map group keys.
- `source_files` — companion plain-text source pages (e.g. the BBC BASIC front-ends).
- `disassemblies` — *additional* formatted disassembly listings (JOYSTIK's two resident-driver variants), each pointing at one of the extra `output/*.json` files.

### Docs

- `README.md` — generated from `acornaeology.json` + `README.md.j2` by `generate_readme.py` (a pre-commit hook and CI keep it current); after changing the project description or any `binary.json` `title`, run `uv run generate_readme.py`.
- `DISASSEMBLY.md` — workflow guide. `GLOSSARY.md` — domain terms.
- `docs/analysis/` — long-form articles (system architecture, build/verification, and a walkthrough of each BASIC front-end), registered as `analyses` in `acornaeology.json` and rendered by the website. `docs/private/` holds the manufacturer manual and is **gitignored — never commit it**.

## Key technical context

- NMOS 6502 (`cpu="6502"`), BBC Model B. Load `&1900`; KEYPAD exec `&3906`, JOYSTIK exec `&1909`.
- Whole-file byte-identity is the bar (no slice). Comment-only edits still change `output/` (the `.asm`/`.json` regenerate) but keep `verify` passing.
- Inline comments describe **intent in domain terms**, never a paraphrase of the mnemonic.
- Each program's `*RUN` file has three roles, named consistently in comments and docs: the **driver loader** (the plain-6502 bootstrap that decrypts, patches the BASIC's length byte, and queues PAGE/OLD/RUN), the **BASIC front-end** (the configuration program the user drives), and the **resident driver** (the `&0A00` code that makes the handset look like the keyboard). Never call the loader or the front-end "the driver".
- KEYPAD's loader relocates its resident driver to `&0A00`, skipping page `&0B` to preserve the soft-key buffer; JOYSTIK's loader decrypts `&1A00–&4AFF` in place. Both then auto-run the BASIC.
- Out-of-range labels (OS entry points, hardware registers, zero page, OS vectors) carry `group=`/`description=`/`access=`/`length=` on `d.label(...)` so they populate the per-version memory-map page; give every mapped label a `group=` (an ungrouped map row warns).
