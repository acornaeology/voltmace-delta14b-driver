"""Disassembly driver for the Voltmace Delta 14B/1 JOYSTIK driver.

Run via:
  uv run fantasm disassemble joystik

The file loads at &1900 and executes at &1909. Its layout:

  &1900-&1908  decoy: a stub BASIC line so a naive *LOAD/LIST sees junk.
  &1909-&19FF  head loader (plain 6502): ROL-decrypts &1A00-&4AFF in place,
               repairs the BASIC's first line, and queues PAGE=&1C00/OLD/RUN.
  &1A00-&1AFF  joystick resident-driver template, variant A (6502, ROL-encoded here;
               runs at &0A00 -- hooks BYTEV and intercepts OSBYTE &81). Its
               joystick_map keys, thresholds and BYTEV chain slot are blank until
               the BASIC configures a copy at &0A00 and installs it.
  &1B00-&1BFF  joystick resident-driver template, variant B (same, an alternate build).
  &1C00-&4AFF  the configuration/demo program, tokenised BBC BASIC (PAGE),
               ROL-encoded; the loader decrypts it up to page &4B.
  &4B00-&4C92  the rest of that BASIC, stored RAW (beyond the decode range).
  &4C93-&4CFF  tail.

The ROL-encoded region (&1A00-&4C92, resident-driver templates + BASIC) is carried as
editable source -- the templates as annotated disassembly, the BASIC as basic/*.bas --
and re-encoded to three incbin payloads at build time (build_encoded_dats), so the
whole file still reassembles byte-identically.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import dasmos
from dasmos.expr import lo, hi, sym

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

# The ROL-encoded region is three conceptually distinct binaries, each carried
# as its own incbin: the two resident-driver templates and the tokenised BASIC.
DRIVER_A_DAT_NAME = 'voltmace-delta-14b-driver-joystik-driver-a-encoded.dat'
DRIVER_B_DAT_NAME = 'voltmace-delta-14b-driver-joystik-driver-b-encoded.dat'
BASIC_DAT_NAME = 'voltmace-delta-14b-driver-joystik-basic-encoded.dat'

LOAD_ADDR = 0x1900          # DFS load address
EXEC_ADDR = 0x1909          # DFS execution address (*RUN entry)
DRIVER_A_ADDR = 0x1A00      # resident-driver template A, stored here
DRIVER_B_ADDR = 0x1B00      # resident-driver template B, stored here
DRIVER_LEN = 0x0100         # each resident-driver template is 256 bytes
BASIC_PAGE = 0x1C00         # PAGE of the tokenised BASIC
ENC_END = 0x4B00            # decode stops here (loader: cpx #&4B)
BASIC_END = 0x4C93          # one past the BASIC's &0D &FF terminator
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


DRIVER_RUNTIME = 0x0A00      # both resident driver variants run relocated here


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
    dd.use_environment("acorn_mos")
    dd.use_environment("acorn_model_b_hardware")
    os.unlink(tmp.name)
    return dd


def _render_driver(driver_ir):
    return str(driver_ir.render(
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


def build_encoded_dats(driver_a_bytes, driver_b_bytes, bas_filepath):
    """Regenerate the three incbin payloads from editable source.

    The loader ROL-decrypts &1A00-&4AFF in place, byte by byte, so each part
    is ROR-encoded independently (the inverse). The two resident-driver
    templates come from assembling their annotated disassembly; the BASIC part
    is the tokenised BASIC ROR-encoded up to the decode limit (&4B00), then its
    raw tail appended unencoded. Returns (driver_a, driver_b, basic) bytes.
    """
    basic = _tokenise_basic(bas_filepath)
    split = ENC_END - BASIC_PAGE            # BASIC bytes that fall inside the decode range
    driver_a_dat = bytes(_ror(b) for b in driver_a_bytes)
    driver_b_dat = bytes(_ror(b) for b in driver_b_bytes)
    basic_dat = bytes(_ror(b) for b in basic[:split]) + basic[split:]
    return driver_a_dat, driver_b_dat, basic_dat


def _emit_joystick_map(dd, driver_bytes, comment_fn):
    """Render joystick_map as one 2-byte entry per line, each with its own comment."""
    base = 0x0AB0
    for addr in range(base, 0x0AFA, 2):
        i = (addr - base) // 2
        key = driver_bytes[addr - DRIVER_RUNTIME]
        param = driver_bytes[addr - DRIVER_RUNTIME + 1]
        dd.byte(addr, 2, override=True)
        dd.comment(addr, comment_fn(i, key, param), align=dasmos.Align.INLINE)
    dd.label(base, 'joystick_map')
    dd.comment(base, '2-byte entries <INKEY key, input descriptor>. The key byte '
                     'is 0 here; the BASIC (PROCASSEM, lines 1780-1830) pokes each '
                     "with the user's chosen INKEY value. The fixed descriptor "
                     'decodes as:')


def _map_comment_a(i, key, param):
    hi, lo = param >> 4, param & 0xF
    if i < 8:
        return (f'joystick axis: ADC channel {hi}, '
                f"{'high' if lo & 1 == 0 else 'low'} threshold")
    if param == 0:
        return 'end-of-map marker'
    if hi == 0:
        return f'fire button: ADVAL(0), bit mask &{lo:X}'
    return f'keypad cell &{param:02X} (inert in this analogue-only variant)'


def _map_comment_b(i, key, param):
    hi, lo = param >> 4, param & 0xF
    if i < 8:
        return (f'joystick axis: ADC channel {hi}, '
                f"{'high' if lo & 1 == 0 else 'low'} threshold")
    if param == 0:
        return 'end-of-map marker'
    return f'keypad: strobe column &{param & 0xF0:02X}, test row bit &{lo:X}'


def _annotate_driver_common(dd):
    """Labels, install routine, and BYTEV-handler frame shared by both resident driver variants."""
    # bytev (&020A), osbyte (&FFF4) and the User VIA come from the acorn_mos /
    # acorn_model_b_hardware environments; only the vector's high byte needs a name.
    dd.label(0x020B, 'bytev_hi')
    # The reason code this driver claims off BYTEV; used by the cmp below.
    dd.constant(0x81, 'osbyte_inkey')
    dd.expr(0x0A0E, sym('osbyte_inkey'))
    dd.entry(0x0A00)                     # install (BASIC: CALL &A00)
    dd.entry(0x0A0D)                     # BYTEV handler (reached via the vector)

    def ci(addr, text):
        dd.comment(addr, text, align=dasmos.Align.INLINE)

    dd.subroutine(
        0x0A00, 'install',
        title='Install the resident joystick driver',
        description="""Point BYTEV at the OSBYTE intercept at &0A0D. Called from
