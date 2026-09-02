"""Disassembly driver for the Voltmace Delta 14B/1 JOYSTIK driver.

Run via:
  uv run fantasm disassemble joystik

The file loads at &1900 and executes at &1909. Its layout:

  &1900-&1908  decoy: a stub BASIC line so a naive *LOAD/LIST sees junk.
  &1909-&19FF  head loader (plain 6502): ROL-decrypts &1A00-&4AFF in place,
               repairs the BASIC's first line, and queues PAGE=&1C00/OLD/RUN.
  &1A00-&1AFF  joystick driver, variant A (6502, ROL-encoded here; runs at
               &0A00 -- hooks BYTEV and intercepts OSBYTE &81).
  &1B00-&1BFF  joystick driver, variant B (same, an alternate build).
  &1C00-&4AFF  the configuration/demo program, tokenised BBC BASIC (PAGE),
               ROL-encoded; the loader decrypts it up to page &4B.
  &4B00-&4C92  the rest of that BASIC, stored RAW (beyond the decode range).
  &4C93-&4CFF  tail.

The ROL-encoded region (&1A00-&4C92, drivers + BASIC) is carried as editable
source -- the drivers as annotated disassembly, the BASIC as basic/*.bas -- and
re-encoded to an incbin payload at build time (build_encoded_dat), so the whole
file still reassembles byte-identically.
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
    or str(_version_dirpath / 'binary' / 'JOYSTIK')
)
_output_dirpath = Path(
    os.environ.get('FANTASM_OUTPUT_DIR', str(_version_dirpath / 'output'))
)
_basic_filepath = _version_dirpath / 'basic' / 'voltmace-delta-14b-driver-joystik.bas'
ENCODED_DAT_NAME = 'voltmace-delta-14b-driver-joystik-encoded.dat'

LOAD_ADDR = 0x1900          # DFS load address
EXEC_ADDR = 0x1909          # DFS execution address (*RUN entry)
DRIVER_A_ADDR = 0x1A00      # driver variant A, stored here
DRIVER_B_ADDR = 0x1B00      # driver variant B, stored here
DRIVER_LEN = 0x0100         # each driver variant is 256 bytes
BASIC_PAGE = 0x1C00         # PAGE of the tokenised BASIC
ENC_END = 0x4B00            # decode stops here (loader: cpx #&4B)
BASIC_END = 0x4C93          # one past the BASIC's &0D &FF terminator
INCBIN_START = DRIVER_A_ADDR
INCBIN_END = BASIC_END
TAIL_START = BASIC_END


def _rol(b):
    return (((b << 1) & 0xFF) | (b >> 7)) & 0xFF


def _ror(b):
    return ((b >> 1) | ((b & 1) << 7)) & 0xFF


def _tokenise_basic(bas_filepath):
    """Greedy-tokenise the BASIC source and reverse the loader's line-10 repair."""
    oaknut = shutil.which('oaknut-basic') or str(Path(sys.executable).parent / 'oaknut-basic')
    with tempfile.TemporaryDirectory() as tmp:
        tok_filepath = Path(tmp) / 'basic.tok'
        subprocess.run(
            [oaknut, 'tokenise', str(bas_filepath), str(tok_filepath), '--crunch', 'greedy'],
            check=True,
        )
        tokens = bytearray(tok_filepath.read_bytes())
    tokens[3] = 0x00  # line-10 length byte is stored as 0 (patched to &17 at run time)
    return bytes(tokens)


DRIVER_RUNTIME = 0x0A00      # both driver variants run relocated here


def _decoded(image, addr):
    lo = addr - LOAD_ADDR
    return bytes(_rol(b) for b in image[lo:lo + DRIVER_LEN])


def _make_driver_disassembler(decoded_bytes):
    tmp = tempfile.NamedTemporaryFile(suffix='.bin', delete=False)
    tmp.write(decoded_bytes)
    tmp.close()
    dd = dasmos.Disassembler.create(
        cpu='6502', auto_label_data_prefix='l', auto_label_code_prefix='c',
        auto_label_subroutine_prefix='sub_c', auto_label_loop_prefix='loop_c',
    )
    dd.load(tmp.name, DRIVER_RUNTIME)
    os.unlink(tmp.name)
    return dd


def _render_driver(dd):
    return str(dd.disassemble().render(
        'beebasm', byte_column=True, byte_column_format='py8dis',
        default_byte_cols=12, default_word_cols=6,
    ))


