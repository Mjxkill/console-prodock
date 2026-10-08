#!/usr/bin/env python3
"""Firmware du disque USB (Bulk-Only + SCSI) contre un modèle du port et de l'hôte, sous UBSan et ASan.

Sans carte ni contrôleur USB : TESTS/host/usb_msc_test.c joue l'hôte, découpe les octets validés
en paquets comme le matériel (512 puis 64 octets), et vérifie chaque commande, les frontières de
paquets, les résidus, les erreurs, la resynchronisation, le reset et l'abandon sur délai.
"""
import subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    with tempfile.TemporaryDirectory(prefix='console_usb_msc_') as tmp:
        exe=Path(tmp)/'usb_msc_test'
        subprocess.run(['cc','-std=c11','-O1','-g','-Wall','-Wextra','-fsanitize=undefined,address','-fno-sanitize-recover=all',
            '-DUSB_MSC_HOST_MODEL','-I',str(ROOT/'fw_console'),str(ROOT/'TESTS/host/usb_msc_test.c'),str(ROOT/'fw_console/usb_msc.c'),'-o',str(exe)],check=True)
        run=subprocess.run([str(exe)],text=True,capture_output=True);print(run.stdout,end='');print(run.stderr,end='')
        assert run.returncode==0 and 'USB MSC HOST PASS' in run.stdout
if __name__=='__main__':main()
