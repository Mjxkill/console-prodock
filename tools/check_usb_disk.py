#!/usr/bin/env python3
"""Essai sur carte du disque USB de la console (périphérique composite 359f:2011).

À lancer sur le PC relié à la console, application usb_disk chargée. Trois vues indépendantes :

1. Port série : identité et compteurs du firmware (le port série reste utilisable pendant tout
   l'essai du disque, c'est l'exigence « un disque et un port série »).
2. Noyau Linux : périphérique de blocs créé par usb-storage, taille, nom ; s'il est monté
   (bureau ouvert ou udisksctl), lecture de LISEZMOI.TXT puis écriture et relecture d'un fichier.
3. Hôte Bulk-Only en espace utilisateur (pyusb), pilote noyau détaché de la seule interface
   disque : INQUIRY, capacité, écriture puis relecture d'une zone de 8 Mio avec débits, erreur
   hors capacité, puis CRC32 de la zone calculé par le firmware dans sa mémoire (commande V).

Aucun droit root : l'accès passe par la règle udev de la console. Avec --no-raw ou --no-files,
la vue correspondante est omise. Sans --allow-sd-write, une SD physique est uniquement lue :
pas de montage ni de test de fichiers et deux lectures brutes de 8 Mio. La zone d'écriture
brute (blocs 32768 à 49151) est réservée aux essais en DDR. --allow-sd-write autorise aussi
ces écritures destructives sur SD : uniquement sur une carte d'essai dont les données
peuvent être perdues.
"""
import argparse
import json
import re
import struct
import subprocess
import time
import uuid
import zlib
from pathlib import Path

import serial
import usb.core
import usb.util
from serial.tools import list_ports
from check_gpu_reloads import console_snapshot

VID, PID = 0x359f, 0x2011
TEST_BLOCK, TEST_BLOCKS, CHUNK = 32768, 16384, 128


class Fail(Exception):
    pass


class Report:
    def __init__(self, out):
        self.out = out
        self.lines = []
        self.data = {'pass': False}

    def log(self, text):
        print(text, flush=True)
        self.lines.append(text)

    def save(self):
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / 'usb_disk.log').write_text('\n'.join(self.lines) + '\n')
        (self.out / 'usb_disk.json').write_text(json.dumps(self.data, indent=2) + '\n')


def command(port, text, expect, timeout=3.0):
    """Envoie une commande d'un caractère et renvoie la ligne commençant par `expect`."""
    quiet = time.monotonic() + 5                 # laisse s'écouler un texte en cours d'émission
    while port.read(256) and time.monotonic() < quiet:
        pass
    port.reset_input_buffer()
    port.write(text.encode())
    deadline, buffer = time.monotonic() + timeout, b''
    while time.monotonic() < deadline:
        buffer += port.read(256)
        complete = buffer.decode(errors='replace').split('\n')[:-1]      # lignes terminées seulement
        for line in complete:
            if line.strip('\r').startswith(expect):
                return line.strip('\r')
    raise Fail(f'pas de réponse série à {text!r} : {buffer!r}')


def block_device(dev):
    """Nom du périphérique de blocs que le noyau a créé pour l'interface disque, ou None."""
    for path in Path('/sys/bus/usb/devices').glob('*:1.2'):
        parent = path.resolve().parent
        try:
            if (int((parent / 'busnum').read_text()), int((parent / 'devnum').read_text())) != (dev.bus, dev.address):
                continue
        except OSError:
            continue
        found = sorted(path.glob('host*/target*/*/block/sd*'))
        return found[0].name if found else None
    return None


