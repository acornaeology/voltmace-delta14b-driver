"""Disassembly driver for the Voltmace Delta 14B/1 KEYPAD driver.

Configures dasmos to produce an annotated disassembly of the KEYPAD *RUN
program. Run via:
  uv run fantasm disassemble keypad
or directly:
  uv run python versions/voltmace-delta-14b-driver-keypad/disassemble/disasm_voltmace_delta_14b_driver_keypad.py

The file loads at &1900 and executes at &3906. Its layout:

  &1900-&19FF  6502 keypad driver (256 bytes), STORED here but written to RUN
               relocated at &0A00 (offset -&F00): install routine + vsync-event
               matrix scanner (User VIA port B &FE60, DDRB &FE62, 74LS157 bit).
  &1A00-&1AFF  image of page &0B, which the relocator deliberately SKIPS so the
               MOS soft-key buffer survives; here it is &10-filler.
  &1B00-&3868  the keypad-definition editor, a tokenised BBC BASIC program,
               stored ROL-encoded (every byte rotated left one bit) as
               rudimentary protection. It relocates to PAGE=&0C00; the first
               line's length byte is stored as 0 and patched to &16 at run time.
  &3869-&3A7F  *RUN entry / relocator-installer (exec &3906): copies the image
               down (driver to &0A00, BASIC to &0C00), decrypts the BASIC,
               and queues PAGE=&C00 / OLD / RUN to start it.

This baseline classifies the ROL-encoded BASIC region as raw data so the
whole file round-trips byte-identically; a later revision will carry that
region as detokenised BASIC source (basic/*.bas) re-encoded at build time.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import dasmos

_script_dirpath = Path(__file__).resolve().parent
_version_dirpath = _script_dirpath.parent
_binary_filepath = (
    os.environ.get('FANTASM_BINARY')
    or os.environ.get('FANTASM_ROM')
    or str(_version_dirpath / 'binary' / 'KEYPAD')
)
_output_dirpath = Path(
    os.environ.get('FANTASM_OUTPUT_DIR', str(_version_dirpath / 'output'))
)
_basic_filepath = _version_dirpath / 'basic' / 'voltmace-delta-14b-driver-keypad.bas'
BASIC_DAT_NAME = 'voltmace-delta-14b-driver-keypad-basic.dat'


def _ror(byte):
    return ((byte >> 1) | ((byte & 1) << 7)) & 0xFF


def build_basic_dat(bas_filepath):
    """Regenerate the ROL-encoded BASIC payload from the editable source.

    Tokenise the detokenised source with oaknut-basic's greedy crunch (the
    tokeniser the original program was built with), reverse the loader's
    line-10 length-byte repair (store it as 0), then rotate every byte right
    one bit — the inverse of the ROL-1 protection the loader decrypts.
    """
    oaknut = shutil.which('oaknut-basic') or str(Path(sys.executable).parent / 'oaknut-basic')
    with tempfile.TemporaryDirectory() as tmp:
        tok_filepath = Path(tmp) / 'basic.tok'
        subprocess.run(
            [oaknut, 'tokenise', str(bas_filepath), str(tok_filepath), '--crunch', 'greedy'],
            check=True,
        )
        tokens = bytearray(tok_filepath.read_bytes())
    tokens[3] = 0x00  # line 10's length byte is stored as 0 (patched to &16 at run time)
    return bytes(_ror(b) for b in tokens)

LOAD_ADDR = 0x1900          # DFS load address
EXEC_ADDR = 0x3906          # DFS execution address (*RUN entry)
DRIVER_RUNTIME = 0x0A00     # the driver is relocated here before it runs
DRIVER_LEN = 0x0100         # &1900-&19FF (256 bytes) -> &0A00-&0AFF
FILLER_START = 0x1A00       # image of page &0B (soft-key buffer), not relocated
FILLER_END = 0x1B00
BASIC_START = 0x1B00        # first byte of the ROL-encoded BASIC (-> PAGE &0C00)
BASIC_END = 0x3869          # one past the &0D &FF terminator

d = dasmos.Disassembler.create(
    cpu='6502',
    auto_label_data_prefix='l',
    auto_label_code_prefix='c',
    auto_label_subroutine_prefix='sub_c',
    auto_label_loop_prefix='loop_c',
)
d.load(_binary_filepath, LOAD_ADDR)

# Load-and-run metadata for a *RUN-able SAVE (DFS load &1900, exec &3906).
d.program(exec_addr=EXEC_ADDR, reload_addr=LOAD_ADDR)

# The driver is stored at &1900 but copied down to &0A00 before execution;
# annotate it at its runtime address.
driver = d.add_move(DRIVER_RUNTIME, LOAD_ADDR, DRIVER_LEN, name='driver')

# Page &0B image (soft-key buffer): the relocator skips it, so these are just
# filler bytes in the file, not code and not relocated.
d.byte(FILLER_START, FILLER_END - FILLER_START)
d.comment(FILLER_START, 'Image of page &0B (the MOS soft-key/function-key '
                        'buffer). The relocator skips page &0B so the user keys '
                        'survive, making these bytes inert filler.')

# The ROL-encoded BASIC program is carried as detokenised source
# (basic/*.bas) and re-encoded to the .dat at build time; include it verbatim.
d.include_binary(BASIC_START, BASIC_END - BASIC_START, BASIC_DAT_NAME)
d.comment(BASIC_START, 'ROL-encoded tokenised BASIC (the keypad-definition '
                       'editor); relocates to PAGE=&0C00 and is decrypted in '
                       'place. Source: basic/voltmace-delta-14b-driver-keypad.bas.')

# ---------------------------------------------------------------------------
# MOS entry points, hardware registers, and OS locations
# ---------------------------------------------------------------------------
d.label(0xFFF1, 'osword')
d.label(0xFFF4, 'osbyte')
d.label(0xFFF7, 'oscli')
d.label(0xFE60, 'user_via_orb')    # User 6522 VIA port B (I/O register B)
d.label(0xFE62, 'user_via_ddrb')   # User 6522 VIA data-direction register B
d.label(0x0220, 'evntv')           # EVNTV: the event vector
d.label(0x0221, 'evntv_hi')
d.label(0xE8AA, 'os_signature')    # OS ROM byte read to distinguish OS versions

# Zero-page scratch used by the relocator/decoder in the tail.
d.label(0x0070, 'copy_dst')        # &70/&71: block-copy destination pointer
d.label(0x0071, 'copy_dst_hi')
d.label(0x0072, 'copy_src')        # &72/&73: block-copy source pointer
d.label(0x0073, 'copy_src_hi')
d.label(0x0074, 'copy_rem')        # &74: remainder byte count
d.label(0x0075, 'copy_pages')      # &75: whole-page count to copy
d.label(0x0080, 'decode_ptr')      # &80/&81: ROL-decode cursor
d.label(0x0081, 'decode_ptr_hi')
d.label(0x023C, 'autorun_index')   # running index into the auto-run buffer

# ---------------------------------------------------------------------------
# The driver, at its &0A00 runtime address
# ---------------------------------------------------------------------------
d.subroutine(
    DRIVER_RUNTIME, 'install_driver', move=driver,
    title='Install the keypad driver',
    description="""Enable the 50 Hz vertical-sync event and route it to the
