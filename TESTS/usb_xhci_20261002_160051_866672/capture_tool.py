#!/usr/bin/env python3
"""Capture bornée xHCI + échos CDC + diagnostic FPGA, à lancer avec sudo.

Exemple, depuis le dossier de validation sur ax15, console au repos :
  sudo /usr/bin/python3 tools/check_usb_xhci.py

Seule la console 359f:2011 / 11252024 est testée. Le parent privilégié crée
une instance tracefs privée, puis lance les échos sous SUDO_UID/SUDO_GID.
Il ne modifie ni la configuration globale de ftrace, ni les modules, ni les
pilotes USB, ni la carte. Les fichiers sont rendus à l'utilisateur à la fin.
Les formats du noyau présent sont archivés et contrôlés avant les filtres.

Références primaires (Linux v6.17, à confronter aux formats locaux archivés) :
https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/usb/host/xhci-trace.h
https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/usb/host/xhci.h
https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/usb/host/xhci-debugfs.c
https://docs.kernel.org/trace/events.html
https://docs.kernel.org/trace/ftrace.html#instances
"""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import pwd
import re
import select
import signal
import subprocess
import sys
import threading
import time
import uuid


IDENTITY = ('359f', '2011', '11252024')
SOURCES = [
    'https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/usb/host/xhci-trace.h',
    'https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/usb/host/xhci.h',
    'https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/usb/host/xhci-debugfs.c',
    'https://docs.kernel.org/trace/events.html',
    'https://docs.kernel.org/trace/ftrace.html#instances',
]


def identify():
    found = []
    for path in Path('/sys/bus/usb/devices').iterdir():
        if not re.fullmatch(r'\d+-\d+(?:\.\d+)*', path.name):
            continue
        try:
            identity = tuple((path / key).read_text().strip()
                             for key in ('idVendor', 'idProduct', 'serial'))
            if identity == IDENTITY:
                found.append(dict(topology=path.name, sysfs=str(path),
                                  bus=int((path/'busnum').read_text()),
                                  address=int((path/'devnum').read_text()),
                                  speed=(path/'speed').read_text().strip(),
                                  vid=identity[0], pid=identity[1], serial=identity[2]))
        except OSError:
            pass
    if len(found) != 1:
        raise RuntimeError(f'Une seule console {IDENTITY} attendue, trouvé : {len(found)}')
    return found[0]


def fields_in_format(text):
    fields = set()
    for declaration in re.findall(r'field:([^;]+);', text):
        match = re.search(r'([A-Za-z_]\w*)(?:\[[^]]*\])?\s*$', declaration)
        if match:
            fields.add(match[1])
    return fields


def event_filter(name, fields, topology, slot):
    """N'utilise que les champs réellement présents dans event/format.

    Les comparaisons de bornes évitent une expression shift/mask non prise en
    charge par certains parseurs ftrace. field3[31:24] est le slot, xhci.h.
    TYPE_COMMAND vaut 5 dans enum xhci_ring_type, distinct du type TRB 14.
    """
    if name.startswith('xhci_urb_'):
        if 'devname' not in fields:
            raise RuntimeError(f'{name}: champ devname absent, filtrage ciblé impossible')
        if not re.fullmatch(r'\d+-\d+(?:\.\d+)*', topology):
            raise ValueError('Topologie USB invalide')
        return f'devname == "{topology}"'
    if name in ('xhci_handle_transfer', 'xhci_queue_trb'):
        required = {'field3'} | ({'type'} if name == 'xhci_queue_trb' else set())
        if not required <= fields:
            raise RuntimeError(f'{name}: champs TRB attendus absents : {required-fields}')
        terms = ['type == 5'] if name == 'xhci_queue_trb' else []
        if slot is not None:
            if not 1 <= slot <= 255:
                raise ValueError('Slot xHCI hors intervalle')
            terms += [f'field3 >= {slot << 24}', f'field3 <= {((slot+1) << 24)-1}']
        return ' && '.join(terms) or '0'
    # Les deux événements reset ci-dessous n'exposent ni slot ni devname.
    return '0'


