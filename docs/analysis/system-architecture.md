# The Voltmace Delta 14B driver system: architecture and runtime

> **Scope.** This article describes how the original Voltmace Delta 14B/1
> software fits together — the hardware it drives, the two programs
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

## 2. Two programs with a common design

The software ships two `*RUN` programs — [`KEYPAD`](../../versions/voltmace-delta-14b-driver-keypad/binary/KEYPAD)
and [`JOYSTIK`](../../versions/voltmace-delta-14b-driver-joystik/binary/JOYSTIK)
— that share a design. Each is a single file that loads into main memory at
`&1900` and contains three kinds of thing:

1. a small **loader** in plain 6502;
2. one or more **resident drivers** in 6502, and a **tokenised BBC BASIC**
   configuration program stored **bit-rotated** as protection (in KEYPAD only the
   BASIC is rotated; the resident driver is stored plain — see §5/§6);
3. some **leftover / padding bytes** — and, in JOYSTIK, a **decoy** stub at the
   very start (see §3).

The loader decrypts the protected region, writes the correct length byte back
into the BASIC's first line (the protection stores it as zero), and hands control
to it; the BASIC lets the user configure a resident driver and then installs it;
the resident driver stays in memory and makes the handset look like the keyboard
to ordinary games. They differ in *which* MOS mechanism the resident driver hooks — and
that difference is the heart of the system.

Three roles recur throughout, and this article names them consistently: the
**driver loader** (the plain-6502 bootstrap that decrypts the image and hands
off), the **BASIC front-end** (the configuration program the user drives), and
the **resident driver** (the 6502 code that stays in memory and makes the
handset look like the keyboard).

## 3. The protection

The protection is light — enough to stop casual `*LOAD`/`LIST`
snooping, not a serious barrier. It has four parts:

- **A decoy (JOYSTIK only).** JOYSTIK's first nine bytes at `&1900` are
  `0D 00 0D 60 60 60…` — a stub that reads as a broken BASIC line, so a naive
  `*LOAD "JOYSTIK"` + `LIST` at PAGE shows junk. Its execution address (`&1909`)
  deliberately starts on the byte just past the stub. KEYPAD has no decoy: its
  file opens on the resident driver itself and its loader sits in the tail (exec
  `&3906`), so its snoop-resistance rests on the encrypted, relocated BASIC
  (below), not on a fake first line.
- **ROL-1 encoding.** A contiguous region is stored with every byte **rotated
  right one bit**. The loader rotates each byte left again (`ASL A : ADC #0`, a
  left-rotate) in place to recover the plaintext; re-encode by rotating right.
  This is the `decode_basic` routine in each loader — named "ROL-1" after that
  decode step.
- **A corrupted first line.** The tokenised BASIC's first line is a `REM` whose
  **length byte is stored as 0**. Even after decryption the program cannot be
  `LIST`ed or `RUN` until the loader writes the true length back (`&16` for
  KEYPAD, `&17` for JOYSTIK) — the `patch_header`/`patch_basic_header` routine.
  The `REM` text is literally `PROTECTION 3=&16` / `=&17`.
- **Self-erasure.** When the user finishes configuring, the BASIC blanks its own
  program text (a `FOR … !A%=0` sweep) and detaches, leaving only the resident
  driver in memory. Both programs also booby-trap the **BREAK key** — a BBC Micro
  has no f10, so soft key 10 (`*KEY10`) is the "break string" a soft BREAK types,
  and it is set to a self-destruct — and issue `*FX200,2` so a BREAK also clears
  user memory. So an interrupted session erases rather than exposes the program
  (hence the "DO NOT PRESS BREAK" warnings), while ESCAPE is deliberately left
  live as the handled "restart" path.

Each BASIC configuration program carries a `Z%` flag that would select an
unprotected/developer mode — leaving the editor listable, and (in JOYSTIK)
printing `UNPROTECTED` rather than `PROGRAM PROTECTED`. But `Z%` is a resident
integer (`&468`) left at `0` in the shipped software and never changed, so the
protected behaviour always runs; the `Z%=1` paths are effectively dead code.

## 4. The driver loader (plain 6502)

The **driver loader** is the only part that runs in place — without first being
decrypted or (as the resident driver is) relocated. Its
job is identical in both programs, though it sits at opposite ends of the file (KEYPAD's
is a *tail* at `&3906`, JOYSTIK's is a *head* at `&1909`, matching each file's
execution (`*RUN`) address):

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

