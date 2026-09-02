# Reproducing the originals: sources, build and verification

> **Scope.** This article explains how this repository regenerates the original
> `KEYPAD` and `JOYSTIK` files, byte-for-byte, from human-readable reverse-
> engineered sources — despite the originals mixing plain 6502, bit-rotated 6502,
> tokenised BASIC (also bit-rotated), and captured workspace in one file. It is
> the build-side companion to [The Voltmace Delta 14B driver system](system-architecture.md),
> which describes what those files *do*.

---

## 1. The problem

A conventional ROM disassembly has a tidy property: the file *is* the code, so a
disassembler can read it, a human can annotate it, and an assembler can turn the
annotated listing straight back into the identical bytes. The Voltmace files
break that property three ways:

- part of each file is **6502 machine code** stored **rotated left one bit**, so
  it is meaningless as code until decrypted;
- another part is a **tokenised BBC BASIC** program, also bit-rotated, that we
  want to keep as *editable BASIC text*, not an opaque blob;
- and the tokenisation was done by a **non-standard, greedier tokeniser** than
  the BBC BASIC ROM, so naively re-tokenising the text does not reproduce the
  original bytes.

The goal is nonetheless a full annotated disassembly that **reassembles to a
byte-identical copy of the whole file** — verified automatically in CI — while
the sources a person edits are readable assembly and readable BASIC.

## 2. The toolchain

Four tools cooperate, each doing one job:

- **[dasmos](https://github.com/acornaeology/dasmos)** — a programmable 6502
  disassembler with a byte-faithful round-trip guarantee. Driver *scripts*
  (`disassemble/disasm_*.py`) load a binary, annotate it (labels, comments,
  data typing, the `&1900→&0A00` relocation via `add_move`), and render a
  beebasm listing. Its `include_binary` primitive lets a region render as an
  `incbin` of an external payload instead of inline `equb`s.
- **[oaknut-basic](https://pypi.org/project/oaknut-basic/)** — a BBC BASIC
  (de)tokeniser. Its **`--crunch greedy`** mode reproduces the greedier-than-ROM
  tokeniser these programs were built with (see §5).
- **[beebasm](https://github.com/stardot/beebasm)** — the assembler. It turns the
  driver listings into bytes and, in `fantasm verify`, reassembles the whole
  listing (resolving the `incbin`) for the byte comparison.
- **[fantasm](https://acornaeology.github.io/fantasm/)** — the CLI/analysis layer:
  `disassemble` runs a driver script, `verify` reassembles and byte-compares the
  whole file, `lint`/`coverage`/`labels` check annotation quality.

## 3. The editable sources

For each program the *source of truth* a person edits is:

- the **dasmos driver script** — the annotations (every instruction commented,
  every label meaningful) live here as Python calls;
- a **`.bas` file** — the BASIC front-end as detokenised, editable text;
- for JOYSTIK, the two **driver variants** are additionally re-emitted as their
  own annotated `.asm` listings (`…-driver-a.asm`, `…-driver-b.asm`) which the
  build assembles.

Everything else — the `.asm` listing, the `.json`, and the `incbin` `.dat`
payload — is *generated*.

## 4. The build, region by region

The trick is that the bit-rotated region is carried as an **`incbin` payload**
that the driver script *regenerates* from the editable sources on every
`fantasm disassemble`, then cross-checks against the bytes dasmos itself
accounted for (its canonical `write_included_binaries` output). If the rebuilt
payload does not match, the build fails loudly.

**KEYPAD** (`build_basic_dat`): only the BASIC is encrypted. The build

1. greedy-tokenises `keypad.bas`;
2. reverses the first-line length repair (stores byte 3 as `0`, see §6);
3. rotates every byte right one bit (the inverse of the loader's left-rotate);

and that is the `.dat` the listing `incbin`s at `&1B00`. The driver itself is
plain 6502, disassembled in place with an `add_move(0x0A00, 0x1900, 0x100)` so
it reads at its `&0A00` runtime address.

**JOYSTIK** (`build_encoded_dat`): the encrypted region is
`[driver A][driver B][encrypted part of the BASIC]`, followed by the BASIC's raw
tail. The build

1. disassembles and annotates each 256-byte driver variant at its `&0A00`
   runtime address, renders its `.asm`, and **assembles it back to bytes** with
   beebasm (which also *proves* the disassembly round-trips);
2. greedy-tokenises `joystik.bas` and reverses the first-line repair;
3. concatenates `driver A + driver B + the BASIC bytes that fall inside the
   decode range` and **rotates the lot right one bit**;
4. appends the BASIC's raw tail (past the loader's page-`&4B` decode limit).

The result is the `.dat` the listing `incbin`s at `&1A00`. So the two joystick
drivers are readable, annotated assembly *and* the byte source for the encrypted
region — beebasm assembles them, and the build re-encrypts the result.

## 5. Why the greedy tokeniser

BBC BASIC's ROM tokeniser and these programs' tokeniser disagree in three ways
(a keyword may interrupt a hex constant or a name; a conditional keyword is
suppressed only before a *non-keyword* name character). `oaknut-basic`'s default
crunch is byte-exact to the ROM and therefore does **not** reproduce these files;
`--crunch greedy` matches the tool that actually built them. Both programs'
BASIC round-trips byte-for-byte under greedy crunch. (This was the finding behind
[oaknut-basic issue #48](https://github.com/rob-smallshire/oaknut/issues/48).)

## 6. The first-line length patch

The loader's `patch_header` writes the true length (`&16`/`&17`) into the first
BASIC line's length byte at run time, because the file stores it as `0` as part
of the protection. So the *build* must do the opposite: after tokenising the
`.bas` (which yields the correct length), it forces byte 3 back to `0` before
rotating and encrypting. The `.bas` in the repository is therefore the *true*
program (it lists and runs); only the on-disc image carries the deliberately
broken length.

## 7. Verification

`fantasm verify <program>` assembles the generated `.asm` with beebasm — from the
listing's own directory, so the relative `incbin` resolves — and compares the
result against the original file. There is **no slice**: the whole file must
match.

```
Verification PASSED: 8576 bytes match      # KEYPAD
Verification PASSED: 13312 bytes match     # JOYSTIK
```

Three independent checks therefore have to agree for a build to pass: dasmos's
own round-trip oracle, the driver-script cross-check of the rebuilt payload
against dasmos's canonical bytes, and beebasm's whole-file reassembly. CI runs
`disassemble → lint → verify` for both programs on every push.

## 8. Tooling that had to be built

Producing this to a publishable standard drove five upstream tool changes, all
since shipped:

- **oaknut-basic** — the `--crunch greedy` tokeniser mode
  ([#48](https://github.com/rob-smallshire/oaknut/issues/48)).
- **dasmos** — `include_binary` for external/generated payloads, and `program`
  for a `*RUN`-able `SAVE` with load/exec addresses
  ([#44](https://github.com/acornaeology/dasmos/issues/44),
  [#45](https://github.com/acornaeology/dasmos/issues/45)).
- **fantasm** — running beebasm from the listing's directory so `incbin`
  resolves ([#20](https://github.com/acornaeology/fantasm/issues/20)); a neutral
  configurable `binary` layout for non-ROM program files
  ([#21](https://github.com/acornaeology/fantasm/issues/21)); and a configurable
  binary filename so the artefacts keep their DFS names, `KEYPAD` and `JOYSTIK`
  ([#22](https://github.com/acornaeology/fantasm/issues/22)).
