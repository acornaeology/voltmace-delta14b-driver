"""Disassembly driver for the Voltmace Delta 14B/1 KEYPAD driver.

Configures dasmos to produce an annotated disassembly of the KEYPAD *RUN
program. Run via:
  uv run fantasm disassemble keypad
or directly:
  uv run python versions/voltmace-delta-14b-driver-keypad/disassemble/disasm_voltmace_delta_14b_driver_keypad.py

The file loads at &1900 and executes at &3906. Its layout:

  &1900-&19FF  6502 keypad resident driver (256 bytes), STORED here but written to RUN
               relocated at &0A00 (offset -&F00): install routine + vsync-event
               matrix scanner (User VIA port B &FE60, DDRB &FE62, 74LS157 bit).
  &1A00-&1AFF  image of page &0B, which the relocator deliberately SKIPS so the
               MOS soft-key buffer survives; here it is &10-filler.
  &1B00-&3868  the keypad-definition editor, a tokenised BBC BASIC program,
               stored ROL-encoded (every byte rotated left one bit) as
               rudimentary protection. It relocates to PAGE=&0C00; the first
               line's length byte is stored as 0 and patched to &16 at run time.
  &3869-&3A7F  *RUN entry / relocator-installer (exec &3906): copies the image
               down (resident driver to &0A00, BASIC to &0C00), decrypts the BASIC,
               and queues PAGE=&C00 / OLD / RUN to start it.

The ROL-encoded BASIC region is carried as detokenised source (basic/*.bas)
and re-encoded to an incbin payload at build time (build_basic_dat), so the
whole file still reassembles byte-identically.
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
DRIVER_RUNTIME = 0x0A00     # the resident driver is relocated here before it runs
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

# The resident driver is stored at &1900 but copied down to &0A00 before execution;
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

# Inline-comment helpers: cm() annotates the relocated resident driver (&0A00),
# ct() annotates the in-place loader tail (&3900).
INLINE = dasmos.Align.INLINE


def cm(addr, text):
    d.comment(addr, text, align=INLINE, move=driver)


def ct(addr, text):
    d.comment(addr, text, align=INLINE)


# ---------------------------------------------------------------------------
# MOS entry points, hardware registers, and OS locations
# ---------------------------------------------------------------------------
# MOS entry-point call vectors (group only -- these are JSR targets, not
# read/write locations).
d.label(0xFFF1, 'osword', group='os_entry_points',
        description='OSWORD: the resident driver calls OSWORD 7 to sound the key-click.')
d.label(0xFFF4, 'osbyte', group='os_entry_points',
        description='OSBYTE: used with A=&99 to insert a key into the buffer, '
                    'A=&0E to enable the vsync event, and to read/set vectors.')
d.label(0xFFF7, 'oscli', group='os_entry_points',
        description='OSCLI: issues the *KEY / *FX-style commands the loader '
                    'queues.')

# Memory-mapped I/O -- the User 6522 VIA that strobes the keypad matrix.
d.label(0xFE60, 'user_via_orb', group='hardware', access='rw',
        description='User VIA port B: writes column strobes and the 74LS157 '
                    'handset-select bit (bit 7); reads the four matrix rows.')
d.label(0xFE62, 'user_via_ddrb', group='hardware', access='w',
        description='User VIA data-direction register B: set to &F0 so the '
                    'four strobe/select lines are outputs, the four rows inputs.')

# OS vectors and workspace.
d.label(0x0220, 'evntv', group='os_vectors', access='rw', length=2,
        description='EVNTV, the event vector: the resident driver saves the old value '
                    'and points it at its vsync-event handler.')
d.label(0x0221, 'evntv_hi')
d.label(0x023C, 'autorun_index', group='os_workspace', access='rw',
        description='Running fill index into the keyboard buffer as the loader '
                    'queues its PAGE / OLD / RUN commands.')
d.label(0x0300, 'kbd_buffer', group='os_workspace', access='w',
        description='Base of the &0300 page holding the MOS keyboard buffer '
                    '(&03E0-&03FF), written directly on the fast hand-off path.')

# OS ROM and BASIC workspace.
d.label(0xE8AA, 'os_signature', group='os_rom', access='r',
        description='OS ROM byte read (for \'O\') to distinguish OS versions '
                    'and choose the command hand-off path.')
d.label(0x0C03, 'basic_line10_len', group='basic_workspace', access='w',
        description='Length byte of the relocated BASIC\'s line 10, patched '
                    'from 0 back to &16 so the protected program lists and runs.')

# Zero-page scratch used by the relocator/decoder in the tail.
d.label(0x0070, 'copy_dst', group='zero_page', access='rw', length=2,
        description='Block-copy destination pointer used by the relocator.')
d.label(0x0071, 'copy_dst_hi')
d.label(0x0072, 'copy_src', group='zero_page', access='rw', length=2,
        description='Block-copy source pointer used by the relocator.')
d.label(0x0073, 'copy_src_hi')
d.label(0x0074, 'copy_rem', group='zero_page', access='rw',
        description='Leftover (part-page) byte count for the relocator.')
d.label(0x0075, 'copy_pages', group='zero_page', access='rw',
        description='Whole-page count for the relocator.')
d.label(0x0080, 'decode_ptr', group='zero_page', access='rw', length=2,
        description='ROL-decode cursor sweeping the encrypted BASIC in place.')
d.label(0x0081, 'decode_ptr_hi')

# ---------------------------------------------------------------------------
# install_driver -- the resident driver, at its &0A00 runtime address
# ---------------------------------------------------------------------------
d.subroutine(
    DRIVER_RUNTIME, 'install_driver', move=driver,
    title='Install the resident keypad driver',
    description="""Enable the 50 Hz vertical-sync event and route it to the