matrix scanner. Sets User VIA port B to strobe the keypad (DDRB = &F0: top
nibble out, bottom nibble in) and hooks EVNTV to point at the event handler,
saving the previous vector at saved_evntv. Called from the BASIC front-end
via CALL &A00.""",
)
d.comment(0x0A06, 'Ask the MOS to fire an event on every 50 Hz vertical sync '
                  '(OSBYTE 14, event 4)', move=driver)
d.comment(0x0A0D, 'Drive the column strobes and 74LS157 handset-select as outputs '
                  'and sense the four row lines as inputs', move=driver)
d.comment(0x0A13, 'Remember whoever currently owns the event vector, to chain to',
          move=driver)
d.comment(0x0A1F, 'Take over EVNTV so each vsync enters the scanner', move=driver)

d.subroutine(
    0x0A31, 'vsync_event_handler', move=driver,
    title='Vertical-sync event handler: scan the keypad',
    description="""Entered from the MOS every 50 Hz vsync event. Strobes the
3x4 matrix through User VIA port B (bit 7 selects handset 0/1 via the 74LS157),
debounces via debounce_counter, and on a newly-pressed key sounds a short beep
(OSWORD 7) and inserts the mapped character into the keyboard buffer
(OSBYTE &99). Chains to the previous event vector on exit.""",
)
d.comment(0x0A37, 'Probe for activity: strobe all columns low and read the rows back',
          move=driver)
d.comment(0x0AA2, 'Acknowledge the press with a short key-click (OSWORD 7)', move=driver)
d.comment(0x0AB1, 'Look up the character for this matrix cell (col*4 + row)', move=driver)
d.comment(0x0AB8, 'Deliver the keystroke into the keyboard buffer as if typed '
                  '(OSBYTE &99)', move=driver)
d.comment(0x0ACD, 'Hand the event on to the handler we displaced', move=driver)

# Driver data tables (dasmos already classifies most of these as data).
d.label(0x0AD0, 'debounce_counter', move=driver)
d.label(0x0AD1, 'current_row', move=driver)
d.label(0x0AD2, 'current_col', move=driver)
d.label(0x0AD3, 'row_masks', move=driver)
d.comment(0x0AD3, 'input-bit mask for each of the 4 matrix rows', move=driver)
d.label(0x0AD7, 'col_strobes', move=driver)
d.comment(0x0AD7, 'column strobes: the 3 columns for handset 0 (&60,&50,&30) '
                  'then handset 1 (bit 7 set selects it via the 74LS157)',
          move=driver)
d.label(0x0ADD, 'key_codes', move=driver)
d.comment(0x0ADD, 'default character for each of the 24 cells (col*4+row): '
                  'handset 0 = digits/DELETE/RETURN, handset 1 = letters A-L',
          move=driver)
d.label(0x0AF6, 'sound_block', move=driver)
d.comment(0x0AF6, 'OSWORD 7 parameter block: channel, amplitude, pitch, duration',
          move=driver)
d.label(0x0AFE, 'saved_evntv', move=driver)
d.comment(0x0AFE, 'previous EVNTV, restored by the JMP (saved_evntv)', move=driver)

# ---------------------------------------------------------------------------
# The *RUN entry and relocator/decoder, in place in the file (&3900 page)
# ---------------------------------------------------------------------------
d.subroutine(
    EXEC_ADDR, 'main',
    title='*RUN entry: relocate, decode, and auto-run',
    description="""The DFS execution address. Relocates the whole image down to
