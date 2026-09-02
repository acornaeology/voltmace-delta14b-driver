# The Voltmace Delta 14B driver system: architecture and runtime

> **Scope.** This article describes how the original Voltmace Delta 14B/1
> software fits together — the hardware it drives, the two programs on the disc
> (`KEYPAD` and `JOYSTIK`), the rudimentary protection wrapping them, the BBC
> BASIC front-ends that configure the drivers, and the resident 6502 drivers
> that hook into the Acorn MOS. Every address and behaviour below was read from
> the annotated disassemblies in this repository, which reassemble
> byte-identically to the original files. A companion article,
> [Reproducing the originals](build-and-verification.md), explains how the
> modern build regenerates those files from editable sources.

---

## 1. The hardware

The **Voltmace Delta 14B** handset combines three input devices in one unit: a
**3×4 keypad** (a 12-key matrix), a **two-axis analogue joystick**, and two
**fire buttons**. Its 15-way D connector can plug straight into the BBC Micro's
analogue port, but that port only distinguishes two of the buttons.

The **Delta 14B/1 interface** unlocks the rest. It connects to *both* the
analogue port and the **user port**, and lets two handsets be used at once. A
**74LS157** quad 2-to-1 multiplexer inside it selects which handset's keypad
lines reach the user-port VIA, under software control: bit 7 of user-port B
drives the select line. So the software strobes the keypad matrix through the
user 6522 VIA (`&FE60`/`&FE62`), reads the joystick pots through the analogue
port (via OSBYTE `&80` / ADVAL), and picks the active handset with the top bit
of the port-B value.

## 2. Two programs, one shape

The disc ships two `*RUN` programs — [`KEYPAD`](../../versions/voltmace-delta-14b-driver-keypad/binary/KEYPAD)
and [`JOYSTIK`](../../versions/voltmace-delta-14b-driver-joystik/binary/JOYSTIK)
— that share a design. Each is a single file that loads into main memory at
`&1900` and contains three kinds of thing:

1. a small **loader** in plain 6502;
2. one or more **resident drivers** in 6502, and a **tokenised BBC BASIC**
   configuration program, both stored **bit-rotated** as protection;
3. a **decoy** and some leftover bytes.

The loader decrypts the protected region, repairs the BASIC, and hands control
to it; the BASIC lets the user configure a driver and then installs it; the
driver stays resident and makes the handset look like the keyboard to ordinary
games. They differ in *which* MOS mechanism the driver hooks — and that
difference is the heart of the system.

## 3. The protection

The protection is deliberately light — enough to stop casual `*LOAD`/`LIST`
snooping, not a serious barrier. It has four parts:

- **A decoy.** The first bytes at `&1900` are `0D 00 0D 60 60 60…` — a stub that
  reads as a broken BASIC line so a naive `*LOAD "KEYPAD"` + `LIST` at PAGE shows
  junk rather than the program.
- **ROL-1 encoding.** A contiguous region is stored with every byte **rotated
  left one bit**. The loader rotates each byte back (`ASL A : ADC #0`, a
  left-rotate) in place. Recover the plaintext by rotating left; re-encode by
  rotating right. This is the `decode_basic` routine in each loader.
- **A corrupted first line.** The tokenised BASIC's first line is a `REM` whose
  **length byte is stored as 0**. Even after decryption the program cannot be
  `LIST`ed or `RUN` until the loader writes the true length back (`&16` for
  KEYPAD, `&17` for JOYSTIK) — the `patch_header`/`patch_basic_header` routine.
  The `REM` text is literally `PROTECTION 3=&16` / `=&17`.
- **Self-erasure.** When the configured driver is finished, the BASIC blanks its
  own program text (a `FOR … !A%=0` sweep) and detaches, leaving only the
  resident driver in memory.

The BASIC is aware of all this: a `Z%` flag distinguishes the protected first run
from an unprotected re-save, and lines print `PROGRAM PROTECTED` / `UNPROTECTED`
accordingly.

## 4. The loader (plain 6502)

The loader is the only part that runs as stored, un-encoded code. Its job is
identical in both programs, though it sits at opposite ends of the file (KEYPAD's
is a *tail* at `&3906`, JOYSTIK's is a *head* at `&1909`, matching each file's
DFS execution address):

1. **`decode_basic`** — ROL-decrypt the protected region in place.
2. **`patch_header`** — restore the first BASIC line's length byte.
3. **`os_dependent_setup`** — read an OS ROM signature (KEYPAD checks one byte at
   `&E8AA` for `'O'`; JOYSTIK checks three, `&E8AA`–`&E8AC`, for `"OS "`) and pick
   how to hand off.
4. **queue the commands** `PAGE=&C00`/`&1C00`, `OLD`, `RUN` into the MOS keyboard
   buffer — either by poking the buffer directly or via OSBYTE `&8A` — so that
   when the loader returns, the OS "types" them and the just-decrypted BASIC
   starts.

The two hand-off paths exist because the direct poke and the OSBYTE route behave
differently across OS versions.

## 5. KEYPAD: a keyboard the MOS polls

