#!/usr/bin/env python3
"""Read Neo USB status and its passive trace while the CPU remains parked."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/neo'))
from load_linux import recovery_commands

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--anchor', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
guard = recovery_commands(a.anchor)[:-3]
out = a.out.resolve()
if any(c in str(out) for c in '{}\\\r\n'):
    raise SystemExit('Unsafe output path')
out.mkdir(exist_ok=False, parents=True)
commands = [*guard,
    'echo USB_PARKED',
    'foreach address {0xe900000c 0xe9000014 0xe9000034 0xe9000044} {',
    '  if {[lindex [read_memory $address 32 1] 0] != 0} {error "Scanout must be disabled"}',
    '}',
    'if {[lindex [read_memory 0xe9003000 32 1] 0] != 0x554d5343} {error "USB MSC identity differs"}',
    'for {set i 0} {$i < 3} {incr i} {',
    '  echo "USB_STATUS $i [read_memory 0xe9003004 32 1]"',
    '  sleep 50',
    '}',
    'set trace_id [lindex [read_memory 0xe9002000 32 1] 0]',
    'echo "USB_TRACE_ID $trace_id"',
    'if {$trace_id == 0x55544e41} {',
    '  if {([lindex [read_memory 0xe9002004 32 1] 0] & 1) != 0} {error "Trace busy at entry"}',
    '  foreach cmd {1 2 4} {',
    '    set expected [expr {([lindex [read_memory 0xe9002008 32 1] 0]+1)&0xffffffff}]',
    '    write_memory 0xe900200c 32 [list $cmd]',
    '    set done 0',
    '    for {set poll 0} {$poll < 100} {incr poll} {',
    '      sleep 2',
    '      if {[lindex [read_memory 0xe9002004 32 1] 0] == 0 && [lindex [read_memory 0xe9002008 32 1] 0] == $expected} {set done 1; break}',
    '    }',
    '    echo "USB_TRACE_ACK $cmd $done"',
    '    if {!$done} {break}',
    '    echo "USB_TRACE_BANK $cmd [read_memory 0xe9002040 32 32]"',
    '    if {$cmd == 1} {sleep 200}',
    '  }',
    '}',
    'echo USB_PROBE_COMPLETE', 'shutdown', '']
script = out / 'probe.tcl'
script.write_text('\n'.join(commands))
error = None
with (ROOT / 'TESTS/neo_board.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with (out / 'openocd.log').open('w') as log:
        try:
            subprocess.run(['/usr/local/bin/openocd', '-f', str(ROOT / 'tools/neo/ae350_espprog.cfg'),
                '-c', 'gdb_port disabled; tcl_port disabled; telnet_port disabled', '-f', str(script)],
                stdout=log, stderr=log, check=True, timeout=20)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            error = str(e)
raw = (out / 'openocd.log').read_text()
report = dict(capture_complete=error is None and 'USB_PROBE_COMPLETE' in raw,
    bitstream_sha256=json.loads((a.anchor / 'result.json').read_text())['bitstream_sha256'],
    scope='USB status and passive trace only, parked CPU; not enumeration qualification',
    status=[int(v, 0) for v in re.findall(r'^USB_STATUS \d+ (\S+)$', raw, re.M)],
    trace_ids=[int(v, 0) for v in re.findall(r'^USB_TRACE_ID (\S+)$', raw, re.M)],
    trace_ack={cmd: bool(int(v)) for cmd, v in re.findall(r'^USB_TRACE_ACK (\d+) ([01])$', raw, re.M)},
    trace_banks={cmd: [int(v, 0) for v in values.split()] for cmd, values in
                 re.findall(r'^USB_TRACE_BANK (\d+) (.+)$', raw, re.M)},
    error=error, cpu_left_halted=True if 'USB_PARKED' in raw else None,
    sd_written=False, flash_written=False, script_sha256=hashlib.sha256(script.read_bytes()).hexdigest())
(out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
if not report['capture_complete']:
    raise SystemExit('Incomplete USB observation; evidence retained')