matrix scanner. Sets User VIA port B to strobe the keypad (DDRB = &F0: top
nibble out, bottom nibble in) and hooks EVNTV to point at the event handler,
saving the previous vector at saved_evntv. Called from the BASIC front-end
via CALL &A00.""",
    on_exit={'A': 'corrupted', 'X': 'corrupted', 'Y': 'corrupted'},
)
cm(0x0A00, 'Preserve the caller flags')
cm(0x0A01, 'Preserve A')
cm(0x0A02, 'Preserve Y...')
cm(0x0A03, '...on the stack')
cm(0x0A04, 'Preserve X...')
cm(0x0A05, '...on the stack')
cm(0x0A06, 'OSBYTE 14: enable an event...')
cm(0x0A08, '...event 4, the 50 Hz vertical sync')
cm(0x0A0A, 'call OSBYTE')
cm(0x0A0D, 'DDRB = &F0: bits 4-7 drive the column strobes + 74LS157 select...')
cm(0x0A0F, '...bits 0-3 sense the four row lines')
cm(0x0A12, 'Block IRQs while re-pointing the vector')
cm(0x0A13, 'Save the current event vector low byte...')
cm(0x0A16, '...at saved_evntv, to chain to on exit')
cm(0x0A19, 'Save its high byte...')
cm(0x0A1C, '...too')
cm(0x0A1F, 'Point EVNTV at vsync_event_handler: low byte &31...')
cm(0x0A21, '...store it')
cm(0x0A24, '...high byte &0A...')
cm(0x0A26, '...store it')
cm(0x0A29, 'Re-enable IRQs')
cm(0x0A2A, 'Restore X...')
cm(0x0A2B, '...from the stack')
cm(0x0A2C, 'Restore Y...')
cm(0x0A2D, '...from the stack')
cm(0x0A2E, 'Restore A')
cm(0x0A2F, 'Restore the flags')
cm(0x0A30, 'Return to the BASIC caller')

# ---------------------------------------------------------------------------
# vsync_event_handler -- runs off EVNTV every frame
# ---------------------------------------------------------------------------
d.subroutine(
    0x0A31, 'vsync_event_handler', move=driver,
    title='Vertical-sync event handler: scan the keypad',
    description="""Entered from the MOS every 50 Hz vsync event. Strobes the
