#!/usr/bin/env python3
"""Generate the diagnostic CPU font from the exact FPGA font asset."""
import sys
from pathlib import Path
data = bytes(int(v, 16) for v in Path(sys.argv[1]).read_text().split())
assert len(data) == 4096
Path(sys.argv[2]).write_text(
    '// Generated from font8x16.hex; see tang/rtl/video/FONT_LICENSE.txt.\n'
    'static const unsigned char gpu_font[4096] = {\n' +
    ''.join(','.join(f'0x{v:02x}' for v in data[i:i+16])+',\n' for i in range(0,len(data),16)) + '};\n')