&0A00 (installing the driver code and moving the encrypted BASIC to PAGE
&0C00), decrypts the BASIC in place, then queues 'PAGE=&C00 / OLD / RUN' so the
now-plain BASIC front-end starts.""",
)
d.subroutine(
    0x391D, 'decode_basic',
    title='Decrypt the relocated BASIC',
    description="""Rotate every byte of the relocated BASIC left one bit (the
inverse of the ROL-1 storage protection), across pages &0C00-&2AFF, in place.""",
)
d.subroutine(
    0x394E, 'os_dependent_setup',
    title='OS-version-dependent setup',
    description='Reads os_signature to choose between the two setup paths below.',
)
d.label(0x0C03, 'basic_line10_len')
d.subroutine(
    0x3961, 'patch_basic_header',
    title="Repair the BASIC program's first line",
    description="""Write &16 (22) into basic_line10_len, the length byte of the
line-10 REM at PAGE=&0C00. That byte is stored as 0 (part of the protection),
so without this repair the relocated program cannot be LISTed or RUN.""",
)
d.subroutine(
    0x3967, 'queue_autorun',
    title='Queue the auto-run command string',
    description="""Copy autorun_commands ('PA.=&C00' / 'OLD' / 'RUN') into the
input buffer so the MOS 'types' them and the decoded BASIC runs.""",
)
d.subroutine(
    0x3986, 'setup_keys',
    title='Alternate key setup (OSBYTE path)',
)
d.subroutine(
    0x39AA, 'relocate_image',
    title='Relocate the program image to &0A00',
    description="""OSCLI the command at oscli_command, then block-copy the image
