# The KEYPAD editor (BASIC front-end)

This describes the BBC BASIC program in
[`voltmace-delta-14b-driver-keypad.bas`](../../versions/voltmace-delta-14b-driver-keypad/basic/voltmace-delta-14b-driver-keypad.bas) —
the user-facing half of the Voltmace Delta 14B KEYPAD software. Line numbers
below refer to that program.

## What it is for

The Delta 14B handset has a 12-key keypad. On its own the BBC Micro cannot tell
those keys apart, so this program lets you **define what each keypad key sends**
and then installs a small machine-code driver that makes the keypad behave like
a set of extra keyboard keys.

You interact with an on-screen picture of the keypad: press a key **on the
handset** to select it, then press the key **on the BBC keyboard** whose
character (or control code, function key, cursor key, …) that keypad key should
produce. Two handsets can be defined independently. When you finish, the program
writes your definitions into the driver, installs it at `&0A00`, and (for the
disc version) wipes itself, leaving the driver resident. The driver then scans
the keypad on every 50 Hz vertical-sync event and feeds your characters into the
keyboard buffer.

The companion machine code — the driver the editor configures and installs — is
covered by the disassembly in
[`voltmace-delta-14b-driver-keypad.asm`](../../versions/voltmace-delta-14b-driver-keypad/output/voltmace-delta-14b-driver-keypad.asm).

## Shape of the program

| Lines | Role |
|-------|------|
| 10–170 | Startup, protection clean-up, OS check, intro screens |
| 180–280 | Main loop and error handling |
| 290–410 | `PROCINIT` — initialise hardware and read the configuration tables |
| 420–510 | Drawing the on-screen keypad |
| 520–740 | The interactive editor (select a key, assign a character) |
| 750–840 | `PROCREADKP` — scan the physical keypad matrix |
| 850–1070 | Screen furniture: headers, instructions, the intro slideshow |
| 1080–1210 | `PROCMENU` — the Sound / Auto / Edit / Finish options |
| 1220–1340 | `PROCFIN` — build, patch, and install the driver |
| 1350–1370 | Finish: wipe the editor and leave the driver running |

## Startup and protection (10–170)

Line 10 is a `REM` that only exists because of the load-time protection: its
length byte is stored as zero in the file and repaired to `&16` by the loader
before the program can run.

Line 30 selects MODE 7, clears the status flags (`Z%`, `E1%`, `E2%`), and sets
the error handler to line 220. `Z%` records whether the program is still running
under protection (`Z%=0`) or has been re-saved unprotected.

Line 60, on a protected first run, zeroes memory from `&C00` to `&3A80` — the
scaffolding the loader used to relocate and decrypt everything — so nothing of
the protection remains once the editor is up.

Lines 70–120 guard against an incompatible operating system: `?&E8AA` is read
as an OS signature (the expected value is `&4F`); on a mismatch the program
displays "KEYPAD DRIVER WILL NOT WORK WITH OPERATING SYSTEM OS 0.1" (line 90)
and stops. Line 130 issues `*FX200,2` (BREAK clears memory, part of the
protection), line 150 dimensions the arrays, and line 170 shows the intro
(`PROCINTRO`) before switching to MODE 1 for the editor.

## Main loop (180–280)

Line 180 draws the header (`PROCH1`), the instructions (`PROCINS`), and runs the
editor (`PROCEDIT`). Line 190 then shows the options menu (`PROCMENU`), which
returns a choice in `Q$`:

- `Q$="E"` (line 200) — re-edit: go back to line 180.
- `Q$="F"` (line 210) — finish: `PROCFIN` builds and installs the driver, then
  the program either `STOP`s (protected) or jumps to the wipe-and-run code at
  1350.

Lines 220–280 are the error handlers, including the "SYSTEM ERROR" report
(line 250) and the ESCAPE-driven restart (error 17).

## Initialisation and the configuration tables (290–410)

`PROCINIT` (line 290) enables the cursor-key/`*FX4` mode, then (line 300) sets
the User VIA data-direction register `?&FE62=&F0` (top nibble outputs for the
column strobes and handset select, bottom nibble inputs for the rows) and clears
the working variables.

The `DATA` statements are read straight into the editor's arrays:

- **Line 320** (`8,4,2,1,0,&60,&50,&30`), read by line 310 → `ROW%()` then
  `COL%()`. `ROW%(0..3)=8,4,2,1` are the **row bit-masks** and `COL%(0..2)=&60,
  &50,&30` are the three **column strobes** — the same scan constants the
  machine-code driver uses. (`ROW%(4)=0` is a sentinel; the loop over `COL%`
  reads one value too many, harmlessly, before line 330's `RESTORE` resets the
  data pointer.)
- **Line 340** (45 values), read by line 330 as **15 keys × (X, Y, colour)** into
  `KPOS%(N%,0..2)` — the screen position and MODE-1 colour for drawing each key.
  The layout is a 3-column (X = 1, 10, 19) by 5-row (Y = 22, 17, 12, 7, 1) grid:
  the 12 keypad keys plus 3 extra cells (e.g. the REAR/SIDE fire button drawn for
  key 13).
- **Lines 370 + 380** (one continuous list ending in `-1`), read by line 350 as
  **code/name pairs** into `ACHR%()`/`ACHR$()`. This is the dictionary used to
  show a readable label when a key is assigned a non-printable code: the VDU
  control codes (`2`→`P ON`, `12`→`CLS`, `13`→`RET`, `127`→`DEL`, …) in line 370,
  and the "high" keys (`&90..&9A`→`f0..f10`, `135`→`COPY`, `136..139`→the four
  cursor keys, `0`→`ESC`) in line 380.