def _assemble(asm_text):
    beebasm = shutil.which('beebasm')
    if beebasm is None:
        raise SystemExit('beebasm not found on PATH')
    with tempfile.TemporaryDirectory() as tmp:
        asm = Path(tmp) / 'd.asm'
        asm.write_text(asm_text, encoding='utf-8')
        out = Path(tmp) / 'd.bin'
        subprocess.run([beebasm, '-i', str(asm), '-o', str(out)],
                       check=True, cwd=tmp, capture_output=True, text=True)
        return out.read_bytes()


def build_encoded_dat(driver_a_bytes, driver_b_bytes, bas_filepath):
    """Regenerate the incbin payload (&1A00-&4C92) from editable source.

    The loader ROL-decrypts &1A00-&4AFF in place, so the plaintext of that
    region is [driver A][driver B][encoded part of the BASIC]; we ROR-encode it
    (the inverse) and append the BASIC's raw tail (&4B00+, beyond the decode
    range). The driver bytes come from assembling their annotated disassembly.
    """
    basic = _tokenise_basic(bas_filepath)
    split = ENC_END - BASIC_PAGE            # BASIC bytes that fall inside the decode range
    plain_encoded = driver_a_bytes + driver_b_bytes + basic[:split]
    return bytes(_ror(b) for b in plain_encoded) + basic[split:]


def _annotate_driver_common(dd):
    """Labels, install routine, and BYTEV-handler frame shared by both variants."""
    dd.label(0x020A, 'bytev')            # BYTEV: the OSBYTE indirection vector
    dd.label(0x020B, 'bytev_hi')
    dd.label(0xFFF4, 'osbyte')
    dd.entry(0x0A00)                     # install (BASIC: CALL &A00)
    dd.entry(0x0A0D)                     # BYTEV handler (reached via the vector)

    def ci(addr, text):
        dd.comment(addr, text, align=dasmos.Align.INLINE)

    dd.subroutine(
        0x0A00, 'install',
        title='Install the joystick driver',
        description="""Point BYTEV at the OSBYTE intercept at &0A0D. Called from
the BASIC via CALL &A00, after it has saved the previous BYTEV (line 50) and
patched the chain slot (line 1840) and sensitivity thresholds (line 1850).""",
    )
    ci(0x0A00, 'Preserve A')
    ci(0x0A01, 'BYTEV low byte -> &0D...')
    ci(0x0A03, '...')
    ci(0x0A06, '...high byte -> &0A...')
    ci(0x0A08, '...so every OSBYTE now enters the handler at &0A0D')
    ci(0x0A0B, 'Restore A')
    ci(0x0A0C, 'Return to the BASIC caller')
    return ci


