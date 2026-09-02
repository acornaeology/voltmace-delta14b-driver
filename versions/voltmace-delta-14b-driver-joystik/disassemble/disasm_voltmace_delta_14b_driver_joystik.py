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


def build_encoded_dat(binary_filepath, bas_filepath):
    """Regenerate the incbin payload (&1A00-&4C92) from editable source.

    The loader ROL-decrypts &1A00-&4AFF in place, so the plaintext of that
    region is [driver A][driver B][encoded part of the BASIC]; we ROR-encode
    it (the inverse) and append the BASIC's raw tail (&4B00+, beyond the decode
    range).
    """
    image = open(binary_filepath, 'rb').read()
    # TODO(driver-asm): source the driver bytes by assembling the annotated
    # driver disassemblies; for now recover them from the image (identical).
    driver_a = bytes(_rol(b) for b in image[DRIVER_A_ADDR - LOAD_ADDR:DRIVER_B_ADDR - LOAD_ADDR])
    driver_b = bytes(_rol(b) for b in image[DRIVER_B_ADDR - LOAD_ADDR:BASIC_PAGE - LOAD_ADDR])

    basic = _tokenise_basic(bas_filepath)
    split = ENC_END - BASIC_PAGE            # BASIC bytes that fall inside the decode range
    plain_encoded = driver_a + driver_b + basic[:split]
    return bytes(_ror(b) for b in plain_encoded) + basic[split:]


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

# Regenerate the incbin payload from editable source and prove it matches the
# bytes dasmos accounted for.
dat_bytes = build_encoded_dat(_binary_filepath, _basic_filepath)
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
