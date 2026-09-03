# Voltmace Delta 14B Driver

[![Verify disassembly](https://github.com/acornaeology/voltmace-delta14b-driver/actions/workflows/verify.yml/badge.svg)](https://github.com/acornaeology/voltmace-delta14b-driver/actions/workflows/verify.yml)

Annotated disassemblies of the driver software for the Voltmace Delta 14B joystick/keypad handset system on the BBC Microcomputer. The Delta 14B/1 interface unit connects up to two handsets (each a 3x4 keypad plus a two-axis analogue joystick) to the BBC Micro's analogue and user ports, multiplexed by a 74LS157. The software ships two programs — JOYSTIK and KEYPAD — each pairing a 6502 driver with a BBC BASIC front-end held under a rudimentary bit-rotation protection. The original driver software is © 1983 Custom Video Productions; the annotations and disassembly scripts here are © 2026 Acornaeology.

Each program pairs a 6502 machine-code driver with a BBC BASIC front-end that is held under a rudimentary bit-rotation protection. The disassembly names and comments the machine code, and carries the BASIC as editable source that is re-encoded to the original bytes at build time.

## Programs

- **Voltmace Delta 14B/1 KEYPAD loader and resident driver**
  - [Formatted disassembly on acornaeology.uk](https://acornaeology.uk/voltmace-delta14b-driver/keypad.html)
- **Voltmace Delta 14B/1 JOYSTIK loader**
  - [Formatted disassembly on acornaeology.uk](https://acornaeology.uk/voltmace-delta14b-driver/joystik.html)

## Documentation

Longer-form articles on how the system works and how this repository rebuilds it:

- [The Voltmace Delta 14B driver system: architecture and runtime](docs/analysis/system-architecture.md)
  How the original system fits together: the handset hardware, the two protected programs, the ROL-1 obfuscation and loader, the BASIC front-ends that configure the drivers, and the resident 6502 drivers that hook EVNTV (KEYPAD, a keyboard the MOS polls) and BYTEV (JOYSTIK, an INKEY the MOS asks).
- [Reproducing the originals: sources, build and verification](docs/analysis/build-and-verification.md)
  How the modern build regenerates the KEYPAD/JOYSTIK files byte-for-byte from editable sources (annotated assembly + detokenised BASIC), re-encrypting a greedy-tokenised, ROR-rotated incbin payload and assembling the JOYSTIK driver variants back to bytes; and the whole-file verification that keeps it honest.
- [How the KEYPAD editor (BASIC front-end) works](docs/analysis/keypad-editor.md)
  A line-by-line walkthrough of the KEYPAD keypad-definition editor: reading the configuration DATA tables, the interactive key editor, the matrix scan, and how PROCFIN pokes the resident driver's key table and installs it.
- [How the JOYSTIK editor (BASIC front-end) works](docs/analysis/joystik-editor.md)
  A line-by-line walkthrough of the JOYSTIK configuration/demo program: joystick-configuration choice, the Acornsoft-game presets, defining keys, and how PROCASSEM copies a driver variant to &A00, pokes joystick_map, and patches the chain slot and thresholds.

## How it works

The machine code is disassembled by a Python script that drives [dasmos](https://github.com/acornaeology/dasmos), a programmable disassembler for 6502/65C02 binaries with a byte-faithful round-trip oracle. The script feeds the original program image to dasmos along with annotations — entry points, labels, the load-time relocation, and comments — to produce readable assembly.

The embedded BASIC front-end is stored bit-rotated and tokenised. It is kept in the repository as **detokenised source** (`versions/*/basic/*.bas`); the build re-tokenises it with [oaknut-basic](https://pypi.org/project/oaknut-basic/)'s greedy crunch and rotates the bytes back, emitting it as a beebasm `incbin` payload so the whole program still reassembles byte-for-byte.

The output is verified by reassembling the complete file with [beebasm](https://github.com/stardot/beebasm) and comparing it byte-for-byte against the original. This whole-file round-trip runs automatically in CI on every push.

The analysis surface around dasmos (verify, lint, audit, cfg, comments, …) is provided by [fantasm](https://acornaeology.github.io/fantasm/) — see its docs for the full command and API reference.

## Disassembling locally

Requires [uv](https://docs.astral.sh/uv/) and [beebasm](https://github.com/stardot/beebasm) (v1.10+).

```sh
uv sync
uv run fantasm disassemble keypad
uv run fantasm verify keypad
uv run fantasm disassemble joystik
uv run fantasm verify joystik
```

## (Re-)Assembling locally

The listing includes the BASIC payload via a relative `incbin`, so run [beebasm](https://github.com/stardot/beebasm) from the version's `output/` directory (where the generated `.dat` sits beside the `.asm`):

```sh
( cd versions/voltmace-delta-14b-driver-keypad/output &&
  beebasm -i voltmace-delta-14b-driver-keypad.asm -o KEYPAD )
( cd versions/voltmace-delta-14b-driver-joystik/output &&
  beebasm -i voltmace-delta-14b-driver-joystik.asm -o JOYSTIK )
```

## References

- [SN74LS157 quad 2-line to 1-line data selector/multiplexer datasheet](docs/sn74ls157.pdf)
  The multiplexer in the Delta 14B/1 interface that strobes the two handsets under software control.

## Credits

- [dasmos](https://github.com/acornaeology/dasmos) — programmable 6502/65C02 disassembler used to produce the annotated assembly
- [oaknut-basic](https://pypi.org/project/oaknut-basic/) — BBC BASIC (de)tokeniser used to carry the front-end as editable source
- [beebasm](https://github.com/stardot/beebasm) by Rich Mayfield and contributors

## License

The annotations and disassembly scripts in this repository are released under the [MIT License](LICENSE). The original program images remain the property of their respective copyright holders.