def annotate_driver_a(dd):
    """Variant A: joystick only (analogue port via OSBYTE &80 / ADVAL)."""
    ci = _annotate_driver_common(dd)
    dd.subroutine(
        0x0A0D, 'osbyte_intercept',
        title='BYTEV handler: map the joystick to INKEY',
        description="""Runs on every OSBYTE; only OSBYTE &81 (INKEY / read key) is
intercepted. If the key being tested matches an entry in joystick_map, the
matching analogue input is read and, when active, a "key pressed" result is
returned; every other call chains to the previous BYTEV.""",
    )
    ci(0x0A0D, 'Only intercept OSBYTE &81 (INKEY / read key)')
    ci(0x0A0F, 'other reason codes -> chain to the previous handler')
    ci(0x0A11, 'Preserve A (reason code)...')
    ci(0x0A12, 'Preserve Y (INKEY high byte)...')
    ci(0x0A13, '...')
    ci(0x0A14, 'A := X = the INKEY key number being tested')
    ci(0x0A15, '...(X also preserved)')
    ci(0x0A16, 'No match yet...')
    ci(0x0A18, '...clear the result flag')
    dd.label(0x0A1B, 'scan_map')
    ci(0x0A1B, 'Does the tested key match this map entry?')
    ci(0x0A1E, 'no -> skip it')
    ci(0x0A20, 'yes -> read the joystick input for it')
    dd.label(0x0A23, 'scan_next')
    ci(0x0A23, 'Step over the 2-byte entry...')
    ci(0x0A24, '...')
    ci(0x0A25, 'first (button) block done?')
    ci(0x0A27, 'yes -> jump to the direction block')
    dd.label(0x0A29, 'scan_more')
    ci(0x0A29, 'End of the map?')
    ci(0x0A2B, 'no -> keep scanning')
    ci(0x0A2D, 'Did any mapped input read as active?')
    ci(0x0A30, 'no -> return the normal INKEY result')
    ci(0x0A32, 'yes: return "key pressed" (X=Y=&FF)...')
    ci(0x0A33, '...')
    ci(0x0A34, 'drop the saved X...')
    ci(0x0A35, '...Y...')
    ci(0x0A36, '...A')
    ci(0x0A37, 'and return, claiming the OSBYTE')
    dd.label(0x0A38, 'not_pressed')
    ci(0x0A38, 'Restore X...')
    ci(0x0A39, '...')
    ci(0x0A3A, 'Restore Y...')
    ci(0x0A3B, '...')
    ci(0x0A3C, 'Restore A')
    dd.label(0x0A3D, 'chain')
    ci(0x0A3D, 'Pass the call to the previous BYTEV (chain slot below)')
    dd.label(0x0A40, 'skip_to_directions')
    for a in (0x0A40, 0x0A41, 0x0A42, 0x0A43, 0x0A44, 0x0A45, 0x0A46, 0x0A47):
        ci(a, 'skip the 8-byte button block')
    ci(0x0A48, 'clear carry for the branch')
    ci(0x0A49, 'resume scanning the direction entries')

    dd.subroutine(
        0x0A4B, 'read_joystick',
        title='Test one analogue input',
        description="""For the matched entry, read its analogue channel with
OSBYTE &80 (ADVAL) and compare the value against the sensitivity thresholds
(a direction) or AND the fire-button bits (a button); flag a hit in result_flag.""",
    )
    ci(0x0A4B, 'Preserve A...')
    ci(0x0A4C, 'Preserve Y...')
    ci(0x0A4D, '...')
    ci(0x0A4E, 'Point at the entry parameter')
    ci(0x0A4F, 'top nibble = ADC channel...')
    ci(0x0A52, '...')
    for a in (0x0A54, 0x0A55, 0x0A56, 0x0A57):
        ci(a, '...shift it down')
    ci(0x0A58, '...into X for OSBYTE &80')
    ci(0x0A59, 'reload the parameter')
    ci(0x0A5C, 'direction entry (>= &10) or a fire button?')
    ci(0x0A5E, '>= &10 -> the fire-button path')
    ci(0x0A60, 'low bit picks which threshold (push vs pull)')
    ci(0x0A62, '...')
    ci(0x0A64, 'OSBYTE &80: read ADC channel X (ADVAL, Y=high byte)...')
    ci(0x0A66, '...')
    ci(0x0A69, 'past the low threshold?')
    ci(0x0A6C, 'no -> not active')
    ci(0x0A6E, 'yes -> active')
    dd.label(0x0A70, 'test_high_threshold')
    ci(0x0A70, 'OSBYTE &80: read ADC channel X...')
    ci(0x0A72, '...')
    ci(0x0A75, 'past the high threshold?')
    ci(0x0A78, 'no -> active')
    ci(0x0A7A, 'yes -> not active')
    dd.label(0x0A7C, 'test_button')
    ci(0x0A7C, 'fire-button mask (low 2 bits)...')
    ci(0x0A7E, '...saved')
    ci(0x0A81, 'OSBYTE &80: read ADC channel X...')
    ci(0x0A83, '...')
    ci(0x0A86, 'the returned button bits...')
    ci(0x0A87, '...AND the mask')
    ci(0x0A8A, 'none set -> not active')
    ci(0x0A8C, 'set -> active')
    dd.label(0x0A8E, 'active')
    ci(0x0A8E, 'Flag a hit...')
    ci(0x0A90, '...in result_flag')
    dd.label(0x0A93, 'read_done')
    ci(0x0A93, 'Restore Y...')
    ci(0x0A94, '...')
    ci(0x0A95, 'Restore A')
    ci(0x0A96, 'Done')

    # Data
    dd.byte(0x0A97, 1)
    dd.label(0x0A97, 'button_mask')
    ci(0x0A97, 'Scratch: fire-button mask (NOP at rest)')
    dd.byte(0x0A98, 1)
    dd.label(0x0A98, 'result_flag')
    ci(0x0A98, 'Set to &FF when a mapped input reads active')
    dd.byte(0x0A99, 0x0AB0 - 0x0A99)
    dd.label(0x0A99, 'unused_a')
    dd.comment(0x0A99, 'Unused')
    dd.byte(0x0AB0, 0x0AFA - 0x0AB0)
    dd.label(0x0AB0, 'joystick_map')
    dd.comment(0x0AB0, '2-byte entries (INKEY key number, parameter). The '
                       "parameter's top nibble is the ADC channel; the low bits "
                       'select the threshold / fire-button test. Buttons first, '
                       'then the four directions.')
    dd.byte(0x0AFA, 3)
    dd.label(0x0AFA, 'chain_to_old_bytev')
    dd.comment(0x0AFA, 'RTS placeholder; the BASIC (line 1840) patches this to '
                       'JMP <previous BYTEV> so non-INKEY OSBYTEs are chained.')
    dd.byte(0x0AFD, 1)
    dd.label(0x0AFD, 'threshold_lo')
    ci(0x0AFD, 'Low sensitivity threshold (BASIC line 1850: SL%)')
    dd.byte(0x0AFE, 1)
    dd.label(0x0AFE, 'threshold_hi')
    ci(0x0AFE, 'High sensitivity threshold (BASIC line 1850: SH%)')
    dd.byte(0x0AFF, 1)
    dd.label(0x0AFF, 'unused_a_end')
    ci(0x0AFF, 'Unused')


