# Glossary

Terms used across the Voltmace Delta 14B driver disassemblies — the handset hardware, the BBC Micro interfaces it uses, and the conventions of these particular programs.

## Voltmace hardware

**Delta 14B**
: A Voltmace handset combining a 3x4 keypad (a 12-key matrix) with a two-axis analogue joystick and two fire buttons. It has a 15-way D-connector that can plug straight into the BBC Micro's analogue port, but that exposes only two of the buttons.

**Delta 14B/1**
: The interface unit that unlocks the full handset. It connects to both the analogue port and the user port and lets two Delta 14B handsets be used at once, strobing them under software control through a 74LS157 multiplexer.

**Handset**
: One Delta 14B unit. The driver scans two handsets, selected by bit 7 of the value written to user-port B.

**74LS157**
: A quad 2-line-to-1-line data selector/multiplexer in the Delta 14B/1. A single select line (driven from user-port B bit 7) chooses which of the two handsets' matrix lines reach the BBC Micro, so one set of port lines reads both.

**CVP — Custom Video Productions**
: The publisher of this driver software (the on-screen and in-code copyright, 1983).

## BBC Micro interfaces

**User port**
: A general-purpose 8-bit parallel port on the BBC Micro, driven by the user 6522 VIA. The keypad matrix is strobed and read through port B here.

**User VIA**
: The 6522 Versatile Interface Adapter behind the user port. Port B input/output register is at `&FE60`; its data-direction register (DDRB) is at `&FE62`. Writing DDRB = `&F0` makes the top nibble outputs (column strobes and the 74LS157 select) and the bottom nibble inputs (the matrix rows).

**Analogue port**
: The BBC Micro's four-channel analogue-to-digital port, used to read the joystick potentiometers.

**EVNTV**
: The MOS event vector at `&0220`. The driver points it at its own handler so it runs on every enabled event.

**Vertical-sync event**
: MOS event 4, raised once per 50 Hz frame. Enabled with `OSBYTE 14` (`&0E`); the driver uses it to poll the keypad matrix in the background.

**OSBYTE / OSWORD / OSCLI**
: MOS entry points at `&FFF4` / `&FFF1` / `&FFF7`. The driver uses `OSBYTE &99` to insert a key into the keyboard buffer, `OSWORD 7` to make the key-click sound, and `OSCLI` to issue `*` commands.

**Soft-key buffer**
: The MOS function-key (`*KEY`) definition buffer in page `&0B`. The driver's relocation deliberately skips this page so the user's key definitions survive.

## Program conventions

**Load-and-run program**
: A `*RUN` file that loads into main memory (here at `&1900`) and executes at its DFS execution address — as opposed to a sideways or parasite ROM. The whole file must reassemble byte-for-byte.

**Relocation**
: The driver is stored in the file at `&1900` but written to run at `&0A00`. The loader copies it down before it runs; the disassembly models this with dasmos's `add_move`.

**ROL-1 protection**
: The rudimentary protection on the embedded BASIC: every byte is rotated left one bit. The loader rotates it back (a right rotation) in memory before running it. Recover the source by rotating left; re-encode for the build by rotating right.

**Greedy crunch**
: The tokeniser behaviour that reproduces these programs' BASIC. The originals were tokenised by a tool greedier about keyword recognition than the BBC BASIC ROM (it lets a keyword interrupt a hex constant or a name, and suppresses a conditional keyword only before a non-keyword name char). `oaknut-basic tokenise --crunch greedy` reproduces it; the default ROM crunch does not.

**incbin payload**
: The BASIC front-end is carried in the repository as detokenised source (`basic/*.bas`) and re-encoded to the exact original bytes at build time, which the listing pulls in with a beebasm `incbin` directive (the `.dat` file beside the `.asm`).