3x4 matrix through User VIA port B (bit 7 selects handset 0/1 via the 74LS157),
debounces and auto-repeats via debounce_counter, and on a pressed key sounds a
short key-click (OSWORD 7) and inserts the mapped character into the keyboard
buffer (OSBYTE &99). Chains to the previous event vector on exit.""",
)
cm(0x0A31, 'Preserve the interrupted flags')
cm(0x0A32, 'Preserve A')
cm(0x0A33, 'Preserve Y...')
cm(0x0A34, '...on the stack')
cm(0x0A35, 'Preserve X...')
cm(0x0A36, '...on the stack')
cm(0x0A37, 'Quick probe: drive every column low on handset 0...')
cm(0x0A39, '...write it')
cm(0x0A3C, '...and read the rows back')
cm(0x0A3F, 'All four rows high (&0F) => nothing down on handset 0')
cm(0x0A41, 'Something is down -> go locate it')
cm(0x0A43, 'Probe handset 1 (bit 7 selects it)...')
cm(0x0A45, '...write it')
cm(0x0A48, '...read the rows')
cm(0x0A4B, '&8F = handset-1 select set, all rows high = no key')
cm(0x0A4D, 'Nothing on either handset -> idle')
d.label(0x0A4F, 'check_held_key', move=driver)
cm(0x0A4F, 'Is a key already being held? (current_row 5 = none)')
cm(0x0A52, 'against the "none" marker (5)')
cm(0x0A54, 'No held key -> full matrix scan')
cm(0x0A56, 'Re-test the held key: fetch its column strobe...')
cm(0x0A59, 'from the strobe table')
cm(0x0A5C, '...drive it')
cm(0x0A5F, '...read the rows...')
cm(0x0A62, '...and mask its row bit')
cm(0x0A65, 'Released (bit high now) -> rescan for a new key')
cm(0x0A67, 'Still held: count down to the next auto-repeat '
           '(patched to LDA by the editor to disable auto-repeat)')
cm(0x0A6A, 'Not time to repeat yet -> exit')
cm(0x0A6C, 'Reload the repeat interval (4 frames)...')
cm(0x0A6E, 'store it')
cm(0x0A71, 'clear carry for the branch')
cm(0x0A72, 'Re-emit the held key')
d.label(0x0A74, 'scan_matrix', move=driver)
cm(0x0A74, 'Full scan: start at column 0')
d.label(0x0A76, 'scan_next_column', move=driver)
cm(0x0A76, 'Start at row 0 of this column')
d.label(0x0A78, 'scan_next_row', move=driver)
cm(0x0A78, 'Only (re)strobe the column when starting at row 0...')
cm(0x0A7A, '...otherwise the strobe already stands')
cm(0x0A7C, 'Drive column X (its handset bit included)...')
cm(0x0A7F, 'write it')
d.label(0x0A82, 'test_row', move=driver)
cm(0x0A82, 'Read the rows...')
cm(0x0A85, '...test this row bit')
cm(0x0A88, 'Bit low -> key at (column X, row Y) is pressed')
cm(0x0A8A, 'Next row...')
cm(0x0A8B, 'all four rows done?')
cm(0x0A8D, '...until all 4 rows tested')
cm(0x0A8F, 'Next column...')
cm(0x0A90, '...6 columns = 3 per handset')
cm(0x0A92, 'loop back for the next column')
cm(0x0A94, 'clear carry for the branch')
cm(0x0A95, 'Nothing pressed -> exit')
d.label(0x0A97, 'key_pressed', move=driver)
cm(0x0A97, 'New press: set the initial auto-repeat delay (24 frames)...')
cm(0x0A99, 'store it')
cm(0x0A9C, 'Remember which key is now held: column...')
cm(0x0A9F, '...and row')
d.label(0x0AA2, 'emit_key', move=driver)
cm(0x0AA2, 'OSWORD 7: play the key-click sound...')
cm(0x0AA4, '...parameter block at sound_block (&0AF6)...')
cm(0x0AA6, 'block high byte &0A')
cm(0x0AA8, 'call OSWORD')
cm(0x0AAB, 'Key-table index = col*4 + row:')
cm(0x0AAC, 'take the column...')
cm(0x0AAF, '...times 4...')
cm(0x0AB0, 'shifted twice = x4')
cm(0x0AB1, '...plus the row')
cm(0x0AB4, '...as an index')
cm(0x0AB5, 'Fetch that cell character into Y')
cm(0x0AB8, 'OSBYTE &99: insert Y into buffer 0 (keyboard)...')
cm(0x0ABA, 'X=0 selects the keyboard buffer')
cm(0x0ABC, '...as if the key were typed')
cm(0x0ABF, 'clear carry for the branch')
cm(0x0AC0, 'Done')
d.label(0x0AC2, 'no_key_down', move=driver)
cm(0x0AC2, "Record 'no key held' (row 5)...")
cm(0x0AC4, 'store it')
d.label(0x0AC7, 'handler_exit', move=driver)
cm(0x0AC7, 'Restore X...')
cm(0x0AC8, 'into X')
cm(0x0AC9, 'Restore Y...')
cm(0x0ACA, 'into Y')
cm(0x0ACB, 'Restore A')
cm(0x0ACC, 'Restore the flags')
cm(0x0ACD, 'Chain to the event handler we displaced')

# ---------------------------------------------------------------------------
# Driver data tables (in the relocated &0A00 block)
# ---------------------------------------------------------------------------
d.label(0x0AD0, 'debounce_counter', move=driver)
cm(0x0AD0, 'Frames until the next auto-repeat (0 = repeat this frame)')
d.label(0x0AD1, 'current_row', move=driver)
cm(0x0AD1, 'Row of the held key (5 = none)')
d.label(0x0AD2, 'current_col', move=driver)
cm(0x0AD2, 'Column of the held key')
d.label(0x0AD3, 'row_masks', move=driver)
cm(0x0AD3, 'Port-B input bit for matrix rows 0-3')
d.byte(0x0AD7, 6, move=driver, override=True)
d.label(0x0AD7, 'col_strobes', move=driver)
cm(0x0AD7, 'Port-B strobe per column: cols 0-2 = handset 0 (&60,&50,&30), '
           'cols 3-5 = handset 1 (bit 7 set for the 74LS157)')
d.label(0x0ADD, 'key_codes', move=driver)
cm(0x0ADD, 'Default character per cell, indexed col*4+row: cells 0-11 handset 0 '
           '(digits/DELETE/RETURN), cells 12-23 handset 1 (letters). The editor '
           'overwrites this table.')
d.byte(0x0AF5, 1, move=driver)
cm(0x0AF5, 'Spare byte')
d.word(0x0AF6, 8, move=driver, override=True)
d.label(0x0AF6, 'sound_block', move=driver)
# The pitch value &0080 must stay a literal, not resolve to the decode_ptr ZP label.
d.expr(0x0AFA, '&0080', move=driver)
cm(0x0AF6, 'OSWORD 7 block: channel &0000, amplitude &FFF8 (patched by the '
           'editor beep option), pitch &0080, duration &0001')
d.word(0x0AFE, 2, move=driver, override=True)
d.label(0x0AFE, 'saved_evntv', move=driver)
d.label(0x0AFF, 'saved_evntv_hi', move=driver)
cm(0x0AFE, 'Previous EVNTV, chained to on exit')

# ---------------------------------------------------------------------------
# main -- the *RUN entry and loader tail, in place in the file (&3900 page)
# ---------------------------------------------------------------------------
d.subroutine(
    EXEC_ADDR, 'main',
    title='*RUN entry: relocate, decode, and auto-run',
    description="""The DFS execution address. Relocates the whole image down to
