#!/usr/bin/env python3
"""Pilote SD + FatFs contre un modèle de carte SDHC en mode SPI, sous UBSan et ASan, sans carte.

Une image FAT32 est créée par mkfs.vfat et remplie par mtools ; le firmware (fw_console/sd.c,
fatfs/) la lit et l'écrit à travers le modèle octet par octet de TESTS/host/sd_model.c ; le fichier
écrit par le firmware est ensuite relu par mtools, indépendamment de FatFs.
"""
import argparse,hashlib,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--megabytes',type=int,default=64);a=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='console_sd_') as tmp:
        work=Path(tmp);files=work/'files';(files/'SUB').mkdir(parents=True)
        (files/'SMALL.TXT').write_bytes(b'ORBITAL\r\n')
        (files/'BLOCK.BIN').write_bytes(bytes((i*7+i//256)&255 for i in range(512*9)))
        (files/'BIG.BIN').write_bytes(hashlib.shake_256(b'console').digest(3*1024*1024+123))
        (files/'SUB/DEEP.BIN').write_bytes(hashlib.shake_256(b'deep').digest(100001))
        image=work/'card.img'
        with image.open('wb') as f:f.truncate(a.megabytes<<20)
        subprocess.run(['mkfs.vfat','-F','32','-n','CONSOLE',str(image)],check=True,stdout=subprocess.DEVNULL)
        for name in ('SMALL.TXT','BLOCK.BIN','BIG.BIN'):subprocess.run(['mcopy','-i',str(image),str(files/name),'::'+name],check=True)
        subprocess.run(['mmd','-i',str(image),'::SUB'],check=True);subprocess.run(['mcopy','-i',str(image),str(files/'SUB/DEEP.BIN'),'::SUB/DEEP.BIN'],check=True)
        fw=ROOT/'fw_console'
        subprocess.run(['cc','-std=c11','-O1','-g','-Wall','-Wextra','-Wno-unused-parameter','-fsanitize=undefined,address','-fno-sanitize-recover=all',
            '-I',str(fw),'-I',str(fw/'fatfs'),str(ROOT/'TESTS/host/sd_test.c'),str(ROOT/'TESTS/host/sd_model.c'),str(fw/'sd.c'),str(fw/'fatfs/ff.c'),str(fw/'fatfs/diskio.c'),
            '-o',str(work/'sd_test')],check=True)
        run=subprocess.run([str(work/'sd_test'),str(image),str(files)],text=True,capture_output=True);print(run.stdout,end='');print(run.stderr,end='')
        assert run.returncode==0 and 'SD HOST PASS' in run.stdout
        # Le fichier écrit par le firmware, relu par mtools.
        subprocess.run(['mcopy','-i',str(image),'::WRITE.BIN',str(work/'WRITE.BIN')],check=True)
        assert (work/'WRITE.BIN').read_bytes()==bytes((i*131+i//251)&255 for i in range(70001))
        print('PASS : fichier écrit par le firmware relu identique par mtools')
if __name__=='__main__':main()
