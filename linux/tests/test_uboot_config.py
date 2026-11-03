#!/usr/bin/env python3
"""Kconfig peut ignorer silencieusement un symbole sans prompt : vérifier le résultat."""
from pathlib import Path
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--config', type=Path,
                    default=Path(__file__).resolve().parents[1]/'build/uboot/out/.config')
p=parser.parse_args().config
config=dict(line.split('=',1) for line in p.read_text().splitlines() if line.startswith('CONFIG_') and '=' in line)
for key in ['RISCV_MMODE','ANDES_PLMT_TIMER','TIMER','PRODOCK_SPI','MMC_SPI','CMD_BOOTMENU']:
    if config.get('CONFIG_'+key)!='y':raise SystemExit('Missing effective U-Boot option: '+key)
for key in ['RISCV_SMODE','ARCH_RV64I','SMP','MMC_WRITE','FAT_WRITE','CMD_SAVEENV']:
    if config.get('CONFIG_'+key)=='y':raise SystemExit('Unexpected U-Boot option: '+key)
print('PASS: U-Boot timer, SPI, menu, M-mode/RV32 and read-only SD configuration')