def annotate_driver_b(dd):
    """Variant B: joystick (analogue) plus keypad matrix (User VIA)."""
    ci = _annotate_driver_common(dd)
    dd.label(0xFE60, 'user_via_orb')
    dd.label(0xFE62, 'user_via_ddrb')
    dd.subroutine(
        0x0A0D, 'osbyte_intercept',
        title='BYTEV handler: map the joystick and keypad to INKEY',
        description="""As variant A, but joystick_map entries >= &10 test the
Delta 14B keypad matrix through the User VIA instead of an analogue channel.""",
    )
    ci(0x0A0D, 'Only intercept OSBYTE &81 (INKEY / read key)')
    ci(0x0A0F, 'other reason codes -> chain to the previous handler')
    ci(0x0A11, 'Preserve A (reason code)...')
    ci(0x0A12, 'Preserve Y (INKEY high byte)...')
    ci(0x0A13, '...')
    ci(0x0A14, 'A := X = the INKEY key number being tested')
    ci(0x0A15, '...(X also preserved)')
    ci(0x0A16, 'No match yet...')
    ci(0x0A18, '...clear the result flag')
    dd.label(0x0A1B, 'scan_map')
    ci(0x0A1B, 'Does the tested key match this map entry?')
    ci(0x0A1E, 'no -> skip it')
    ci(0x0A20, 'yes -> read the mapped input for it')
    dd.label(0x0A23, 'scan_next')
    ci(0x0A23, 'Step over the 2-byte entry...')
    ci(0x0A24, '...')
    ci(0x0A25, 'end of the map?')
    ci(0x0A27, 'no -> keep scanning')
    ci(0x0A29, 'Did any mapped input read as active?')
    ci(0x0A2C, 'no -> return the normal INKEY result')
    ci(0x0A2E, 'yes: return "key pressed" (X=Y=&FF)...')
    ci(0x0A2F, '...')
    ci(0x0A30, 'drop the saved X...')
    ci(0x0A31, '...Y...')
    ci(0x0A32, '...A')
    ci(0x0A33, 'and return, claiming the OSBYTE')
    dd.label(0x0A34, 'not_pressed')
    ci(0x0A34, 'Restore X...')
    ci(0x0A35, '...')
    ci(0x0A36, 'Restore Y...')
    ci(0x0A37, '...')
    ci(0x0A38, 'Restore A')
    dd.label(0x0A39, 'chain')
    ci(0x0A39, 'Pass the call to the previous BYTEV (chain slot below)')

    dd.subroutine(
        0x0A3C, 'read_input',
        title='Test one joystick or keypad input',
        description="""For the matched entry: entries below &10 read an analogue
channel (OSBYTE &80 / ADVAL) against the thresholds; entries >= &10 strobe a
keypad column through User VIA port B and test a row bit. A hit sets
result_flag.""",
    )
    ci(0x0A3C, 'Preserve A...')
    ci(0x0A3D, 'Preserve Y...')
    ci(0x0A3E, '...')
    ci(0x0A3F, 'Analogue entry (< &10) or keypad entry?')
    ci(0x0A41, '>= &10 -> the keypad path')
    ci(0x0A43, 'Point at the entry parameter')
    ci(0x0A44, 'ADC channel in the top nibble...')
    for a in (0x0A47, 0x0A48, 0x0A49, 0x0A4A):
        ci(a, '...shift it down...')
    ci(0x0A4B, '...into X for OSBYTE &80')
    ci(0x0A4C, 'reload the parameter')
    ci(0x0A4F, 'low bit picks which threshold (push vs pull)')
    ci(0x0A51, '...')
    ci(0x0A53, 'OSBYTE &80: read ADC channel X (ADVAL, Y=high byte)...')
    ci(0x0A55, '...')
    ci(0x0A58, 'past the low threshold?')
    ci(0x0A5B, 'no -> not active')
    ci(0x0A5D, 'yes -> active')
    dd.label(0x0A5F, 'test_high_threshold')
    ci(0x0A5F, 'OSBYTE &80: read ADC channel X...')
    ci(0x0A61, '...')
    ci(0x0A64, 'past the high threshold?')
    ci(0x0A67, 'no -> active')
    ci(0x0A69, 'yes -> not active')
    dd.label(0x0A6B, 'test_keypad')
    ci(0x0A6B, 'Point at the entry parameter')
    ci(0x0A6C, 'top nibble = the column strobe...')
    ci(0x0A6F, '...')
    ci(0x0A71, '...saved')
    ci(0x0A74, 'low nibble = the row bit mask...')
    ci(0x0A77, '...')
    ci(0x0A79, 'DDRB = &F0: strobes out, rows in...')
    ci(0x0A7B, '...')
    ci(0x0A7E, 'save the row mask')
    ci(0x0A81, 'Drive the column strobe...')
    ci(0x0A84, '...onto port B')
    ci(0x0A87, 'Read the rows back...')
    ci(0x0A8A, '...')
    ci(0x0A8B, '...and mask this row bit')
    ci(0x0A8E, 'low (pressed) -> not-active path... ')
    ci(0x0A90, 'high -> active')
    dd.label(0x0A92, 'active')
    ci(0x0A92, 'Flag a hit...')
    ci(0x0A94, '...in result_flag')
    dd.label(0x0A97, 'read_done')
    ci(0x0A97, 'Restore Y...')
    ci(0x0A98, '...')
    ci(0x0A99, 'Restore A')
    ci(0x0A9A, 'Done')

    # Data
    dd.byte(0x0A9B, 1)
    dd.label(0x0A9B, 'row_mask')
    ci(0x0A9B, 'Scratch: keypad row bit mask')
    dd.byte(0x0A9C, 1)
    dd.label(0x0A9C, 'col_strobe')
    ci(0x0A9C, 'Scratch: keypad column strobe')
    dd.byte(0x0A9D, 1)
    dd.label(0x0A9D, 'result_flag')
    ci(0x0A9D, 'Set to &FF when a mapped input reads active')
    dd.byte(0x0A9E, 0x0AB0 - 0x0A9E)
    dd.label(0x0A9E, 'unused_b')
    dd.comment(0x0A9E, 'Unused')
    dd.byte(0x0AB0, 0x0AFA - 0x0AB0)
    dd.label(0x0AB0, 'joystick_map')
    dd.comment(0x0AB0, '2-byte entries (INKEY key number, parameter). Entries '
                       'below &10 test an analogue channel (top nibble) against '
                       'the thresholds; entries >= &10 strobe a keypad column '
                       '(top nibble) and test a row bit (low nibble).')
    dd.byte(0x0AFA, 3)
    dd.label(0x0AFA, 'chain_to_old_bytev')
    dd.comment(0x0AFA, 'RTS placeholder; the BASIC (line 1840) patches this to '
                       'JMP <previous BYTEV> so non-INKEY OSBYTEs are chained.')
    dd.byte(0x0AFD, 1)
    dd.label(0x0AFD, 'threshold_lo')
    ci(0x0AFD, 'Low sensitivity threshold (BASIC line 1850: SL%)')
    dd.byte(0x0AFE, 1)
    dd.label(0x0AFE, 'threshold_hi')
    ci(0x0AFE, 'High sensitivity threshold (BASIC line 1850: SH%)')
    dd.byte(0x0AFF, 1)
    dd.label(0x0AFF, 'unused_b_end')
    ci(0x0AFF, 'Unused')