class Disk:
    """Hôte Bulk-Only minimal sur l'interface 2 (EP1 OUT 0x01, EP1 IN 0x81)."""

    def __init__(self, dev):
        self.dev, self.tag = dev, 0x20260000

    def transfer(self, cb, length=0, data=None, timeout=5000):
        self.tag += 1
        into_host = data is None
        cbw = struct.pack('<IIIBBB', 0x43425355, self.tag, length, 0x80 if into_host else 0, 0, len(cb)) + cb.ljust(16, b'\0')
        if self.dev.write(0x01, cbw, timeout) != 31:
            raise Fail('commande non acceptée')
        received = b''
        if length and into_host:
            while len(received) < length:
                part = bytes(self.dev.read(0x81, length - len(received), timeout))
                received += part
                if len(part) % 512:
                    break
        elif length:
            if self.dev.write(0x01, data, timeout) != length:
                raise Fail('données non acceptées')
        csw = bytes(self.dev.read(0x81, 512, timeout))
        if len(csw) != 13:
            raise Fail(f'état de {len(csw)} octets au lieu de 13')
        signature, tag, residue, status = struct.unpack('<IIIB', csw)
        if signature != 0x53425355 or tag != self.tag:
            raise Fail(f'état invalide : {csw.hex()}')
        return status, residue, received

    def sense(self):
        status, _, data = self.transfer(bytes([0x03, 0, 0, 0, 18, 0]), 18)
        if status or len(data) != 18:
            raise Fail('REQUEST SENSE refusé')
        return data[2] << 16 | data[12] << 8 | data[13]

    def read(self, block, count):
        cb = struct.pack('>BBIBHB', 0x28, 0, block, 0, count, 0)
        status, residue, data = self.transfer(cb, count * 512)
        return status, residue, data

    def write(self, block, payload):
        cb = struct.pack('>BBIBHB', 0x2a, 0, block, 0, len(payload) // 512, 0)
        status, residue, _ = self.transfer(cb, len(payload), payload)
        return status, residue


def pattern(seed):
    """8 Mio pseudo-aléatoires reproductibles."""
    out, value = bytearray(), seed
    words = TEST_BLOCKS * 512 // 4
    for _ in range(words // 4096):
        chunk = []
        for _ in range(4096):
            value = (value * 1664525 + 1013904223) & 0xffffffff
            chunk.append(value)
        out += struct.pack('<4096I', *chunk)
    return bytes(out)


def raw_view(report, dev, port, allow_sd):
    state = command(port, 's', 'USBDISK MEDIA=')
    read_only = 'MEDIA=SD' in state and not allow_sd
    if read_only:
        report.log('Support = carte SD : vue brute en lecture seule (aucune écriture sur la carte)')
    detached = False
    try:
        if dev.is_kernel_driver_active(2):
            dev.detach_kernel_driver(2)
            detached = True
        usb.util.claim_interface(dev, 2)
        disk = Disk(dev)
        status, residue, data = disk.transfer(bytes([0x12, 0, 0, 0, 36, 0]), 36)
        if status or len(data) != 36:
            raise Fail('INQUIRY refusé')
        vendor, product = data[8:16].decode().strip(), data[16:32].decode().strip()
        report.log(f'INQUIRY : « {vendor} » « {product} » amovible={data[1] >> 7}')
        for _ in range(3):                      # UNIT ATTENTION éventuel après changement de support
            status, _, _ = disk.transfer(bytes(6))
            if status == 0:
                break
            report.log(f'TEST UNIT READY refusé, sense {disk.sense():06x}')
        else:
            raise Fail('le disque ne devient pas prêt')
        status, _, data = disk.transfer(bytes([0x25]) + bytes(9), 8)
        last, size = struct.unpack('>II', data)
        blocks = last + 1
        report.log(f'Capacité : {blocks} blocs de {size} octets ({blocks * size / 2**20:.1f} Mio)')
        if status or size != 512 or blocks < TEST_BLOCK + TEST_BLOCKS:
            raise Fail('capacité inattendue')
        if read_only:
            # Deux lectures des 8 premiers Mio : identiques, secteur d'amorce valide, débit.
            passes = []
            for _ in range(2):
                start, data = time.monotonic(), bytearray()
                for offset in range(0, TEST_BLOCKS, CHUNK):
                    status, residue, part = disk.read(offset, CHUNK)
                    if status or residue or len(part) != CHUNK * 512:
                        raise Fail(f'lecture du bloc {offset} : état {status}, résidu {residue}, sense {disk.sense():06x}')
                    data += part
                passes.append((bytes(data), time.monotonic() - start))
            megabytes = TEST_BLOCKS * 512 / 2**20
            report.log(f'Lecture {megabytes:.0f} Mio x 2 : {megabytes / passes[0][1]:.2f} et {megabytes / passes[1][1]:.2f} Mio/s, '
                       f'identiques={passes[0][0] == passes[1][0]}, amorce 55AA={passes[0][0][510:512] == bytes([0x55, 0xaa])}')
            report.data['raw'] = dict(vendor=vendor, product=product, blocks=blocks, read_only=True,
                                      read_mib_s=[megabytes / p[1] for p in passes], crc32=f'{zlib.crc32(passes[0][0]):08x}')
            if passes[0][0] != passes[1][0] or passes[0][0][510:512] != bytes([0x55, 0xaa]):
                raise Fail('lectures brutes de la carte SD incohérentes')
            return
        payload = pattern(int(time.time()) & 0xffffffff)
        start = time.monotonic()
        for offset in range(0, TEST_BLOCKS, CHUNK):
            status, residue = disk.write(TEST_BLOCK + offset, payload[offset * 512:(offset + CHUNK) * 512])
            if status or residue:
                raise Fail(f'écriture du bloc {TEST_BLOCK + offset} : état {status}, résidu {residue}, sense {disk.sense():06x}')
        write_s = time.monotonic() - start
        start, back = time.monotonic(), bytearray()
        for offset in range(0, TEST_BLOCKS, CHUNK):
            status, residue, data = disk.read(TEST_BLOCK + offset, CHUNK)
            if status or residue or len(data) != CHUNK * 512:
                raise Fail(f'lecture du bloc {TEST_BLOCK + offset} : état {status}, résidu {residue}, {len(data)} octets')
            back += data
        read_s = time.monotonic() - start
        megabytes = TEST_BLOCKS * 512 / 2**20
        report.log(f'Écriture {megabytes:.0f} Mio : {megabytes / write_s:.2f} Mio/s ; lecture : {megabytes / read_s:.2f} Mio/s')
        if bytes(back) != payload:
            first = next(i for i in range(len(payload)) if back[i] != payload[i])
            raise Fail(f'relecture différente à l\'octet {first}')
        # Lectures de tailles impaires, à cheval sur la zone.
        for block, count in ((TEST_BLOCK + 1, 1), (TEST_BLOCK + 5, 7), (TEST_BLOCK + 100, 9), (TEST_BLOCK + 1000, 31)):
            status, residue, data = disk.read(block, count)
            if status or data != payload[(block - TEST_BLOCK) * 512:(block - TEST_BLOCK + count) * 512]:
                raise Fail(f'lecture de {count} blocs en {block}')
        status, residue, data = disk.read(blocks - 1, 2)
        code = disk.sense()
        report.log(f'Lecture hors capacité : état {status}, résidu {residue}, sense {code:06x}')
        if status != 1 or residue != 1024 or code != 0x052100:
            raise Fail('erreur hors capacité mal signalée')
        expected = zlib.crc32(payload)
        report.data['raw'] = dict(vendor=vendor, product=product, blocks=blocks, megabytes=megabytes,
                                  write_mib_s=megabytes / write_s, read_mib_s=megabytes / read_s, crc32=f'{expected:08x}')
        if 'MEDIA=DDR' in state:
            line = command(port, 'v', 'USBDISK VERIFY', timeout=20)
            report.log(line)
            if line.split('CRC=')[1].strip().lower() != f'{expected:08x}':
                raise Fail(f'le firmware calcule un autre CRC que le PC ({expected:08x})')
            report.log('CRC32 de la zone identique côté firmware et côté PC')
    finally:
        try:
            usb.util.release_interface(dev, 2)
        except usb.core.USBError:
            pass
        if detached:
            dev.attach_kernel_driver(2)


def file_view(report, dev, wait):
    name = None
    deadline = time.monotonic() + wait
    while name is None and time.monotonic() < deadline:
        name = block_device(dev)
        if name is None:
            time.sleep(0.5)
    if name is None:
        raise Fail('le noyau n\'a créé aucun périphérique de blocs pour le disque')
    sys_block = Path('/sys/block') / name
    for _ in range(40):                          # la taille arrive après READ CAPACITY
        sectors = int((sys_block / 'size').read_text())
        if sectors:
            break
        time.sleep(0.25)
    model = (sys_block / 'device/model').read_text().strip()
    vendor = (sys_block / 'device/vendor').read_text().strip()
    report.log(f'Noyau : /dev/{name} « {vendor} » « {model} », {sectors} secteurs ({sectors * 512 / 2**20:.1f} Mio), amovible={(sys_block / "removable").read_text().strip()}')
    report.data['kernel'] = dict(device=name, vendor=vendor, model=model, sectors=sectors)
    if sectors == 0:
        raise Fail('capacité nulle vue du noyau')

    def mount_point():
        out = subprocess.run(['lsblk', '-no', 'MOUNTPOINT', f'/dev/{name}'], capture_output=True, text=True).stdout.split()
        return Path(out[0]) if out else None

    where = mount_point()
    if where is None:
        result = subprocess.run(['udisksctl', 'mount', '--no-user-interaction', '-b', f'/dev/{name}'], capture_output=True, text=True)
        report.log('udisksctl mount : ' + (result.stdout + result.stderr).strip())
        where = mount_point()
    if where is None:
        report.log('Volume non monté (pas de session de bureau active ni de droit udisks) : vue fichiers omise')
        report.data['files'] = None
        return
    text = (where / 'LISEZMOI.TXT').read_text() if (where / 'LISEZMOI.TXT').exists() else None
    report.log(f'Monté sur {where} ; LISEZMOI.TXT : {text.splitlines()[0] if text else "absent"}')
    payload = pattern(0x51ab1e)[:4 << 20]
    # Ne jamais écraser un fichier préexistant du support, même en mode
    # écriture explicitement autorisé. Nom FAT 8.3 et création exclusive.
    filename = 'T' + uuid.uuid4().hex[:7].upper() + '.BIN'
    target = where / filename
    start = time.monotonic()
    with target.open('xb') as stream:
        stream.write(payload)
    subprocess.run(['sync', '-f', str(target)], check=True)
    write_s = time.monotonic() - start
    # Démonter puis remonter : la relecture vient du disque, pas du cache du PC.
    subprocess.run(['udisksctl', 'unmount', '--no-user-interaction', '-b', f'/dev/{name}'], capture_output=True, text=True)
    remount = subprocess.run(['udisksctl', 'mount', '--no-user-interaction', '-b', f'/dev/{name}'], capture_output=True, text=True)
    where = mount_point()
    if where is None:
        raise Fail('remontage impossible : ' + remount.stderr.strip())
    start = time.monotonic()
    same = (where / filename).read_bytes() == payload
    read_s = time.monotonic() - start
    (where / filename).unlink()
    subprocess.run(['sync', '-f', str(where)], check=True)
    report.log(f'Fichier de 4 Mio : écriture {4 / write_s:.2f} Mio/s, relecture après remontage {4 / read_s:.2f} Mio/s, identique={same}')
    report.data['files'] = dict(mount=str(where), write_mib_s=4 / write_s, read_mib_s=4 / read_s, same=same, readme=text)
    # Toujours démonter : la vue suivante détache le pilote du noyau.
    subprocess.run(['udisksctl', 'unmount', '--no-user-interaction', '-b', f'/dev/{name}'], capture_output=True, text=True)
    if not same:
        raise Fail('fichier relu différent')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--wait', type=float, default=20, help='attente du périphérique de blocs (s)')
    p.add_argument('--no-raw', action='store_true')
    p.add_argument('--no-files', action='store_true')
    p.add_argument('--allow-sd-write', action='store_true')
    a = p.parse_args()
    report = Report(a.out)
    try:
        snapshot = console_snapshot()
        if snapshot is None:
            raise Fail('console 11252024 absente')
        dev = usb.core.find(idVendor=VID, idProduct=PID,
                            bus=snapshot['bus'], address=snapshot['address'])
        if dev is None:
            raise Fail('console 359f:2011 absente')
        config = dev.get_active_configuration()
        classes = [(i.bInterfaceNumber, i.bInterfaceClass, [e.bEndpointAddress for e in i]) for i in config]
        report.log(f'USB {dev.bus}:{dev.address} bcdDevice={dev.bcdDevice:04x} vitesse={dev.speed} interfaces={classes}')
        report.data['usb'] = dict(bcd_device=dev.bcdDevice, speed=dev.speed, interfaces=classes,
                                  snapshot=snapshot)
        if dev.speed != 3:
            raise Fail('la liaison n\'est pas en High Speed')
        if [c[:2] for c in classes] != [(0, 2), (1, 10), (2, 8)]:
            raise Fail('interfaces attendues : CDC, CDC données, stockage de masse')
        ports = [x.device for x in list_ports.comports()
                 if (x.vid, x.pid, x.serial_number) == (VID, PID, '11252024')]
        if len(ports) != 1:
            raise Fail(f'un port série attendu, trouvé {ports}')
        with serial.Serial(ports[0], 115200, timeout=0.05, exclusive=True) as port:
            report.log(command(port, '?', 'USBDISK '))
            initial = command(port, 's', 'USBDISK MEDIA=')
            report.log(initial)
            media = dict(re.findall(r'(\w+)=(\w+)', initial)).get('MEDIA')
            if media not in ('SD', 'DDR'):
                raise Fail('support inconnu : ' + initial)
            if not a.no_files:
                if media == 'SD' and not a.allow_sd_write:
                    report.log('SD en lecture seule : montage et test de fichiers omis')
                    report.data['files'] = dict(skipped='SD read-only')
                else:
                    file_view(report, dev, a.wait)
            if not a.no_raw:
                raw_view(report, dev, port, a.allow_sd_write)
            time.sleep(1.0)
            final = command(port, 's', 'USBDISK MEDIA=')
            report.log(final)
            counters = dict(re.findall(r'(\w+)=(\w+)', final))
            report.data['firmware'] = counters
            if int(counters['TIMEOUTS']) or int(counters['LOSSES']) or int(counters['RESYNCS']):
                raise Fail('le firmware signale des délais, pertes ou resynchronisations')
        report.data['pass'] = True
        report.log('PASS disque USB + port série')
    except (Fail, usb.core.USBError, OSError) as error:
        report.log(f'ÉCHEC : {error}')
        report.data['error'] = str(error)
    report.save()
    raise SystemExit(0 if report.data['pass'] else 1)


if __name__ == '__main__':
    main()