&0A00 (installing the resident driver code and moving the encrypted BASIC to PAGE
&0C00), decrypts the BASIC in place, then queues 'PAGE=&C00 / OLD / RUN' so the
now-plain BASIC front-end starts.""",
)
ct(0x3906, 'Preserve A')
ct(0x3907, 'Preserve X...')
ct(0x3908, '...on the stack')
ct(0x3909, 'Preserve Y...')
ct(0x390A, '...on the stack')
ct(0x390B, 'Copy the image down (resident driver to &0A00, BASIC to PAGE &0C00)')
ct(0x390E, 'Decrypt the relocated BASIC in place')
ct(0x3911, "Repair the BASIC's first-line length byte")
ct(0x3914, 'Queue the auto-run commands (OS-dependent)')
ct(0x3917, 'Restore Y...')
ct(0x3918, 'into Y')
ct(0x3919, 'Restore X...')
ct(0x391A, 'into X')
ct(0x391B, 'Restore A')
ct(0x391C, 'Return to the MOS; the queued commands then run the BASIC')

d.subroutine(
    0x391D, 'decode_basic',
    title='Decrypt the relocated BASIC',
    description="""Rotate every byte of the relocated BASIC left one bit (the
inverse of the ROL-1 storage protection), across pages &0C00-&2AFF, in place.""",
)
ct(0x391D, 'Save the caller decode_ptr low byte...')
ct(0x391F, 'save it')
ct(0x3922, '...and high byte...')
ct(0x3924, '...at decode_ptr_save')
ct(0x3927, 'Point decode_ptr at PAGE &0C00: low byte 0...')
ct(0x3929, 'set it')
ct(0x392B, '...high byte &0C...')
ct(0x392D, 'byte index 0')
d.label(0x392F, 'decode_next_page', move=None)
ct(0x392F, 'Set the page being decrypted')
d.label(0x3931, 'decode_next_byte', move=None)
ct(0x3931, 'Read an encrypted byte...')
ct(0x3933, 'clear carry for the rotate')
ct(0x3934, '...rotate it left one bit (undo the ROL-1 protection)...')
ct(0x3935, '...carrying bit 7 into bit 0...')
ct(0x3937, '...and store it back')
ct(0x3939, 'Next byte...')
ct(0x393A, '...to the end of the page')
ct(0x393C, 'Next page...')
ct(0x393E, 'increment the page')
ct(0x393F, '...until page &2B (end of the BASIC region)')
ct(0x3941, 'keep decrypting pages')
ct(0x3943, 'Restore the caller decode_ptr...')
ct(0x3946, 'low byte')
ct(0x3948, 'high byte')
ct(0x394B, 'store it')
ct(0x394D, 'Done')

d.subroutine(
    0x394E, 'os_dependent_setup',
    title='OS-version-dependent setup',
    description='Reads os_signature to pick how the auto-run commands are queued.',
)
ct(0x394E, 'clear Y')
ct(0x3950, 'Read the OS ROM signature byte...')
ct(0x3953, "...'O' identifies the supported OS")
ct(0x3955, 'Supported OS -> poke the buffer directly')
ct(0x3957, 'Other OS -> insert via OSBYTE')
ct(0x395A, 'Done')
d.label(0x395B, 'use_direct_poke', move=None)
ct(0x395B, 'Queue by poking the keyboard buffer')
ct(0x395E, 'Done')
d.word(0x395F, 2, override=True)
d.label(0x395F, 'decode_ptr_save')
d.label(0x3960, 'decode_ptr_save_hi')
ct(0x395F, "Scratch: caller's decode_ptr saved across decode_basic (&EAEA at rest)")

d.subroutine(
    0x3961, 'patch_basic_header',
    title="Repair the BASIC program's first line",
    description="""Write &16 (22) into basic_line10_len, the length byte of the