d = dasmos.Disassembler.create(
    cpu='6502',
    auto_label_data_prefix='l',
    auto_label_code_prefix='c',
    auto_label_subroutine_prefix='sub_c',
    auto_label_loop_prefix='loop_c',
)
d.load(_binary_filepath, LOAD_ADDR)
d.program(exec_addr=EXEC_ADDR, reload_addr=LOAD_ADDR)

# Decoy stub BASIC line at the very start.
d.byte(0x1900, EXEC_ADDR - 0x1900)
d.label(0x1900, 'decoy')

# The ROL-encoded drivers + BASIC, carried as editable source (see build).
d.include_binary(INCBIN_START, INCBIN_END - INCBIN_START, ENCODED_DAT_NAME)
d.label(INCBIN_START, 'encoded_region')
d.comment(INCBIN_START, 'ROL-encoded: driver variant A (&1A00), driver variant B '
                        '(&1B00), then the tokenised BASIC from PAGE=&1C00 '
                        '(raw past &4B00). Drivers: see driver_a.asm/driver_b.asm; '
                        'BASIC: basic/voltmace-delta-14b-driver-joystik.bas.')

# Tail after the BASIC: BBC BASIC's own variable heap, saved with the image.
d.byte(TAIL_START, 0x1900 + len(open(_binary_filepath, 'rb').read()) - TAIL_START)
d.label(TAIL_START, 'basic_variables')
d.comment(TAIL_START, "BBC BASIC's variable heap as it stood when the author saved "
                      'the &1900-&4D00 image: variable-name/value records for the '
                      "program globals (e.g. REV$=\"Rev 2.0\", and LR%, R1%, EV$, "
                      'LVL%, LVH%, S% ...). Not used by the loader; PAGE=&1C00 sits '
                      'below it, so BASIC rebuilds its own variables on RUN.')