the BASIC via CALL &A00, after it has saved the previous BYTEV (line 50) and
patched the chain slot (line 1840) and sensitivity thresholds (line 1850).""",
    )
    ci(0x0A00, 'Preserve A')
    ci(0x0A01, 'BYTEV low byte -> &0D...')
    ci(0x0A03, 'store it')
    ci(0x0A06, '...high byte -> &0A...')
    ci(0x0A08, '...so every OSBYTE now enters the handler at &0A0D')
    ci(0x0A0B, 'Restore A')
    ci(0x0A0C, 'Return to the BASIC caller')
    return ci


def annotate_driver_a(dd, driver_bytes):
    """Resident driver, variant A: joystick only (analogue port via OSBYTE &80 / ADVAL)."""
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
    ci(0x0A13, 'on the stack')
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
    ci(0x0A24, 'twice')
    ci(0x0A25, "first joystick's direction entries (channels 1-2) done?")
    ci(0x0A27, 'yes -> skip the second joystick and go to the fire buttons')
    dd.label(0x0A29, 'scan_more')
    ci(0x0A29, 'End of the map?')
    ci(0x0A2B, 'no -> keep scanning')
    ci(0x0A2D, 'Did any mapped input read as active?')
    ci(0x0A30, 'no -> return the normal INKEY result')
    ci(0x0A32, 'yes: return "key pressed" (X=Y=&FF)...')
    ci(0x0A33, 'X and Y')
    ci(0x0A34, 'drop the saved X...')
    ci(0x0A35, '...Y...')
    ci(0x0A36, '...A')
    ci(0x0A37, 'and return, claiming the OSBYTE')
    dd.label(0x0A38, 'not_pressed')
    ci(0x0A38, 'Restore X...')
    ci(0x0A39, 'into X')
    ci(0x0A3A, 'Restore Y...')
    ci(0x0A3B, 'into Y')
    ci(0x0A3C, 'Restore A')
    dd.label(0x0A3D, 'chain')
    ci(0x0A3D, 'Pass the call to the previous BYTEV (chain slot below)')
    dd.label(0x0A40, 'skip_to_buttons')
    for a in (0x0A40, 0x0A41, 0x0A42, 0x0A43, 0x0A44, 0x0A45, 0x0A46, 0x0A47):
        ci(a, "skip channels 3-4 (the second joystick's direction entries)")
    ci(0x0A48, 'clear carry for the branch')
    ci(0x0A49, 'resume scanning at the fire-button entries')

    dd.subroutine(
        0x0A4B, 'read_joystick',
        title='Test one analogue input',
        description="""For the matched entry, read its analogue channel with