line-10 REM at PAGE=&0C00. That byte is stored as 0 (part of the protection),
so without this repair the relocated program cannot be LISTed or RUN.""",
)
ct(0x3961, 'The first BASIC line is 22 bytes long...')
ct(0x3963, '...restore its length byte (stored as 0 by the protection)')
ct(0x3966, 'Done')

d.subroutine(
    0x3967, 'queue_autorun',
    title='Queue the auto-run commands (direct poke)',
    description="""Copy autorun_commands into the MOS keyboard buffer so the OS
reads them as typed and runs the decoded BASIC. autorun_index wraps into the
32-byte buffer at &03E0-&03FF.""",
)
ct(0x3967, 'Start at the first command byte')
d.label(0x3969, 'queue_next_byte', move=None)
ct(0x3969, 'Current buffer fill position...')
ct(0x396C, 'read a command byte...')
ct(0x396F, '...&00 terminates')
ct(0x3971, 'Poke it into the keyboard buffer')
ct(0x3974, 'Advance the fill position...')
ct(0x3977, 'reload it')
ct(0x397A, 'unless it wrapped to 0')
ct(0x397C, '...wrapping back to &E0 (buffer at &03E0)...')
ct(0x397E, 'store it')
d.label(0x3981, 'queue_advance', move=None)
ct(0x3981, 'Next command byte')
ct(0x3982, 'loop')
d.label(0x3985, 'queue_done', move=None)
ct(0x3985, 'Done')

d.subroutine(
    0x3986, 'setup_keys',
    title='Queue the auto-run commands (OSBYTE path)',
    description="""The non-&4F-OS variant of queue_autorun: set the BREAK/ESCAPE