def slot_mapping(topology):
    found = []
    for path in Path('/sys/kernel/debug/usb/xhci').glob('*/devices/*/name'):
        try:
            if path.read_text().strip() == topology:
                found.append(dict(slot=int(path.parent.name, 10),
                                  controller=path.parents[2].name, name_file=str(path)))
        except (OSError, ValueError):
            continue
    if len(found) > 1:
        raise RuntimeError('Plusieurs slots debugfs correspondent à la console')
    return found[0] if found else None


def usbmon_matches(line, bus, address):
    columns = line.split()
    if len(columns) < 4:
        return False
    endpoint = columns[3].split(':')
    try:
        return len(endpoint) == 4 and int(endpoint[1]) == bus and int(endpoint[2]) == address
    except ValueError:
        return False


class CaptureReader:
    """Lecture non bloquante ; garde les lignes coupées entre deux read()."""
    def __init__(self, source, destination, stop, accept=None, limit=16*1024*1024):
        self.fd = os.open(source, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        try:
            self.stream = destination.open('xb')
        except BaseException:
            os.close(self.fd)
            raise
        self.stop = stop
        self.accept = accept
        self.limit = limit
        self.written = 0
        self.truncated = False
        self.error = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def emit(self, line):
        if self.accept is not None and not self.accept(line.decode(errors='replace')):
            return
        if self.written + len(line) > self.limit:
            self.truncated = True
            self.stop.set()
            return
        self.stream.write(line)
        self.written += len(line)

    def run(self):
        partial = b''
        drain_until = None
        try:
            while True:
                if self.stop.is_set():
                    if drain_until is None:
                        drain_until = time.monotonic()+.2
                    if time.monotonic() >= drain_until:
                        break
                readable, _, _ = select.select([self.fd], [], [], .1)
                if not readable:
                    if self.stop.is_set():
                        break
                    continue
                try:
                    block = os.read(self.fd, 65536)
                except BlockingIOError:
                    if self.stop.is_set():
                        break
                    continue
                if not block:
                    break
                partial += block
                lines = partial.split(b'\n')
                partial = lines.pop()
                for line in lines:
                    self.emit(line+b'\n')
                if self.truncated:
                    break
            if partial:
                self.emit(partial)
        except BaseException as error:
            self.error = str(error)
            self.stop.set()
        finally:
            self.stream.flush()
            self.stream.close()
            os.close(self.fd)


def echo_worker(args):
    """Seul ce processus non privilégié ouvre le CDC et les contrôles USB."""
    if os.geteuid() == 0:
        raise RuntimeError('Le processus écho refuse de fonctionner sous root')
    import serial
    from serial.tools import list_ports
    from usb_control_probe import control

    device = identify()
    ports = [p for p in list_ports.comports()
             if (p.vid, p.pid, p.serial_number) == (0x359f, 0x2011, '11252024')]
    if len(ports) != 1 or device['topology'] != args.device:
        raise RuntimeError('Console différente ou port CDC ambigu')
    result = dict(status='running', device=device, uid=os.geteuid(), samples=[],
                  started_monotonic_ns=time.monotonic_ns(), started_wall_ns=time.time_ns())
    deadline = time.monotonic() + args.seconds
    args.out.mkdir(mode=0o750, exist_ok=False)
    node = '/dev/bus/usb/%03d/%03d' % (device['bus'], device['address'])
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)

    def read_window(dev, end):
        data = bytearray()
        while time.monotonic() < end:
            data.extend(dev.read(min(4096, dev.in_waiting) or 1))
        return data

    try:
        with serial.Serial(ports[0].device, 115200, timeout=.01,
                           write_timeout=1, exclusive=True) as dev:
            if read_window(dev, time.monotonic()+.15):
                raise RuntimeError('Données déjà reçues : arrêter l’animation avant ce diagnostic')
            for index in range(args.rounds):
                if time.monotonic() >= deadline:
                    result['status'] = 'bounded_pass'
                    break
                value = bytes([(index*73+17) & 255])
                sample = dict(index=index, expected=value.hex(), start_monotonic_ns=time.monotonic_ns())
                dev.write(b'E\x01\x00'+value)
                got = bytearray()
                until = min(deadline, time.monotonic()+1)
                while not got and time.monotonic() < until:
                    got.extend(dev.read(1))
                sample['first_read_monotonic_ns'] = time.monotonic_ns()
                got.extend(read_window(dev, min(deadline, time.monotonic()+.01)))
                sample.update(received=got.hex(), end_monotonic_ns=time.monotonic_ns())
                result['samples'].append(sample)
                print(json.dumps(sample), flush=True)
                if got != value:
                    got.extend(read_window(dev, min(deadline, time.monotonic()+1)))
                    sample['received_after_grace'] = got.hex()
                    result['status'] = 'late' if got == value else 'mismatch'
                    break
            else:
                result['status'] = 'pass'
            # Same CDC descriptor stays open. The private reads are AFTER the
            # echo sequence; their endpoint changes cannot precede its fault.
            result['diagnostic_start_monotonic_ns'] = time.monotonic_ns()
            trace = io.StringIO()
            try:
                with open(node, 'r+b', buffering=0) as fd, contextlib.redirect_stdout(trace):
                    control(fd, True, True)
                    control(fd, True, False)
            except Exception as error:
                result['diagnostic_error'] = str(error)
            (args.out/'fpga.txt').write_text(trace.getvalue())
    except KeyboardInterrupt:
        result['status'] = 'interrupted'
    except Exception as error:
        result.update(status='error', error=str(error))
    finally:
        result['ended_monotonic_ns'] = time.monotonic_ns()
        (args.out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    return 0 if result['status'] in ('pass', 'bounded_pass') else 1


def root_capture(args):
    if os.geteuid() != 0:
        raise RuntimeError('Lancer avec sudo : une instance tracefs exige les droits administrateur')
    try:
        uid, gid = int(os.environ['SUDO_UID']), int(os.environ['SUDO_GID'])
        account = pwd.getpwuid(uid)
    except (KeyError, ValueError) as error:
        raise RuntimeError('SUDO_UID/SUDO_GID requis : lancer depuis le compte utilisateur avec sudo') from error
    if uid == 0:
        raise RuntimeError('Le compte des échos doit être non privilégié')
    trace_root = next((p for p in (Path('/sys/kernel/tracing'), Path('/sys/kernel/debug/tracing'))
                       if (p/'instances').is_dir()), None)
    if trace_root is None:
        raise RuntimeError('tracefs avec instances absent ; aucun montage/global modifié par cet outil')
    device = identify()
    mapping = slot_mapping(device['topology'])
    slot = mapping['slot'] if mapping else None
    # Reject other CDC readers before changing tracing. No owner is terminated.
    sysfs = Path(device['sysfs'])
    ports = list(sysfs.glob('*/tty/ttyACM*'))
    if len(ports) != 1:
        raise RuntimeError('Un seul ttyACM de la console attendu')
    owner = subprocess.run(['fuser', '/dev/'+ports[0].name], capture_output=True, text=True)
    if owner.returncode != 1 or owner.stdout.strip() or owner.stderr.strip():
        raise RuntimeError(f'Port CDC occupé ou impossible à vérifier : {owner.stdout} {owner.stderr}')

    args.out.mkdir(mode=0o750, parents=False, exist_ok=False)
    os.chown(args.out, uid, gid)
    instance = trace_root/'instances'/('console_usb_'+str(os.getpid())+'_'+uuid.uuid4().hex[:10])
    report = dict(status='preparing', device=device, slot_mapping=mapping,
                  instance=str(instance), kernel=os.uname().release, uid=uid, gid=gid,
                  started_wall_ns=time.time_ns(), started_monotonic_ns=time.monotonic_ns(),
                  seconds_limit=args.seconds, events={}, cleanup_errors=[], sources=SOURCES,
                  limits=[
                      'Pas de capture des PID électriques USB ; trace FPGA = UTMI.',
                      'Les événements TRB ne contiennent pas le contrôleur PCI ; un slot identique sur un autre contrôleur reste possible.',
                      'Les événements reset-context/debug ne permettent pas un filtre par périphérique.',
                      'xhci_urb_giveback expose status dans format mais ne l’imprime pas dans TP_printk v6.17 ; USBmon ajoute les statuts URB si disponible.',
                      'Une corrélation reset/erreur ne prouve pas la cause initiale du défaut PHY.',
                  ])
    if slot is None:
        report['limits'].append('Slot debugfs absent : les TRB sont capturés pour tous les slots ; URB et USBmon restent ciblés.')
    stop = threading.Event()
    readers = []
    enabled = []
    child = None
    child_log = None
    created = False
    old_handlers = {}
    def interrupt(signum, _frame):
        report['signal'] = signum
        stop.set()
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            old_handlers[sig] = signal.signal(sig, interrupt)
        instance.mkdir()
        created = True
        (instance/'tracing_on').write_text('0')
        clocks = (instance/'trace_clock').read_text().replace('[', '').replace(']', '').split()
        if 'mono' not in clocks:
            raise RuntimeError('Horloge tracefs mono absente : corrélation temporelle non garantie')
        (instance/'trace_clock').write_text('mono')
        (instance/'buffer_size_kb').write_text('256')
        required = ('xhci_handle_transfer', 'xhci_queue_trb', 'xhci_urb_enqueue', 'xhci_urb_giveback')
        optional = ('xhci_urb_dequeue', 'xhci_handle_cmd_reset_ep', 'xhci_dbg_reset_ep')
        for name in required + optional:
            path = instance/'events/xhci-hcd'/name
            if not (path/'format').exists():
                if name in required:
                    raise RuntimeError(f'Événement obligatoire absent : xhci-hcd/{name}')
                report['events'][name] = dict(available=False)
                continue
            fmt = (path/'format').read_text()
            (args.out/(name+'.format')).write_text(fmt)
            fields = fields_in_format(fmt)
            expression = event_filter(name, fields, device['topology'], slot)
            (path/'filter').write_text(expression)
            accepted = (path/'filter').read_text().strip()
            report['events'][name] = dict(available=True, fields=sorted(fields),
                                           filter=expression, accepted_filter=accepted)
            (path/'enable').write_text('1')
            enabled.append(path)
        readers.append(CaptureReader(instance/'trace_pipe', args.out/'xhci.trace', stop))
        mon = Path(f"/sys/kernel/debug/usb/usbmon/{device['bus']}u")
        if mon.exists():
            readers.append(CaptureReader(mon, args.out/'usbmon.trace', stop,
                           lambda line: usbmon_matches(line, device['bus'], device['address'])))
            report['usbmon'] = dict(source=str(mon), bus=device['bus'], address=device['address'])
        else:
            report['usbmon'] = dict(unavailable=True, source=str(mon))
        for reader in readers:
            reader.thread.start()
        (instance/'tracing_on').write_text('1')
        (instance/'trace_marker').write_text(f"console_start monotonic_ns={time.monotonic_ns()} wall_ns={time.time_ns()}")
        command = [sys.executable, str(Path(__file__).resolve()), '--echo-worker',
                   '--device', device['topology'], '--out', str(args.out/'echo'),
                   '--seconds', str(max(1, args.seconds-5)), '--rounds', str(args.rounds)]
        report['command'] = command
        child_log = (args.out/'echo.log').open('x')
        child = subprocess.Popen(command, stdout=child_log, stderr=subprocess.STDOUT,
                                 user=uid, group=gid, extra_groups=os.getgrouplist(account.pw_name, gid),
                                 start_new_session=True, close_fds=True)
        report.update(status='capturing', child_pid=child.pid)
        deadline = time.monotonic()+args.seconds
        while child.poll() is None and not stop.wait(.1):
            if time.monotonic() >= deadline:
                report['status'] = 'time_limit'
                break
            try:
                if int((sysfs/'devnum').read_text()) != device['address']:
                    raise RuntimeError('Adresse USB modifiée')
            except (OSError, ValueError, RuntimeError) as error:
                report.update(status='device_changed', error=str(error))
                break
        if report['status'] == 'capturing':
            report['status'] = 'completed' if child.poll() is not None else 'interrupted'
    except Exception as error:
        report.update(status='error', error=str(error))
    finally:
        if child is not None:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    try:
                        child.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        report['cleanup_errors'].append(
                            'Processus écho encore présent après SIGKILL ; arrêt du traçage poursuivi')
            report['child_returncode'] = child.returncode
        if child_log is not None:
            child_log.close()
        if created:
            try:
                (instance/'trace_marker').write_text(f'console_end monotonic_ns={time.monotonic_ns()}')
                (instance/'tracing_on').write_text('0')
            except OSError as error:
                report['cleanup_errors'].append(str(error))
        stop.set()
        for reader in readers:
            if reader.thread.ident is None:
                reader.stream.close()
                os.close(reader.fd)
            else:
                reader.thread.join(timeout=2)
                if reader.thread.is_alive():
                    report['cleanup_errors'].append('Lecteur trace non arrêté après deux secondes')
            report.setdefault('readers', []).append(dict(bytes=reader.written, truncated=reader.truncated, error=reader.error))
        if created:
            report['cpu_stats'] = {}
            for stats in (instance/'per_cpu').glob('cpu*/stats'):
                try:
                    report['cpu_stats'][stats.parent.name] = stats.read_text()
                except OSError as error:
                    report['cleanup_errors'].append(str(error))
            for path in enabled:
                try:
                    (path/'enable').write_text('0')
                except OSError as error:
                    report['cleanup_errors'].append(str(error))
            try:
                instance.rmdir()  # tracefs retire uniquement notre instance.
            except OSError as error:
                report['cleanup_errors'].append(str(error))
        report['ended_monotonic_ns'] = time.monotonic_ns()
        with (args.out/'capture.json').open('x') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')
        # Le sous-processus est terminé ; ne jamais suivre de lien symbolique.
        for directory, subdirs, filenames in os.walk(args.out, followlinks=False):
            os.chown(directory, uid, gid, follow_symlinks=False)
            for name in subdirs + filenames:
                os.chown(Path(directory)/name, uid, gid, follow_symlinks=False)
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
    print(json.dumps(dict(status=report['status'], output=str(args.out),
                          child_returncode=report.get('child_returncode'),
                          cleanup_errors=report['cleanup_errors']), indent=2))
    return int(report['status'] != 'completed' or report.get('child_returncode') != 0 or bool(report['cleanup_errors']))


def self_test():
    fmt = ('field:unsigned short common_type; offset:0; size:2; signed:0;\n'
           'field:__data_loc char[] devname; offset:8; size:4; signed:0;\n'
           'field:u32 field3; offset:12; size:4; signed:0;\n'
           'field:u32 type; offset:16; size:4; signed:0;\n')
    fields = fields_in_format(fmt)
    assert fields == {'common_type', 'devname', 'field3', 'type'}
    assert event_filter('xhci_urb_giveback', fields, '3-7', 5) == 'devname == "3-7"'
    assert event_filter('xhci_queue_trb', fields, '3-7', 5) == 'type == 5 && field3 >= 83886080 && field3 <= 100663295'
    assert event_filter('xhci_handle_transfer', fields, '3-7', None) == '0'
    try:
        event_filter('xhci_handle_transfer', set(), '3-7', 5)
    except RuntimeError:
        pass
    else:
        raise AssertionError('Champ inconnu accepté')
    assert usbmon_matches('ffff 123 C Bi:3:066:2 -71 0', 3, 66)
    assert not usbmon_matches('ffff 123 C Bi:3:067:2 -71 0', 3, 66)
    assert not usbmon_matches('ligne tronquée', 3, 66)
    print('PASS : formats/filtres vérifiés, sélection USBmon bus/adresse, aucun accès matériel')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--rounds', type=int, default=1000)
    parser.add_argument('--self-test', action='store_true', help='vérifications sans root, tracefs ou USB')
    parser.add_argument('--echo-worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--device', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.out is None:
        name = 'usb_xhci_'+time.strftime('%Y%m%d_%H%M%S')+'_'+str(os.getpid())
        args.out = Path(__file__).resolve().parents[1]/'TESTS'/name
    if not 1 <= args.seconds <= 30 or not 1 <= args.rounds <= 10000:
        parser.error('--seconds doit être entre 1 et 30, --rounds entre 1 et 10000')
    args.out = args.out.resolve()
    try:
        return echo_worker(args) if args.echo_worker else root_capture(args)
    except (RuntimeError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