OSBYTE &80 (ADVAL) and compare the value against the sensitivity thresholds
(a direction) or AND the fire-button bits (a button); flag a hit in result_flag.""",
    )
    ci(0x0A4B, 'Preserve A...')
    ci(0x0A4C, 'Preserve Y...')
    ci(0x0A4D, 'on the stack')
    ci(0x0A4E, 'Point at the entry parameter')
    ci(0x0A4F, 'top nibble = ADC channel...')
    ci(0x0A52, 'mask the top nibble')
    for a in (0x0A54, 0x0A55, 0x0A56, 0x0A57):
        ci(a, '...shift it down')
    ci(0x0A58, '...into X for OSBYTE &80')
    ci(0x0A59, 'reload the parameter')
    ci(0x0A5C, 'axis entry (offset < &10) or a fire button (offset >= &10)?')
    ci(0x0A5E, 'offset >= &10 -> the fire-button path')
    ci(0x0A60, 'low bit picks which threshold (push vs pull)')
    ci(0x0A62, 'else test the high threshold')
    ci(0x0A64, 'OSBYTE &80: read ADC channel X (ADVAL, Y=high byte)...')
    ci(0x0A66, 'call OSBYTE')
    ci(0x0A69, 'past the low threshold?')
    ci(0x0A6C, 'no -> not active')
    ci(0x0A6E, 'yes -> active')
    dd.label(0x0A70, 'test_high_threshold')
    ci(0x0A70, 'OSBYTE &80: read ADC channel X...')
    ci(0x0A72, 'call OSBYTE')
    ci(0x0A75, 'past the high threshold?')
    ci(0x0A78, 'no -> active')
    ci(0x0A7A, 'yes -> not active')
    dd.label(0x0A7C, 'test_button')
    ci(0x0A7C, 'fire-button mask (low 2 bits)...')
    ci(0x0A7E, '...saved')
    ci(0x0A81, 'OSBYTE &80: read ADC channel X...')
    ci(0x0A83, 'call OSBYTE')
    ci(0x0A86, 'the returned button bits...')
    ci(0x0A87, '...AND the mask')
    ci(0x0A8A, 'none set -> not active')
    ci(0x0A8C, 'set -> active')
    dd.label(0x0A8E, 'active')
    ci(0x0A8E, 'Flag a hit...')
    ci(0x0A90, '...in result_flag')
    dd.label(0x0A93, 'read_done')
    ci(0x0A93, 'Restore Y...')
    ci(0x0A94, 'store it')
    ci(0x0A95, 'Restore A')
    ci(0x0A96, 'Done')

    # Data
    dd.byte(0x0A97, 1)
    dd.label(0x0A97, 'button_mask')
    ci(0x0A97, 'Scratch: fire-button mask (&EA at rest)')
    dd.byte(0x0A98, 1)
    dd.label(0x0A98, 'result_flag')
    ci(0x0A98, 'Result byte (&EA at rest): the handler zeroes it, then sets it to '
               '&FF if a mapped input reads active')
    dd.byte(0x0A99, 0x0AB0 - 0x0A99)
    dd.label(0x0A99, 'unused_a')
    dd.comment(0x0A99, 'Unused')
    _emit_joystick_map(dd, driver_bytes, _map_comment_a)
    dd.byte(0x0AFA, 3)
    dd.label(0x0AFA, 'chain_to_old_bytev')
    dd.comment(0x0AFA, 'RTS placeholder; the BASIC (line 1840) patches this to '
                       'JMP <previous BYTEV> so non-INKEY OSBYTEs are chained.')
    dd.byte(0x0AFD, 1)
    dd.label(0x0AFD, 'threshold_lo')
    ci(0x0AFD, 'Low-threshold comparison value; BASIC line 1850 pokes SH% here')
    dd.byte(0x0AFE, 1)
    dd.label(0x0AFE, 'threshold_hi')
    ci(0x0AFE, 'High-threshold comparison value; BASIC line 1850 pokes SL% here')
    dd.byte(0x0AFF, 1)
    dd.label(0x0AFF, 'unused_a_end')
    ci(0x0AFF, 'Unused')


def annotate_driver_b(dd, driver_bytes):
    """Resident driver, variant B: joystick (analogue) plus keypad matrix (User VIA)."""
    ci = _annotate_driver_common(dd)
    # user_via_orb_irb (&FE60) / user_via_ddrb (&FE62) come from acorn_model_b_hardware.
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
    ci(0x0A13, 'on the stack')
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
    ci(0x0A24, 'twice')
    ci(0x0A25, 'end of the map?')
    ci(0x0A27, 'no -> keep scanning')
    ci(0x0A29, 'Did any mapped input read as active?')
    ci(0x0A2C, 'no -> return the normal INKEY result')
    ci(0x0A2E, 'yes: return "key pressed" (X=Y=&FF)...')
    ci(0x0A2F, 'X and Y')
    ci(0x0A30, 'drop the saved X...')
    ci(0x0A31, '...Y...')
    ci(0x0A32, '...A')
    ci(0x0A33, 'and return, claiming the OSBYTE')
    dd.label(0x0A34, 'not_pressed')
    ci(0x0A34, 'Restore X...')
    ci(0x0A35, 'into X')
    ci(0x0A36, 'Restore Y...')
    ci(0x0A37, 'into Y')
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
    ci(0x0A3E, 'on the stack')
    ci(0x0A3F, 'Analogue entry (< &10) or keypad entry?')
    ci(0x0A41, '>= &10 -> the keypad path')
    ci(0x0A43, 'Point at the entry parameter')
    ci(0x0A44, 'ADC channel in the top nibble...')
    for a in (0x0A47, 0x0A48, 0x0A49, 0x0A4A):
        ci(a, '...shift it down...')
    ci(0x0A4B, '...into X for OSBYTE &80')
    ci(0x0A4C, 'reload the parameter')
    ci(0x0A4F, 'low bit picks which threshold (push vs pull)')
    ci(0x0A51, 'else test the high threshold')
    ci(0x0A53, 'OSBYTE &80: read ADC channel X (ADVAL, Y=high byte)...')
    ci(0x0A55, 'call OSBYTE')
    ci(0x0A58, 'past the low threshold?')
    ci(0x0A5B, 'no -> not active')
    ci(0x0A5D, 'yes -> active')
    dd.label(0x0A5F, 'test_high_threshold')
    ci(0x0A5F, 'OSBYTE &80: read ADC channel X...')
    ci(0x0A61, 'call OSBYTE')
    ci(0x0A64, 'past the high threshold?')
    ci(0x0A67, 'no -> active')
    ci(0x0A69, 'yes -> not active')
    dd.label(0x0A6B, 'test_keypad')
    ci(0x0A6B, 'Point at the entry parameter')
    ci(0x0A6C, 'top nibble = the column strobe...')
    ci(0x0A6F, 'mask the top nibble')
    ci(0x0A71, '...saved')
    ci(0x0A74, 'low nibble = the row bit mask...')
    ci(0x0A77, 'mask the low nibble')
    ci(0x0A79, 'DDRB = &F0: strobes out, rows in...')
    ci(0x0A7B, 'set it')
    ci(0x0A7E, 'save the row mask')
    ci(0x0A81, 'Drive the column strobe...')
    ci(0x0A84, '...onto port B')
    ci(0x0A87, 'Read the rows back...')
    ci(0x0A8A, 'into A')
    ci(0x0A8B, '...and mask this row bit')
    ci(0x0A8E, 'low (pressed) -> not-active path... ')
    ci(0x0A90, 'high -> active')
    dd.label(0x0A92, 'active')
    ci(0x0A92, 'Flag a hit...')
    ci(0x0A94, '...in result_flag')
    dd.label(0x0A97, 'read_done')
    ci(0x0A97, 'Restore Y...')
    ci(0x0A98, 'into Y')
    ci(0x0A99, 'Restore A')
    ci(0x0A9A, 'Done')

    # Data
    dd.byte(0x0A9B, 1)
    dd.label(0x0A9B, 'row_mask')
    ci(0x0A9B, 'Scratch: keypad row bit mask (&EA at rest)')
    dd.byte(0x0A9C, 1)
    dd.label(0x0A9C, 'col_strobe')
    ci(0x0A9C, 'Scratch: keypad column strobe (&EA at rest)')
    dd.byte(0x0A9D, 1)
    dd.label(0x0A9D, 'result_flag')
    ci(0x0A9D, 'Result byte (&EA at rest): the handler zeroes it, then sets it to '
               '&FF if a mapped input reads active')
    dd.byte(0x0A9E, 0x0AB0 - 0x0A9E)
    dd.label(0x0A9E, 'unused_b')
    dd.comment(0x0A9E, 'Unused')
    _emit_joystick_map(dd, driver_bytes, _map_comment_b)
    dd.byte(0x0AFA, 3)
    dd.label(0x0AFA, 'chain_to_old_bytev')
    dd.comment(0x0AFA, 'RTS placeholder; the BASIC (line 1840) patches this to '
                       'JMP <previous BYTEV> so non-INKEY OSBYTEs are chained.')
    dd.byte(0x0AFD, 1)
    dd.label(0x0AFD, 'threshold_lo')
    ci(0x0AFD, 'Low-threshold comparison value; BASIC line 1850 pokes SH% here')
    dd.byte(0x0AFE, 1)
    dd.label(0x0AFE, 'threshold_hi')
    ci(0x0AFE, 'High-threshold comparison value; BASIC line 1850 pokes SL% here')
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
# MOS + Model B hardware knowledge: names the OS entry points and vectors, the
# User VIA, and turns reason-code immediates before JSR osbyte/osword symbolic.
d.use_environment("acorn_mos")
d.use_environment("acorn_model_b_hardware")
d.program(exec_addr=EXEC_ADDR, reload_addr=LOAD_ADDR)

# Decoy stub BASIC line at the very start.
d.byte(0x1900, EXEC_ADDR - 0x1900)
d.label(0x1900, 'decoy')

# The three conceptually distinct binaries in the ROL-encoded region, each its
# own incbin, all carried as editable source and regenerated at build time.
d.include_binary(DRIVER_A_ADDR, DRIVER_LEN, DRIVER_A_DAT_NAME)
d.label(DRIVER_A_ADDR, 'driver_a_template_encoded')
d.banner(DRIVER_A_ADDR, title='Resident-driver template A (encoded)',
         description='ROL-encoded, 256 bytes; runs at &0A00. Disassembled in '
                     'driver-a.asm.')
d.include_binary(DRIVER_B_ADDR, DRIVER_LEN, DRIVER_B_DAT_NAME)
d.label(DRIVER_B_ADDR, 'driver_b_template_encoded')
d.banner(DRIVER_B_ADDR, title='Resident-driver template B (encoded)',
         description='ROL-encoded, 256 bytes; runs at &0A00. Disassembled in '
                     'driver-b.asm.')
d.include_binary(BASIC_PAGE, BASIC_END - BASIC_PAGE, BASIC_DAT_NAME)
d.label(BASIC_PAGE, 'basic_encoded')
d.banner(BASIC_PAGE, title='Tokenised BASIC front-end (encoded)',
         description='The configuration program (PAGE=&1C00), ROL-encoded up to '
                     'basic_raw_tail then stored raw. Source: '
                     'basic/voltmace-delta-14b-driver-joystik.bas.')
d.label(ENC_END, 'basic_raw_tail')
d.comment(ENC_END, 'The loader stops decrypting here (page &4B): the rest of the '
                   'BASIC is stored raw, beyond the decode range.')

# Tail after the BASIC: BBC BASIC's own variable heap, saved with the image.
d.byte(TAIL_START, 0x1900 + len(open(_binary_filepath, 'rb').read()) - TAIL_START)
d.label(TAIL_START, 'fossilised_basic_heap')
d.banner(TAIL_START, title='Fossilised BASIC heap',
         description="BBC BASIC's variable heap as it stood when the author saved "
                     'the &1900-&4D00 image: variable-name/value records for the '
                     'program globals (e.g. REV$="Rev 2.0", and LR%, R1%, EV$, '
                     'LVL%, LVH%, S% ...). Not used by the loader; PAGE=&1C00 sits '
                     'below it, so BASIC rebuilds its own variables on RUN.')

# ---------------------------------------------------------------------------
# Annotation of the plain head loader (&1909-&19FF)
# ---------------------------------------------------------------------------
INLINE = dasmos.Align.INLINE


def c(addr, text):
    d.comment(addr, text, align=INLINE)


d.comment(0x1900, 'Decoy stub BASIC line (&0D, line 13, RTS bytes) so a naive '
                  '*LOAD/LIST at PAGE sees junk, not the loader. It is 9 bytes '
                  '(&1900-&1908); the exec address &1909 starts just past it. '
                  '(KEYPAD has no such decoy: its file opens on the resident '
                  'driver, and its loader sits in the tail at &3906.)')

# MOS entry points, OS locations, and zero page. This is the loader's
# view; the resident drivers add BYTEV, the analogue port and the User
# VIA on top (see the driver-variant listings).
d.label(0xFFF4, 'osbyte', group='os_entry_points',
        description='OSBYTE: used to read/set vectors and enable ADC input '
                    'while the loader hands off to the BASIC.')
d.label(0xE8AA, 'os_signature', group='os_rom', access='r', length=3,
        description='Three OS ROM bytes read as the "OS " tag to distinguish '
                    'OS versions and choose the command hand-off path.')
d.label(0xE8AB, 'os_signature_1')
d.label(0xE8AC, 'os_signature_2')
d.label(0x0300, 'kbd_buffer', group='os_workspace', access='w',
        description='Base of the &0300 page holding the MOS keyboard buffer, '
                    'written directly on the fast hand-off path.')
d.label(0x1C03, 'basic_line10_len', group='basic_workspace', access='w',
        description='Length byte of the relocated BASIC\'s line 10, patched '
                    'from 0 back to &17 so the protected program lists and runs.')
d.label(0x0023C, 'autorun_index', group='os_workspace', access='rw',
        description='Running fill index into the keyboard buffer as the loader '
                    'queues its PAGE / OLD / RUN commands.')
d.label(0x0080, 'decode_ptr', group='zero_page', access='rw', length=2,
        description='ROL-decode cursor sweeping the encrypted drivers and BASIC '
                    'in place.')
d.label(0x0081, 'decode_ptr_hi')

d.subroutine(
    EXEC_ADDR, 'main',
    title='*RUN entry: decrypt and auto-run',
    description="""The file system execution address (*RUN entry-point) for this