KEYPAD is the simpler of the two. Its resident driver is stored *plain* at
`&1900` (it is not part of the encrypted region — only the BASIC is), but it is
written to **run relocated at `&0A00`**; the loader copies it down, deliberately
skipping page `&0B` so the MOS soft-key buffer survives. See
[`…-keypad.asm`](../../versions/voltmace-delta-14b-driver-keypad/output/voltmace-delta-14b-driver-keypad.asm).

The driver installs by enabling the **50 Hz vertical-sync event** (OSBYTE 14,
event 4) and pointing **EVNTV** (`&0220`) at its handler. Thereafter the MOS
calls the handler every frame. The handler:

- sets up user-port B (DDRB `&FE62 = &F0`: strobes and the 74LS157 select as
  outputs, the four rows as inputs);
- strobes each column of the 3×4 matrix for each handset (bit 7 selects the
  handset) and reads the rows;
- debounces and auto-repeats via a countdown;
- on a fresh press, sounds a short key-click (OSWORD 7) and **inserts the mapped
  character into the keyboard buffer** (OSBYTE `&99`), so the key appears exactly
  as if typed;
- chains to the previous event handler.

The **BASIC front-end** ([`keypad-editor.md`](keypad-editor.md))
is an interactive editor: you press a key *on the handset* to select it, then a
key *on the BBC keyboard* to assign its character, for two handsets. On finishing
it pokes the 24-entry `key_codes` table inside the resident driver (at `&ADD`),
patches the sound and auto-repeat options, and `CALL &A00` installs it.

## 6. JOYSTIK: an INKEY the MOS asks

JOYSTIK is richer. Here the drivers are themselves **inside the encrypted
region** — two 256-byte variants at `&1A00` and `&1B00`, both ROL-encoded and
both written to run at `&0A00`. See
[`driver-a.asm`](../../versions/voltmace-delta-14b-driver-joystik/output/voltmace-delta-14b-driver-joystik-driver-a.asm)
and [`driver-b.asm`](../../versions/voltmace-delta-14b-driver-joystik/output/voltmace-delta-14b-driver-joystik-driver-b.asm).

Rather than *push* keys into the buffer, the JOYSTIK driver **answers a question
the game asks**. It hooks **BYTEV** (`&020A`, the OSBYTE vector) and intercepts
**OSBYTE `&81` (INKEY)**. Games that read the keyboard with `INKEY(-key)` — the
Acornsoft convention the BASIC's help screens describe — call OSBYTE `&81` with a
negative key number; the driver checks that key against its `joystick_map` and,
if it matches, reads the corresponding input and returns "pressed" (`X=Y=&FF`).
Every other OSBYTE is passed on to the previous handler through a chain slot
(`&AFA`) that the BASIC patches to `JMP <old BYTEV>`.

`joystick_map` is a table of `<INKEY key, descriptor>` pairs. The **key** byte
is 0 in the file; the BASIC pokes it with the user's chosen `INKEY` value. The
**descriptor** is fixed and decodes per variant:

- **Variant A** (single joystick): descriptors below index 8 are joystick axes
  (top nibble = ADC channel; the low bit picks the high or low sensitivity
  threshold); the rest are fire buttons (`ADVAL(0)` bit masks).
- **Variant B** (with the adaptor box): the later entries instead strobe a
  **keypad column** (top nibble) through user-port B and test a **row bit** (low
  nibble) — the same matrix scan KEYPAD uses.

The **BASIC front-end** ([`joystik-editor.md`](joystik-editor.md))
lets you pick a joystick configuration (which selects variant A or B, `H%=7`
vs. `H%=35`), choose a ready-made mapping for an Acornsoft game or define your
own, test it live, tune the sensitivity, and finish. `PROCASSEM` copies the
chosen variant to `&A00`, pokes `joystick_map` with the mapping, patches the
chain slot and thresholds, and `CALL &A00` installs it.

## 7. Two ways to fake a keyboard

The contrast between the two programs is the interesting part of the system:

| | **KEYPAD** | **JOYSTIK** |
|---|---|---|
| MOS hook | EVNTV (event 4, vsync) | BYTEV (OSBYTE `&81`) |
| Model | **push** — polls the hardware each frame and *injects* keys | **pull** — answers `INKEY(-key)` on demand from the hardware |
| Hardware read | user-port matrix scan | analogue (ADVAL) + optional matrix scan |
| Compatible with | anything reading the keyboard buffer | games using `INKEY(-key)` |
| Driver storage | plain (relocated) | ROL-encrypted, two variants |

Both end at the same place: a small routine resident at `&0A00–&0AFF` that makes
the Voltmace hardware indistinguishable from keyboard input to an unmodified
game, which can then be `*SAVE`d and re-installed with `*KEY10 CALL &A00`.

## 8. Runtime lifecycle

Putting it together, a run of either program goes:

1. `*RUN` loads the file at `&1900` and jumps to its exec address.
2. The **loader** decrypts the protected region, repairs the BASIC's first line,
   and queues `PAGE=…`/`OLD`/`RUN`.
3. The OS reads those queued commands and the **BASIC configuration program**
   starts.
4. The user configures the driver; the BASIC **pokes and installs** it at
   `&0A00` (hooking EVNTV or BYTEV).
5. On finishing, the BASIC prints how to `*SAVE` the driver, **erases its own
   program text**, and ends — leaving the resident driver in place.
6. The user loads their game; the driver quietly translates handset input into
   the key presses the game expects.