# ---------------------------------------------------------------------------
# Annotation of the plain head loader (&1909-&19FF)
# ---------------------------------------------------------------------------
INLINE = dasmos.Align.INLINE


def c(addr, text):
    d.comment(addr, text, align=INLINE)


d.comment(0x1900, 'Decoy stub BASIC line (&0D, line 13, RTS bytes) so a naive '
                  '*LOAD/LIST at PAGE sees junk, not the loader')

# MOS entry points, OS locations, and zero page.
d.label(0xFFF4, 'osbyte')
d.label(0xE8AA, 'os_signature')    # three OS ROM bytes read as the "OS " tag
d.label(0xE8AB, 'os_signature_1')
d.label(0xE8AC, 'os_signature_2')
d.label(0x0300, 'kbd_buffer')      # &0300 page holding the MOS keyboard buffer
d.label(0x1C03, 'basic_line10_len')  # length byte of the relocated BASIC's line 10
d.label(0x0023C, 'autorun_index')  # running fill index into the keyboard buffer
d.label(0x0080, 'decode_ptr')      # &80/&81: ROL-decode cursor
d.label(0x0081, 'decode_ptr_hi')

d.subroutine(
    EXEC_ADDR, 'main',
    title='*RUN entry: decrypt and auto-run',
    description="""The DFS execution address. Decrypts the drivers and BASIC in
place, repairs the BASIC's first line, then queues PAGE=&1C00 / OLD / RUN so the
now-plain BASIC configuration program starts.""",
)
c(0x1909, 'Preserve A')
c(0x190A, 'Preserve X...')
c(0x190B, '...on the stack')
c(0x190C, 'Preserve Y...')
c(0x190D, '...on the stack')
c(0x190E, 'Decrypt the drivers and BASIC in place')
c(0x1911, "Repair the BASIC's first-line length byte")
c(0x1914, 'Queue the auto-run commands (OS-dependent)')
c(0x1917, 'Restore Y...')
c(0x1918, '...')
c(0x1919, 'Restore X...')
c(0x191A, '...')
c(0x191B, 'Restore A')
c(0x191C, 'Return to the MOS; the queued commands then run the BASIC')

