"""Pure identity and launch policy for a persistent, already-tested Festival.

No hardware access. A new live GM1 identity comes only from the successful
six-window result, never from the historical PID3158 after restoration.
"""
import hashlib
import json
from pathlib import Path
import re
import time

MEASURE_SHA = '7afae5c49aec9dcaed001f7eafdcfb878f62b66e7437c81b38e47dda4e4cfdfc'
TARGET = dict(bytes=16640496, sha256='6b8d3eeb273e03be38eb73a2ff6fee60dad16678316bfdacb52b4db308fec3f7', crc32='fa358bf4')
BASE = dict(bytes=10052024, sha256='df529a3463d6f3138895eeefb6ac70d149d7a714f51be74fb79a73079054e29b', crc32='e4089d74')
HELPER = dict(bytes=221180, sha256='7cc3e1766d15cb47ac98ab4a6ab33540b5a281c9715afc760c68ab0af03effaf', crc32='fa6b4b5b')
SAVE_SHA = '2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6'
FPGA_SHA = 'fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f'
HOST = 'michael-AX15'
PORT = '/dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00'
KERNEL = '6.12.112-prodock-luma3d-g3d1-r1'
PROGRAM = 'luma3d-fm4a'
TAG = 'fm4live1'
ARGS = ['--festival', '--festival-save', '/tmp/fm4live1.festival.save', '--memory-save', '/tmp/fm4live1.memory.save']


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def anchor(value):
    need(isinstance(value, dict) and set(value) == {'pid', 'start_ticks'}, 'Invalid identity fields')
    need(type(value['pid']) is int and value['pid'] > 1 and type(value['start_ticks']) is int and value['start_ticks'] > 0, 'Invalid process identity')
    return value.copy()


def measurement_proof(result):
    need(result.get('passed') is True and result.get('hardware') is True and result.get('manifest_sha256') == MEASURE_SHA, 'Six windows not qualified')
    need(result.get('restored_gm1') is True and result.get('functional_passed') is True, 'Baseline restoration not established')
    need(not any(k in result for k in ('error', 'cleanup_error', 'receiver_abort_error')), 'Unresolved measurement failure')
    windows = result.get('windows', [])
    need([x['window']['mode'] for x in windows] == [0, 1, 2, 3, 5, 4], 'Incomplete six-window coverage')
    for row in windows:
        need(row['measurement']['hardware'] is True and row['measurement']['mode'] == row['window']['mode'], 'Window identity differs')
        need(all(row['display'].get(k) == 0 for k in ('errors', 'uf', 'invalid', 'fault')), 'Window GPU fault')
    recovery = result['recovery']
    need(recovery['save']['sha256'] == SAVE_SHA, 'Protected campaign changed')
    return anchor(recovery['identity'])


def octets(raw):
    data = bytearray()
    end = None
    for line in raw.replace(b'\r', b'').splitlines():
        if re.fullmatch(rb'[0-7]{7,}(?: +[0-7]{3}){1,16}', line):
            words = line.split()
            need(end is None and int(words[0], 8) == len(data), 'Discontinuous argv dump')
            data.extend(int(x, 8) for x in words[1:])
            need(len(data) <= 1024, 'Oversized argv')
        elif re.fullmatch(rb'[0-7]{7,}', line):
            need(end is None, 'Duplicate argv end')
            end = int(line, 8)
    need(end == len(data), 'Incomplete argv dump')
    return bytes(data)


def parse_identity(raw, program, argv):
    need(re.fullmatch(r'[A-Za-z0-9_.-]+', program), 'Unsafe process name')
    rows = re.findall(rb'^(\d+) \(' + program.encode() + rb'\) ([^\r\n]+)', raw, re.M)
    need(len(rows) == 1, 'Missing/duplicate process stat')
    pid, fields = int(rows[0][0]), rows[0][1].split()
    need(len(fields) >= 20 and fields[0] not in (b'Z', b'X'), 'Process is not alive')
    expected = ('\0'.join(['/tmp/' + program, *argv]) + '\0').encode()
    need(octets(raw) == expected, 'Unexpected complete argv')
    need(re.search(rb'^l[^\r\n]* /proc/' + str(pid).encode() + rb'/exe -> /tmp/' + program.encode() + rb'\r?$', raw, re.M), 'Unexpected executable link')
    return anchor(dict(pid=pid, start_ticks=int(fields[19])))


def term_command(identity, program, pidfile):
    a = anchor(identity)
    need(re.fullmatch(r'[A-Za-z0-9_.-]+', program) and re.fullmatch(r'/tmp/[A-Za-z0-9_.-]+', pidfile), 'Unsafe stop target')
    pid, ticks = a['pid'], a['start_ticks']
    return (f'test -f {pidfile} && test ! -L {pidfile} && test "`cat {pidfile}`" = {pid} && set -- `cat /proc/{pid}/stat`'
            f' && test "$1" = {pid} && test "$2" = "({program})" && test "$3" != Z && test "$3" != X'
            f' && shift 21 && test "$1" = {ticks} && kill -TERM {pid} && sleep 1')


def launch_command(program, tag, args):
    need(re.fullmatch(r'[A-Za-z0-9_.-]+', program) and re.fullmatch(r'[a-z0-9_]+', tag), 'Unsafe launch identifier')
    need(all(re.fullmatch(r'[A-Za-z0-9_./-]+', arg) for arg in args), 'Unsafe argv')
    # /dev/null prevents an unattended demo from filling tmpfs with perf logs.
    # The supervising shell retains only the PID and eventual exit code.
    return (f'( /tmp/{program} {" ".join(args)} < /dev/null > /dev/null 2>&1 & p=$!;'
            f' printf "%s\\n" "$p" > /tmp/{tag}.pid.tmp && mv /tmp/{tag}.pid.tmp /tmp/{tag}.pid;'
            f' wait "$p"; rc=$?; printf "%s\\n" "$rc" > /tmp/{tag}.exit ) < /dev/null > /dev/null 2>&1 & echo LIVE_LAUNCHED')


def review_check(review, manifest_sha, proof_sha, current_anchor, host, now=None, restore=False):
    now = time.time() if now is None else now
    need(host == HOST and review.get('host') == HOST and review.get('port') == PORT, 'Wrong board host/port')
    need(review.get('manifest_sha256') == manifest_sha and review.get('proof_sha256') == proof_sha and review.get('expected_identity') == current_anchor, 'Review identity mismatch')
    need(review.get('fpga_sha256') == FPGA_SHA and review.get('save_sha256') == SAVE_SHA, 'Reference changed')
    for key in ('same_g22r0_since_measurement', 'same_helper_and_elf_since_measurement', 'ordinary_shell_confirmed', 'no_other_console_session'):
        need(review.get(key) is True, 'Missing continuity review: ' + key)
    need(review.get('root_authorized_restore' if restore else 'root_authorized_leave_demo_running') is True, 'Persistent action not authorized')
    need(type(review.get('reviewed_unix')) in (int, float) and 0 <= now-review['reviewed_unix'] <= 1800, 'Review expired')