behaviour, then insert each autorun_commands byte with OSBYTE &8A.""",
)
ct(0x3986, 'OSBYTE 200: set the BREAK/ESCAPE behaviour...')
ct(0x3988, 'value 3')
ct(0x398A, 'call OSBYTE')
ct(0x398D, 'Start at the first command byte')
d.label(0x398F, 'insert_next_key', move=None)
ct(0x398F, 'Read a command byte...')
ct(0x3992, '...&00 terminates')
ct(0x3994, 'The character to insert')
ct(0x3995, 'Save the loop index...')
ct(0x3996, 'save it')
ct(0x3999, 'OSBYTE &8A: insert Y into buffer 0 (keyboard)...')
ct(0x399B, 'A = &8A')
ct(0x399D, 'call OSBYTE')
ct(0x39A0, 'Restore the loop index...')
ct(0x39A3, 'into X')
ct(0x39A4, 'Next command byte')
ct(0x39A5, 'loop')
d.label(0x39A8, 'setup_keys_done', move=None)
ct(0x39A8, 'Done')
d.byte(0x39A9, 1)
d.label(0x39A9, 'setup_key_index')
ct(0x39A9, 'Scratch: saved loop index (&EA at rest)')

d.subroutine(
    0x39AA, 'relocate_image',
    title='Relocate the program image to &0A00',
    description="""OSCLI the startup command, then block-copy the image from