d.subroutine(
    0x191D, 'decode_basic',
    title='Decrypt the drivers and BASIC',
    description="""Rotate every byte of &1A00-&4AFF left one bit (the inverse of
the ROL-1 storage protection), in place. That covers both driver variants
(&1A00, &1B00) and the tokenised BASIC from PAGE=&1C00; the loop stops at page
&4B, leaving the BASIC's raw tail untouched.""",
)
c(0x191D, 'Save the caller decode_ptr low byte...')
c(0x191F, '...')
c(0x1922, '...and high byte...')
c(0x1924, '...at decode_ptr_save')
c(0x1927, 'Point decode_ptr at &1A00: low byte 0...')
c(0x1929, '...')
c(0x192B, '...high byte &1A...')
c(0x192D, 'byte index 0')
d.label(0x192F, 'decode_next_page')
c(0x192F, 'Set the page being decrypted')
d.label(0x1931, 'decode_next_byte')
c(0x1931, 'Read an encrypted byte...')
c(0x1933, 'clear carry for the rotate')
c(0x1934, '...rotate it left one bit (undo the ROL-1 protection)...')
c(0x1935, '...carrying bit 7 into bit 0...')
c(0x1937, '...and store it back')
c(0x1939, 'Next byte...')
c(0x193A, '...to the end of the page')
c(0x193C, 'Next page...')
c(0x193E, '...')
c(0x193F, '...until page &4B (the BASIC raw tail is left alone)')
c(0x1941, '...')
c(0x1943, 'Restore the caller decode_ptr...')
c(0x1946, '...')
c(0x1948, '...')
c(0x194B, '...')
c(0x194D, 'Done')

d.subroutine(
    0x194E, 'os_dependent_setup',
    title='OS-version-dependent setup',
    description='Reads the three-byte "OS " ROM signature to pick how the '
                'auto-run commands are queued.',
)
c(0x194E, 'Count matching signature bytes in Y')
c(0x1950, 'First OS ROM byte...')
c(0x1953, "...'O'?")
c(0x1955, '...')
c(0x1957, 'match: bump the count')
d.label(0x1958, 'os_check_1')
c(0x1958, 'Second OS ROM byte...')
c(0x195B, "...'S'?")
c(0x195D, '...')
c(0x195F, 'match: bump the count')
d.label(0x1960, 'os_check_2')
c(0x1960, 'Third OS ROM byte...')
c(0x1963, "...' '?")
c(0x1965, '...')
c(0x1967, 'match: bump the count')
d.label(0x1968, 'os_check_done')
c(0x1968, 'All three bytes matched "OS "?')
c(0x196A, 'yes -> poke the buffer directly')
c(0x196C, 'no -> insert via OSBYTE')
c(0x196F, 'Done')
d.label(0x1970, 'use_direct_poke')
c(0x1970, 'Queue by poking the keyboard buffer')
c(0x1973, 'Done')

d.word(0x1974, 2, override=True)
d.label(0x1974, 'decode_ptr_save')
d.label(0x1975, 'decode_ptr_save_hi')
c(0x1974, "Scratch: caller's decode_ptr saved across decode_basic")

d.subroutine(
    0x1976, 'patch_header',
    title="Repair the BASIC program's first line",
    description="""Write &17 (23) into basic_line10_len, the length byte of the
line-10 REM at PAGE=&1C00, which is stored as 0 by the protection.""",
)
c(0x1976, 'The first BASIC line is 23 bytes long...')
c(0x1978, '...restore its length byte (stored as 0 by the protection)')
c(0x197B, 'Done')

d.subroutine(
    0x197C, 'queue_autorun',
    title='Queue the auto-run commands (direct poke)',
    description="""Copy autorun_commands into the MOS keyboard buffer so the OS
reads them as typed. autorun_index wraps into the 32-byte buffer at
&03E0-&03FF.""",
)
c(0x197C, 'Start at the first command byte')
d.label(0x197E, 'queue_next_byte')
c(0x197E, 'Current buffer fill position...')
c(0x1981, 'read a command byte...')
c(0x1984, '...&00 terminates')
c(0x1986, 'Poke it into the keyboard buffer')
c(0x1989, 'Advance the fill position...')
c(0x198C, '...')
c(0x198F, '...')
c(0x1991, '...wrapping back to &E0 (buffer at &03E0)...')
c(0x1993, '...')
d.label(0x1996, 'queue_advance')
c(0x1996, 'Next command byte')
c(0x1997, '...')
d.label(0x199A, 'queue_done')
c(0x199A, 'Done')

