# The JOYSTIK editor (BASIC front-end)

This describes the BBC BASIC program in
[`voltmace-delta-14b-driver-joystik.bas`](voltmace-delta-14b-driver-joystik.bas) —
the user-facing half of the Voltmace Delta 14B JOYSTIK software. Line numbers
below refer to that program.

## What it is for

The Delta 14B handset has a two-axis analogue joystick, two fire buttons, and
(via the Delta 14B/1 adaptor) a keypad. Games written for the keyboard can't use
it directly. This program lets you **map joystick directions, fire buttons and
keypad keys onto keyboard keys**, then installs a small machine-code driver that
makes those inputs look like key presses to any game that reads the keyboard
with `INKEY(-key)` (lines 500–510 explain that convention to the user).

You pick a joystick configuration, choose a ready-made mapping for an Acornsoft
game (or define your own), optionally test and tune it, and finish. The driver
then stays resident at `&A00–&AFF` while your game is loaded and run.

The companion machine code — the two driver variants this program installs — is
covered by the disassemblies in
[`../output/voltmace-delta-14b-driver-joystik-driver-a.asm`](../output/voltmace-delta-14b-driver-joystik-driver-a.asm)
and
[`driver-b.asm`](../output/voltmace-delta-14b-driver-joystik-driver-b.asm).

## Shape of the program

| Lines | Role |
|-------|------|
| 10–170 | Startup, protection clean-up, OS check, array `DIM`s |
| 190–240 | Main flow: intro, init, game select, edit, build, menu |
| 250–272 | Error handling |
| 280–520 | `PROCINTRO` — copyright, joystick-configuration choice, help |
| 530–600 | Screen furniture (`PROCCONT`, `PROCWARN`, `PROCSCREEN`, `PROCFUNCTION`) |
| 610–990 | `PROCGAME` — pick a preset game mapping or user-define; the `DATA` tables |
| 1000–1240 | Key display/entry (`PROCEDIT`, `PROCKEY`, `PROCDEFAULTPRINT`) |
| 1080–1190 | `PROCINIT` — key-name, `INKEY`-value, sensitivity and channel tables |
| 1250–1370 | `PROCFINI` — how to save the driver and load your game |
| 1380–1460 | `PROCTERM` — the Edit / Test / Sensitivity / Finish menu |
| 1470–1710 | `PROCTEST` — live display of joystick, buttons and keypad |
| 1720–1870 | `PROCASSEM` — build and install the driver |
| 1880–1930 | `PROCJOY` — adjust joystick sensitivity |
| 1960–2010 | Finish: wipe the program, leave the driver running |

## Startup and protection (10–170)

Line 10 is a `REM` whose length byte is stored as 0 and repaired to `&17` by the
loader before the program runs. Line 50 selects MODE 7 and saves the current
BYTEV (`OVL%=?&20A:OVH%=?&20B`) — the previous OSBYTE vector, which the driver
will chain to. Line 80, on a protected first run, blanks memory. Line 90 reads
the OS version (`?&F0C7`/`?&F0C8`), and lines 140–150 dimension the working
arrays.

## Intro and joystick configuration (280–520)

`PROCINTRO` shows the copyright, then (lines 350–400) asks which configuration is
in use:

- **Single joystick** (`S`) — line 370 sets `H%=7`, so `PROCASSEM` later installs
  **driver variant A** (analogue joystick only).
- **1 or 2 joysticks + adaptor box** (`1`/`2`) — lines 380–390 set `H%=35`, so
  **driver variant B** is installed (which also scans the keypad matrix). Lines
  480–481 warn that some programs pulse User-Port P7 and can disturb the keypad.

Lines 420–510 explain that the driver simulates up to `J%` keyboard keys and is
compatible with games that read the keyboard via `INKEY(-key)`.

## Choosing a mapping (610–990)

`PROCGAME` lists eight choices (line 610): **user-defined** plus seven Acornsoft
games (named in the `T$` table, line 1150). Selecting one (line 640) `RESTORE`s
to the matching `DATA` line (810–960 for single joystick, 890–960 for the adaptor
configurations) and reads a preset list of `INKEY` key numbers into `V%()` — the
key each joystick input should emulate for that game.

## Initialisation tables (1080–1190)

`PROCINIT` sets the sensitivity (`SEN%`, and the thresholds `SL%`/`SH%`, line
1080), then reads:

- **`K$()`** (line 1100) — printable key names (`f0`…`f9`, `A`…`Z`, digits,
  symbols, `ESCAPE`, cursor keys, …).
- **`N%()`** (line 1120) — the `INKEY` (negative-`INKEY`) value for each of those
  keys.
- **`T$()`** (line 1150) — the game names.
- **`C$()`** (line 1170) and **`CH%()`** (line 1180) — the on-screen labels and
  ADC channel for each joystick input (direction, fire, keypad cell).

## Defining and displaying keys (1000–1240)

For user-defined mappings, `PROCEDIT` (line 1020) restores the saved BYTEV so the
keyboard reads normally, then `PROCKEY` (line 1200) waits for you to hold a key,
identifies it by scanning `INKEY(-N%(n))` for every key, and records its `INKEY`
value in `V%()`. `PROCDEFAULTPRINT` (line 1040) shows the current mapping.

## Building the driver (1720–1870)

`PROCASSEM` turns the mapping into a working resident driver:

- Line 1730 recovers the previous BYTEV (`R%`) to chain to.
- Line 1740 points `TBL%` at `&AB0` — the driver's `joystick_map`.
- Line 1750 chooses the driver **source**: `&1A00` (variant A) when `H%=7`, else
  `&1B00` (variant B).
- Line 1760 copies that 256-byte variant down to `&A00`.
- Lines 1780–1830 poke the mapping into `joystick_map`: each 2-byte entry gets the
  negated `INKEY` value (`-V%(...)`) the driver should respond to.
- Line 1840 patches the chain slot: `?&AFA=&4C` (a `JMP` opcode) with `&AFB/&AFC`
  set to `R%`, so non-`INKEY` OSBYTEs pass to the original vector.
- Line 1850 writes the sensitivity thresholds into `&AFD`/`&AFE`.
- Line 1860 `CALL &A00` runs the install routine, hooking BYTEV.

## Test, tune and finish (1380–2010)

`PROCTERM` (line 1380) offers **Edit / Test / Alter sensitivity / Finish**.
`PROCTEST` (line 1470) shows a live grid: `PROCDISAD`/`PROCDISLOW`/`PROCDISHIGH`
threshold the analogue axes (`ADVAL`), `PROCDISFIRE` reads the fire buttons
(`ADVAL(0)`), and `PROCDISUP` reads the keypad matrix through the User VIA.
`PROCJOY` (line 1880) re-computes `SL%`/`SH%` from a 1–9 sensitivity and re-pokes
`&AFD`/`&AFE` live. `PROCFINI` (line 1250) tells you how to `*SAVE` the driver
(`*SAVE <name> A00 +100`) and re-install it later (`*KEY10 CALL &A00`). The
finish code (lines 1960–2010) blanks and detaches the program, leaving only the
resident, configured driver.