binary; it starts just past the decoy stub at &1900. Decrypts the resident
drivers and BASIC in place, writes the correct length byte back into the BASIC's
first line, then queues PAGE=&1C00 / OLD / RUN so the now-plain BASIC
configuration program starts.""",
)
c(0x1909, 'Preserve A')
c(0x190A, 'Preserve X...')
c(0x190B, '...on the stack')
c(0x190C, 'Preserve Y...')
c(0x190D, '...on the stack')
c(0x190E, 'Decrypt the resident drivers and BASIC in place')
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
    title='Decrypt the resident drivers and BASIC',
    description="""Rotate every byte of &1A00-&4AFF left one bit (the inverse of
the ROL-1 storage protection), in place. That covers both resident driver variants
(&1A00, &1B00) and the tokenised BASIC from PAGE=&1C00; the loop stops at page
&4B, leaving the BASIC's raw tail untouched.""",
)
c(0x191D, 'Save the caller decode_ptr low byte...')
c(0x191F, '...')
c(0x1922, '...and high byte...')
c(0x1924, '...at decode_ptr_save')
# decode_ptr starts at the encoded region (&1A00); render the immediates as its
# low/high bytes so they track the label.
d.expr(0x1928, lo(sym('driver_a_template_encoded')))
d.expr(0x192C, hi(sym('driver_a_template_encoded')))
c(0x1927, 'Point decode_ptr at the encoded region (&1A00): low byte...')
c(0x1929, '...')
c(0x192B, '...high byte...')
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
d.expr(0x1940, hi(sym('basic_raw_tail')))
c(0x193F, '...until basic_raw_tail (page &4B); the raw tail is left alone')
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
c(0x19BE, 'Scratch: saved loop index (&EA at rest)')

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