The resident driver installs by enabling the **50 Hz vertical-sync event** (OSBYTE 14,
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
it overwrites the 24-entry `key_codes` table inside the resident driver (at
`&ADD`) — which the image ships pre-filled with a default layout, so KEYPAD's
driver is a template carrying working defaults rather than a blank one —
sets the driver's two behaviour options — whether a keypress sounds the
key-click (the OSWORD 7 call above) and whether keys auto-repeat — and `CALL &A00`
installs it.

## 6. JOYSTIK: an INKEY the MOS asks

JOYSTIK is more elaborate. Here the resident drivers ship as **configurable
templates inside the encrypted region** — two 256-byte variants at `&1A00` and
`&1B00`, both ROL-encoded and both written to run at `&0A00`. They are stored
with their `joystick_map` keys, thresholds and BYTEV chain slot blank; the BASIC
front-end copies the chosen template to `&0A00`, pokes those fields, and installs
the result. See
[`driver-a.asm`](../../versions/voltmace-delta-14b-driver-joystik/output/voltmace-delta-14b-driver-joystik-driver-a.asm)
and [`driver-b.asm`](../../versions/voltmace-delta-14b-driver-joystik/output/voltmace-delta-14b-driver-joystik-driver-b.asm).

Rather than *push* keys into the buffer, the JOYSTIK resident driver is **called
when the game reads the keyboard**. It hooks **BYTEV** (`&020A`, the OSBYTE
vector) and intercepts **OSBYTE `&81` (INKEY)**. A game that reads the keyboard
with `INKEY(-key)` calls OSBYTE `&81` with a negative key number; the resident
driver checks that number against its `joystick_map` and, if it matches, reads
the corresponding input and returns a "pressed" result (`X=Y=&FF`).
Every other OSBYTE is passed on to the previous handler through a chain slot
(`&AFA`) that the BASIC patches to `JMP <old BYTEV>`.

`joystick_map` is a table of `<INKEY key, descriptor>` pairs. The **key** byte
is 0 in the file; the BASIC pokes it with the user's chosen `INKEY` value. The
**descriptor** is fixed and decodes per variant:

- the **joystick-only** resident driver (variant A): descriptors below index 8
  are joystick axes (top nibble = ADC channel; the low bit picks the high or low
  sensitivity threshold); the rest are fire buttons (`ADVAL(0)` bit masks).
- the **joystick + keypad** resident driver (variant B): the later entries
  instead strobe a **keypad column** (top nibble) through user-port B and test a
  **row bit** (low nibble) — the same matrix scan KEYPAD uses.

The **BASIC front-end** ([`joystik-editor.md`](joystik-editor.md))
lets you pick a joystick configuration (which selects the joystick-only or
joystick + keypad template, `H%=7` vs. `H%=35`), choose a ready-made
mapping for an Acornsoft game or define your own, test it live, tune the
sensitivity, and finish. `PROCASSEM` copies the chosen template to
`&A00`, pokes `joystick_map` with the mapping, patches the chain slot and
thresholds, and `CALL &A00` installs the configured resident driver.

## 7. Two ways to fake a keyboard

The contrast between the two programs is the interesting part of the system:

| | **KEYPAD** | **JOYSTIK** |
|---|---|---|
| MOS hook | EVNTV (event 4, vsync) | BYTEV (OSBYTE `&81`) |
| Model | **push** — polls the hardware each frame and *injects* keys | **pull** — answers `INKEY(-key)` on demand from the hardware |
| Hardware read | user-port matrix scan | analogue (ADVAL) + optional matrix scan |
| Compatible with | anything reading the keyboard buffer | games using `INKEY(-key)` |
| Resident driver storage | plain (relocated) | ROL-encrypted, two variants |

Both end at the same place: a resident driver at `&0A00–&0AFF` that makes
the Voltmace hardware indistinguishable from keyboard input to an unmodified
game, which can then be `*SAVE`d and re-installed with `*KEY10 CALL &A00`.

## 8. Runtime lifecycle

Putting it together, a run of either program goes:

1. `*RUN` loads the file at `&1900` and jumps to its exec address.
2. The **loader** decrypts the protected region, restores the length byte in the
   BASIC's first line, and queues `PAGE=…`/`OLD`/`RUN`.
3. The OS reads those queued commands and the **BASIC configuration program**
   starts.
4. The user configures the resident driver; the BASIC **pokes and installs** it
   at `&0A00` (hooking EVNTV or BYTEV).
5. On finishing, the BASIC program prints instructions telling the user how to
   `*SAVE` the now-configured resident driver (to tape or disc), **erases its own
   program text**, and ends — leaving the resident driver in place.
6. The user loads their game; the resident driver translates handset input into
   the key presses the game expects.