&1900 down to &0A00 (copy_pages pages via copy_src -> copy_dst), skipping
destination page &0B so the soft-key buffer survives.""",
)
ct(0x39AA, 'OSCLI the startup command at oscli_command (&39F1): low byte...')
ct(0x39AC, '...high byte...')
ct(0x39AE, '...call OSCLI')
ct(0x39B1, '(carry set; not used by the copy below)')
ct(0x39B2, 'Leftover byte count = 0 (whole pages only)...')
ct(0x39B4, 'store it')
ct(0x39B6, 'Copy &20 = 32 pages...')
ct(0x39B8, 'store it')
ct(0x39BA, 'Destination = &0A00: low byte...')
ct(0x39BC, 'store it')
ct(0x39BE, '...high byte...')
ct(0x39C0, 'store it')
ct(0x39C2, 'Source = &1900 (the loaded image): low byte...')
ct(0x39C4, 'store it')
ct(0x39C6, '...high byte...')
ct(0x39C8, 'store it')
ct(0x39CA, 'Byte index within the page')
ct(0x39CC, 'Page count...')
ct(0x39CE, '...none -> just the remainder')
d.label(0x39D0, 'copy_page', move=None)
ct(0x39D0, 'Which destination page are we about to write?')
d.comment(0x39D2, 'Leave page &0B untouched so the user soft-key definitions '
                  'survive the move', align=INLINE)
ct(0x39D4, '...skip the store for that page')
ct(0x39D6, 'Copy one byte...')
ct(0x39D8, 'to the destination')
d.label(0x39DA, 'copy_next_byte', move=None)
ct(0x39DA, 'Next byte...')
ct(0x39DB, '...to the end of the page')
ct(0x39DD, 'Next source page...')
ct(0x39DF, '...and destination page')
ct(0x39E1, 'one fewer page')
ct(0x39E2, '...until all pages copied')
d.label(0x39E4, 'copy_remainder', move=None)
ct(0x39E4, 'Any leftover bytes? (none here)')
ct(0x39E6, 'none -> done')
d.label(0x39E8, 'copy_remainder_byte', move=None)
ct(0x39E8, 'Copy one byte...')
ct(0x39EA, 'to the destination')
ct(0x39EC, 'next byte')
ct(0x39ED, 'one fewer')
ct(0x39EE, 'loop')
d.label(0x39F0, 'copy_done', move=None)
ct(0x39F0, 'Done')

# ---------------------------------------------------------------------------
# Data in the loader tail
# ---------------------------------------------------------------------------
d.string(0x39F1, 2)                  # "T."
d.byte(0x39F3, 1)                    # &0D terminator
d.label(0x39F1, 'oscli_command')
ct(0x39F1, 'Startup *-command "T." (*TAPE): select the cassette filing system, '
           'CR-terminated')
# The auto-run command lines, fed to the keyboard buffer one byte at a time.
d.byte(0x39F4, 2)                    # &15, &0D
d.string(0x39F6, 8)                  # "PA.=&C00"
d.byte(0x39FE, 1)
d.string(0x39FF, 3)                  # "OLD"
d.byte(0x3A02, 1)
d.string(0x3A03, 3)                  # "RUN"
d.byte(0x3A06, 2)                    # &0D, &00 terminator
d.label(0x39F4, 'autorun_commands')
ct(0x39F4, 'CTRL-U + CR: clear the input line')
ct(0x39F6, 'set PAGE to &0C00, where the BASIC now lives')
ct(0x39FE, 'submit')
ct(0x39FF, 'reinstate the decoded program (OLD)')
ct(0x3A02, 'submit')
ct(0x3A03, 'run it (RUN)')
ct(0x3A06, 'submit; the &00 then stops the queue copy')

# Padding and decoy around the loader.
d.comment(0x3869, 'Zero padding between the encrypted BASIC and the *RUN loader')
d.byte(0x3900, 6)
d.label(0x3900, 'loader_preamble')
d.comment(0x3900, 'Filler ahead of the loader entry; reads as a stub BASIC line '
                  '(&0D, line 13, then RTS bytes)')
d.byte(0x3A08, 0x3A80 - 0x3A08)
d.label(0x3A08, 'trailing_data')
d.comment(0x3A08, 'Uninitialised tail of the saved image. The file is a memory '
                  'dump &1900-&3A80 (the BASIC clears exactly TO &3A80); the '
                  "loader's code and tables end ~120 bytes short, so this holds "
                  'whatever occupied the memory at save time. It is referenced by '
                  'nothing and decodes as neither 6502, tokenised BASIC (raw or '
                  'bit-rotated), nor text; its byte statistics are those of noise. '
                  'Inert: the BASIC memory-clear overwrites it at startup.')

# Entry points.
d.entry(EXEC_ADDR)                     # *RUN entry: relocator-installer
d.entry(DRIVER_RUNTIME, move=driver)   # install routine (BASIC calls CALL &A00)
d.entry(0x0A31, move=driver)           # vsync event handler (reached via EVNTV)

ir = d.disassemble()
output = str(
    ir.render(
        'beebasm',
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
