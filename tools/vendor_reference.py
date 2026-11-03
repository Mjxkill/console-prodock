"""Location of optional Sipeed reference designs used by historical analyses.

The production sources are in this repository. These comparisons additionally
need a checkout of TangMega-138KPro-example, selected by SIPEED_REFERENCE.
"""
import os
from pathlib import Path

ROOT = Path(os.environ.get('SIPEED_REFERENCE',
            Path(__file__).resolve().parents[1] / 'external/TangMega-138KPro-example')).expanduser()
USB = ROOT / 'usb2_soft/usb_uart_loopback/src'