- **Line 400** (30 values), read by line 390 as **2 handsets × 15 keys** into
  `KNUM%(N%,KP%)` — the **default character** each key sends. `KP%=0` is the
  numeric handset (`DEL, 0, RETURN, 1…9`); `KP%=1` is an editing/function handset
  (DEL, cursor keys, `HOME`, `COPY`, `CLS`, `f0`, `RETURN`, `f1`, …). `PROCCONV`
  turns each code into its on-screen label as it is read.

## Drawing the keypad (420–510)

`PROCKEYPAD` (line 420) draws all 15 keys and the copyright line. `PROCBKKEY`
(430) draws a key in its unselected colour, `PROCWTKEY` (440) draws the currently
selected key highlighted and shows its assigned character. The workhorse is
`PROCkey` (450–500): it positions itself from `KPOS%()`, prints the label from
`KCHR$(N%,KP%)`, and special-cases key 13, which shows `REAR` or `SIDE`
(the handset's two fire buttons) rather than a character.

## The interactive editor (520–740)

`PROCEDIT` (line 520) is the core loop:

1. Draw the keypad and take the current selection `N%=CURKEY%` (530).
2. Highlight it (`PROCWTKEY`, 540) and scan the physical keypad (`PROCREADKP`,
   550).
3. If a *different* keypad key is now pressed (line 560), move the highlight to it
   and beep.
4. Read a BBC keyboard key with `K%=INKEY(5)` (570). Lines 580–590 handle the
   flashing highlight and the `CTRL Q` (`K%=17`) exit.
5. `CTRL A` (`K%=1`, lines 600–610) toggles between the two handsets (`KP%`) and
   redraws.
6. Otherwise (line 620) `PROCCONV` turns the pressed key into a display string,
   `PROCYEL` stores it, `PROCSND` beeps, and the loop repeats.

Supporting routines:

- `PROCCONV` (630–640): a printable key (`32<K%<127`) becomes its own centred
  character; anything else is looked up via `PROCSPECIAL`.
- `PROCSPECIAL` (710–740): search the `ACHR%()` table for the code and take the
  matching `ACHR$()` label.
- `PROCPAD` (650–680): pad a label to a fixed 5-character cell.
- `PROCYEL` (700): store the new code in `KNUM%(N%,KP%)`; key 10 is mirrored onto
  keys 12 and 14 (a wide key occupying three cells).

## Scanning the physical keypad (750–840)

`PROCREADKP` reads the handset matrix directly through User VIA port B (`&FE60`),
exactly as the driver does. Line 750 selects the handset by writing `KP%*&80`
(bit 7 drives the 74LS157 multiplexer) and checks for "no key". The nested loops
(780–830) strobe each column (`?&FE60=COL%(X%)+&80*KP%`) and test each row
(`?&FE60 AND ROW%(Y%)`); a pressed cell yields `CURKEY%=3*CURROW%+CURCOL%`.

## Screens and presentation (850–1070)

These procedures build the MODE-1/MODE-7 screens: `PROCH1`/`PROCHEAD`/`PROCBIG`
(double-height banners), `PROCA1`/`PROCA2` (text windows), `PROCWARN` (the
"DO NOT PRESS BREAK" line), `PROCINS` (the how-to-use instructions, 890–900), and
`PROCINTRO` (910–1010), the copyright-and-explanation slideshow shown at startup.
`PROCCONT` (1050–1070) is the "PRESS SPACE-BAR TO CONTINUE" pause. The intro text
explains that the driver installs at `&A00–&AFF` and runs under EVENT 4 (vertical
sync), which the driver enables itself (lines 950–960).

## The options menu (1080–1210)

`PROCMENU` offers four choices keyed S / A / E / F: **Sound** (beep on keypad
press, toggled by `B%`, `PROCONOFF`), **Auto** repeat (`A%`, `PROCAUTO`),
**re-Edit**, and **Finish**. Lines 1130–1180 read the choice into `Q$` and return
it to the main loop.

## Building and installing the driver (1220–1340)

`PROCFIN` turns the on-screen definitions into a working driver:

- Lines 1220–1230 tell the user how to save/reload the resulting driver
  (`*SAVE MC A00 +100`, `*KEY10 CALL&A00`).
- Lines 1240–1280 rewrite the stored codes into the form the driver inserts:
  function-key codes in `&87–&8B` are nudged by 4, codes in `&90–&9B` are reduced
  by `&10`, and a zero becomes `&1B` (ESCAPE).
- **Line 1290** pokes the finished 24-entry table into the driver:
  `?(&ADD+4*C%+R%+12*KP%)=KNUM%(3*R%+C%,KP%)`. `&ADD` is the driver's `key_codes`
  table (see the machine-code disassembly), indexed by `column*4 + row +
  12*handset` — this is the bridge between the editor and the resident driver.
- Line 1300 patches the driver to enable auto-repeat if selected; line 1310
  patches the sound block for the beep option.
- Line 1330 `CALL &A00` runs the driver's install routine (enable the vsync
  event, set the port directions, hook `EVNTV`).

## Finishing (1350–1370)

Reached when the program is running unprotected (from disc): line 1350 wipes the
BASIC program (`FOR N%=PAGE TO PAGE+&1C00 STEP4:!N%=0`), leaves an empty program
(`!PAGE=&FF0D`), re-arms `*KEY10 CALL&A00`, and prints "KEYPAD OPERATIONAL". Line
1370 resets `PAGE` and `END`s, leaving only the resident, now-configured driver
in memory.