# Captured leftover RAM between the loader and the resident drivers.
d.byte(0x19D4, DRIVER_A_ADDR - 0x19D4)
d.label(0x19D4, 'fossilised_memory')
d.banner(0x19D4, title='Fossilised memory',
         description='Whatever occupied memory after the command list when the '
                     'image was saved, up to the resident driver at &1A00: '
                     'high-entropy noise, referenced by nothing and inert.')

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

# Disassemble and annotate the two decrypted resident-driver templates at their &0A00
# runtime address, write their listings, and assemble them back to bytes.
_image = open(_binary_filepath, 'rb').read()
_driver_bytes = {}
for _name, _addr, _annotate in (
    ('a', DRIVER_A_ADDR, annotate_driver_a),
    ('b', DRIVER_B_ADDR, annotate_driver_b),
):
    _bytes = _decoded(_image, _addr)
    _dd = _make_driver_disassembler(_bytes)
    _annotate(_dd, _bytes)
    _driver_ir = _dd.disassemble()
    _stem = f'voltmace-delta-14b-driver-joystik-driver-{_name}'
    _asm = _render_driver(_driver_ir)
    _asm_filepath = _output_dirpath / f'{_stem}.asm'
    _asm_filepath.write_text(_asm, encoding='utf-8')
    print(f'Wrote {_asm_filepath}', file=sys.stderr)
    # Also emit the structured JSON so the site can render the variant as
    # a formatted, anchored disassembly (not just plain text).
    _driver_json_filepath = _output_dirpath / f'{_stem}.json'
    _driver_json_filepath.write_text(str(_driver_ir.render('json')), encoding='utf-8')
    print(f'Wrote {_driver_json_filepath}', file=sys.stderr)
    _driver_bytes[_name] = _assemble(_asm)

# Regenerate the three incbin payloads from editable source and prove each
# matches the bytes dasmos accounted for.
_dats = build_encoded_dats(_driver_bytes['a'], _driver_bytes['b'], _basic_filepath)
_dat_names = (DRIVER_A_DAT_NAME, DRIVER_B_DAT_NAME, BASIC_DAT_NAME)
with tempfile.TemporaryDirectory() as tmp:
    ir.write_included_binaries(tmp)
    for _name, _dat in zip(_dat_names, _dats):
        _canonical = (Path(tmp) / _name).read_bytes()
        if _dat != _canonical:
            raise SystemExit(
                f'rebuilt {_name} does not match the image: '
                f'{len(_dat)} bytes built vs {len(_canonical)} canonical'
            )
for _name, _dat in zip(_dat_names, _dats):
    _dat_filepath = _output_dirpath / _name
    _dat_filepath.write_bytes(_dat)
    print(f'Wrote {_dat_filepath}', file=sys.stderr)
