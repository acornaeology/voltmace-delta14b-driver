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

# Tail after the BASIC.
d.byte(TAIL_START, 0x1900 + len(open(_binary_filepath, 'rb').read()) - TAIL_START)
d.label(TAIL_START, 'tail')

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