d.subroutine(
    0x199B, 'setup_keys',
    title='Queue the auto-run commands (OSBYTE path)',
    description="""The non-"OS "-signature variant of queue_autorun: set the
BREAK/ESCAPE behaviour, then insert each autorun_commands byte with OSBYTE &8A.""",
)
c(0x199B, 'OSBYTE 200: set the BREAK/ESCAPE behaviour...')
c(0x199D, '...')
c(0x199F, 'call OSBYTE')
c(0x19A2, 'Start at the first command byte')
d.label(0x19A4, 'insert_next_key')
c(0x19A4, 'Read a command byte...')
c(0x19A7, '...&00 terminates')
c(0x19A9, 'The character to insert')
c(0x19AA, 'Save the loop index...')
c(0x19AB, '...')
c(0x19AE, 'OSBYTE &8A: insert Y into buffer 0 (keyboard)...')
c(0x19B0, 'A = &8A')
c(0x19B2, 'call OSBYTE')
c(0x19B5, 'Restore the loop index...')
c(0x19B8, '...')
c(0x19B9, 'Next command byte')
c(0x19BA, '...')
d.label(0x19BD, 'setup_keys_done')
c(0x19BD, 'Done')

d.byte(0x19BE, 1)
d.label(0x19BE, 'setup_key_index')
c(0x19BE, 'Scratch: saved loop index (NOP at rest)')

# The auto-run command lines, fed to the keyboard buffer one byte at a time.
d.byte(0x19BF, 2)                    # &15, &0D
d.string(0x19C1, 9)                  # "PA.=&1C00"
d.byte(0x19CA, 1)
d.string(0x19CB, 3)                  # "OLD"
d.byte(0x19CE, 1)
d.string(0x19CF, 3)                  # "RUN"
d.byte(0x19D2, 2)                    # &0D, &00 terminator
d.label(0x19BF, 'autorun_commands')
c(0x19BF, 'CTRL-U + CR: clear the input line')
c(0x19C1, 'set PAGE to &1C00, where the BASIC lives')
c(0x19CA, 'submit')
c(0x19CB, 'reinstate the decoded program (OLD)')
c(0x19CE, 'submit')
c(0x19CF, 'run it (RUN)')
c(0x19D2, 'submit; the &00 then stops the queue copy')

# Uninitialised bytes between the loader and the drivers.
d.byte(0x19D4, DRIVER_A_ADDR - 0x19D4)
d.label(0x19D4, 'loader_tail')
d.comment(0x19D4, 'Unused bytes after the command list, up to the driver at '
                  '&1A00; referenced by nothing and inert.')

# Entry point: the *RUN loader.
d.entry(EXEC_ADDR)

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
output_filepath = _output_dirpath / 'voltmace-delta-14b-driver-joystik.asm'
output_filepath.write_text(output, encoding='utf-8')
print(f'Wrote {output_filepath}', file=sys.stderr)
json_filepath = _output_dirpath / 'voltmace-delta-14b-driver-joystik.json'
json_filepath.write_text(str(ir.render('json')), encoding='utf-8')
print(f'Wrote {json_filepath}', file=sys.stderr)

# Disassemble and annotate the two decrypted driver variants at their &0A00
# runtime address, write their listings, and assemble them back to bytes.
_image = open(_binary_filepath, 'rb').read()
_driver_bytes = {}
for _name, _addr, _annotate in (
    ('a', DRIVER_A_ADDR, annotate_driver_a),
    ('b', DRIVER_B_ADDR, annotate_driver_b),
):
    _dd = _make_driver_disassembler(_decoded(_image, _addr))
    _annotate(_dd)
    _asm = _render_driver(_dd)
    _asm_filepath = _output_dirpath / f'voltmace-delta-14b-driver-joystik-driver-{_name}.asm'
    _asm_filepath.write_text(_asm, encoding='utf-8')
    print(f'Wrote {_asm_filepath}', file=sys.stderr)
    _driver_bytes[_name] = _assemble(_asm)

# Regenerate the incbin payload from editable source and prove it matches the
# bytes dasmos accounted for.
dat_bytes = build_encoded_dat(_driver_bytes['a'], _driver_bytes['b'], _basic_filepath)
with tempfile.TemporaryDirectory() as tmp:
    ir.write_included_binaries(tmp)
    canonical = (Path(tmp) / ENCODED_DAT_NAME).read_bytes()
if dat_bytes != canonical:
    raise SystemExit(
        f'rebuilt payload does not match the image: '
        f'{len(dat_bytes)} bytes built vs {len(canonical)} canonical'
    )
dat_filepath = _output_dirpath / ENCODED_DAT_NAME
dat_filepath.write_bytes(dat_bytes)
print(f'Wrote {dat_filepath}', file=sys.stderr)
