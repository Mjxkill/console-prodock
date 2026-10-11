#!/usr/bin/env python3
"""Installe seulement le nouveau dossier PRODOCK sur la SD qualifiée, sans formatage.

Exiger les six images préparées, la console USB 11252024, le nombre de secteurs
et le secteur FAT attendus. Préserver CONSOLE.TST et refuser un dossier existant.
Le montage temporaire demande root sur ax15 ; --check-package n'accède pas au matériel.
"""
import argparse,hashlib,json,os,shutil,subprocess,tempfile,zlib
from pathlib import Path
NAMES={'UBOOT.BIN','LINUX.BIN','LUMA.BIN','LUMA.DAT','ORBITAL.BIN','ORBITAL.DAT'}
BOOT_SHA='b38bfbbef097132a872ea66d636324ed9c0e0d9846299a466e3eeb7ae2ef363b'
SECTORS=31116288

def require(test,message):
    if not test:raise RuntimeError(message)

def fingerprint(path):
    sha=hashlib.sha256();crc=0;size=0
    with path.open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):
            sha.update(part);crc=zlib.crc32(part,crc);size+=len(part)
    return size,sha.hexdigest(),crc

def target():
    found=[]
    for block in Path('/sys/class/block').iterdir():
        if (block/'partition').exists():continue
        for parent in (block.resolve(),*block.resolve().parents):
            try:identity=((parent/'idVendor').read_text().strip(),(parent/'idProduct').read_text().strip(),(parent/'serial').read_text().strip())
            except OSError:continue
            if identity==('359f','2011','11252024'):
                require((parent/'speed').read_text().strip()=='480','USB HS requis')
                found.append(block);break
    require(len(found)==1,'Une seule SD USB de la console doit être présente et liée à usb-storage')
    block=found[0];require(int((block/'size').read_text())==SECTORS,'Capacité différente de la SD qualifiée')
    dev=Path('/dev')/block.name
    with dev.open('rb',buffering=0) as f:boot=f.read(512)
    require(hashlib.sha256(boot).hexdigest()==BOOT_SHA,'Secteur FAT différent de la SD qualifiée')
    return dev

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pack',type=Path,required=True);p.add_argument('--check-package',action='store_true')
    a=p.parse_args();pack=a.pack.resolve();m=json.loads((pack/'manifest.json').read_text())
    require(set(m['files'])==NAMES,'Liste des fichiers différente du paquet prévu')
    for name,v in m['files'].items():
        require(fingerprint(pack/'PRODOCK'/name)[:2]==(v['bytes'],v['sha256']),'Image altérée : '+name)
    print('Paquet vérifié :',sum(v['bytes'] for v in m['files'].values()),'octets',flush=True)
    if a.check_package:return
    require(os.geteuid()==0,'Le montage de la SD sur ax15 demande sudo ; aucun fichier SD écrit')
    dev=target();print('SD vérifiée :',dev,'USB 11252024,',SECTORS,'secteurs',flush=True)
    # Do not unmount or repurpose a mount opened by another application.
    status=subprocess.run(['findmnt','-rn','-S',str(dev)],capture_output=True,text=True)
    require(status.returncode==1,'La SD est déjà montée ; la démonter avant cette installation')
    mount=Path(tempfile.mkdtemp(prefix='prodock-install-'));mounted=False
    try:
        subprocess.run(['mount','-t','vfat','-o','rw,noatime',str(dev),str(mount)],check=True);mounted=True
        require(not (mount/'PRODOCK').exists() and not (mount/'PRODNEW').exists(),'Dossier déjà présent : aucun remplacement autorisé')
        before=fingerprint(mount/'CONSOLE.TST')
        require(before[0]==262144 and before[2]==0x18210e0c,'Fichier témoin différent de celui lu sous U-Boot')
        staging=mount/'PRODNEW';staging.mkdir()
        for name,v in m['files'].items():
            destination=staging/name
            with (pack/'PRODOCK'/name).open('rb') as source,destination.open('xb') as dest:
                shutil.copyfileobj(source,dest,1024*1024);dest.flush();os.fsync(dest.fileno())
                os.posix_fadvise(dest.fileno(),0,0,os.POSIX_FADV_DONTNEED)
            require(fingerprint(destination)[:2]==(v['bytes'],v['sha256']),'Relecture différente : '+name)
            print('Écrit et relu :',name,flush=True)
        require(fingerprint(mount/'CONSOLE.TST')==before,'Fichier témoin modifié')
        staging.rename(mount/'PRODOCK');os.sync()
    finally:
        if mounted:subprocess.run(['umount',str(mount)],check=True)
        mount.rmdir()
    # Independent remount read-only; neither cache hints nor write completion
    # alone count as verification of the final directory and FAT metadata.
    verify=Path(tempfile.mkdtemp(prefix='prodock-verify-'));mounted=False
    try:
        subprocess.run(['mount','-t','vfat','-o','ro',str(dev),str(verify)],check=True);mounted=True
        for name,v in m['files'].items():
            require(fingerprint(verify/'PRODOCK'/name)[:2]==(v['bytes'],v['sha256']),'Relecture finale différente : '+name)
        require(fingerprint(verify/'CONSOLE.TST')==before,'Fichier témoin final différent')
    finally:
        if mounted:subprocess.run(['umount',str(verify)],check=True)
        verify.rmdir()
    print('PRODOCK_SD_INSTALLED : six images vérifiées, CONSOLE.TST préservé, SD démontée',flush=True)
if __name__=='__main__':main()