from &1900 down to &0A00 (copy_pages pages via copy_src -> copy_dst), skipping
destination page &0B so the soft-key buffer survives.""",
)
d.comment(0x39D2, 'Leave page &0B untouched so the user soft-key definitions survive '
                  'the move', align=dasmos.Align.INLINE)

# Padding, decoy, and trailing data around the loader.
d.comment(0x3869, 'Zero padding between the encrypted BASIC and the *RUN loader')
d.byte(0x3900, 6)
d.label(0x3900, 'loader_preamble')
d.comment(0x3900, 'Filler ahead of the loader entry; reads as a stub BASIC line '
                  '(&0D, line 13, then RTS bytes)')
d.byte(0x3A06, 0x3A80 - 0x3A06)
d.label(0x3A06, 'trailing_data')
d.comment(0x3A06, 'Trailing bytes the loader never references; the relocated '
                  'copy is wiped by the BASIC memory-clear (FOR A%=&C00 TO &3A80) '
                  'at startup')

# Tail data.
d.string(0x39F1, 3)                  # the OSCLI command string
d.label(0x39F1, 'oscli_command')
d.comment(0x39F1, 'startup command "*T." (*TAPE): select the cassette filing '
                  'system before relocating', align=dasmos.Align.INLINE)
d.label(0x39F4, 'autorun_commands')
d.comment(0x39F4, "auto-run command lines: 'PA.=&C00' / 'OLD' / 'RUN', "
                  "CR-separated, &00-terminated", align=dasmos.Align.INLINE)

# Entry points.
d.entry(EXEC_ADDR)                     # *RUN entry: relocator-installer
d.entry(DRIVER_RUNTIME, move=driver)   # install routine (BASIC calls CALL &A00)
d.entry(0x0A31, move=driver)           # vsync event handler (reached via EVNTV)

ir = d.disassemble()
output = str(
    ir.render(
        'beebasm',
        boundary_label_prefix='pydis_',
        byte_column=True,
        byte_column_format='py8dis',
        default_byte_cols=12,
        default_word_cols=6,
    )
)
_output_dirpath.mkdir(parents=True, exist_ok=True)
output_filepath = _output_dirpath / 'voltmace-delta-14b-driver-keypad.asm'
output_filepath.write_text(output, encoding='utf-8')
print(f'Wrote {output_filepath}', file=sys.stderr)
json_filepath = _output_dirpath / 'voltmace-delta-14b-driver-keypad.json'
json_filepath.write_text(str(ir.render('json')), encoding='utf-8')
print(f'Wrote {json_filepath}', file=sys.stderr)

# Regenerate the incbin payload from the editable BASIC source, and prove it
# reproduces exactly the bytes dasmos accounted for (its canonical reference).
dat_bytes = build_basic_dat(_basic_filepath)
with tempfile.TemporaryDirectory() as tmp:
    ir.write_included_binaries(tmp)
    canonical = (Path(tmp) / BASIC_DAT_NAME).read_bytes()
if dat_bytes != canonical:
    raise SystemExit(
        f'{_basic_filepath.name} does not reproduce the original encoded BASIC: '
        f'{len(dat_bytes)} bytes built vs {len(canonical)} canonical'
    )
dat_filepath = _output_dirpath / BASIC_DAT_NAME
dat_filepath.write_bytes(dat_bytes)
print(f'Wrote {dat_filepath}', file=sys.stderr)
