#!/usr/bin/env python3
"""Observe the unsuccessful R1 Linux launch; preserve the CPU execution state."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--inspect-linux-and-resume', action='store_true',
               help='Require known running-kernel fingerprint, read log/UART status, resume Linux')
p.add_argument('--halt-linux', action='store_true',
               help='Verify the known RAM-only R1 Linux and leave it halted for a power-cycle')
p.add_argument('--uart-witness', action='store_true',
               help='Send a bounded UART TX witness while Linux is halted, capture BL616, resume Linux')
p.add_argument('--debugger-help', action='store_true',
               help='Before UART witness, read debugger CLI help using its timed escape sequence')
a = p.parse_args()
if a.debugger_help and not a.uart_witness:
    p.error('--debugger-help requires --uart-witness')
if sum((a.inspect_linux_and_resume, a.halt_linux, a.uart_witness)) > 1:
    p.error('Choose one probe mode')
anchor = ROOT/'TESTS/neo_720p_20261012/n56r1_linux_20261022'
prior = json.loads((anchor/'result.json').read_text())
if (prior['bitstream_sha256'] != '426389b02a4c1c240a28a711546569315e5c4d9478199f12e1e38f46009d3d2d'
        or prior['run_mode'] != 'linux' or prior['passed'] or prior['load_error'] is not None):
    raise ValueError('Expected the completed but unconfirmed R1 launch')
if 'NEO_LAUNCH_BEGIN' not in (anchor/'openocd.log').read_text():
    raise ValueError('CPU launch was not attempted')
out = a.out.resolve()
if any(c in str(out) for c in '{}\\\r\n'):
    raise ValueError('Unsafe output path')
out.mkdir(parents=True, exist_ok=False)
script = out/'probe.tcl'
script.write_text('''riscv expose_csrs 1994,1996,2000
init
set previous [nds.cpu curstate]
if {$previous ne "running" && $previous ne "halted"} {error "Unexpected CPU state"}
echo "BOOT_PREVIOUS_STATE $previous"
halt
set failed [catch {
    foreach name {pc priv satp mstatus mie mtvec mepc mcause mtval sp ra a0 a1 a2 a3 a4 a5 a6 a7 csr1994 csr1996 csr2000} {
        echo "BOOT_REGISTER $name [reg $name]"
    }
    set pc [lindex [reg pc] 2]
    if {[lindex [reg priv] 2] == 3 && [lindex [reg satp] 2] == 0} {
        riscv set_enable_virt2phys off
        echo "BOOT_CODE [read_memory [expr {$pc&0xfffffffc}] 32 8]"
    }
    if {$previous eq "running"} {
        for {set sample 0} {$sample < 5} {incr sample} {
            resume
            sleep 50
            halt
            echo "BOOT_PC $sample [reg pc] [reg priv]"
        }
    }
} reason]
if {$previous eq "running"} {resume}
if {$failed} {error $reason}
echo BOOT_OBSERVATION_COMPLETE
shutdown
''')
if a.inspect_linux_and_resume or a.halt_linux:
    kernel = ROOT/'linux/build-neo/kernel/arch/riscv/boot/Image'
    manifest = json.loads((ROOT/'linux/build-neo/manifest.json').read_text())
    image_hash = hashlib.sha256(kernel.read_bytes()).hexdigest()
    if image_hash not in json.dumps(manifest):
        raise ValueError('Kernel image not in current package manifest')
    symbols = {line.split()[2]:int(line.split()[0],16) for line in
               (ROOT/'linux/build-neo/kernel/System.map').read_text().splitlines() if len(line.split()) == 3}
    phys = lambda name: symbols[name]-0xc0000000+0x08000000
    if symbols['arch_cpu_idle'] != 0xc01927fe:
        raise ValueError('Not the identified kernel idle function')
    code = int.from_bytes(kernel.read_bytes()[0x192802:0x192806], 'little')
    if code != 0x10500073:
        raise ValueError('Kernel idle instruction differs')
    script.write_text('''init
halt
echo "LINUX_CONTEXT [reg pc] [reg priv] [reg satp]"
if {[lindex [reg satp] 2] == 0} {error "Expected Linux address space"}
riscv set_enable_virt2phys off
if {[lindex [read_memory 0x08192802 16 1] 0] != 0x0073 || [lindex [read_memory 0x08192804 16 1] 0] != 0x1050 || [lindex [read_memory 0x0947d028 32 1] 0] != 3} {error "Running kernel fingerprint differs"}
''' + f'''echo "LINUX_STATE [read_memory {phys('system_state'):#x} 32 1]"
echo "LINUX_JIFFIES [read_memory {phys('jiffies'):#x} 32 2]"
echo "LINUX_LOG_POINTER [read_memory {phys('log_buf'):#x} 32 1]"
echo "LINUX_LOG_LENGTH [read_memory {phys('log_buf_len'):#x} 32 1]"
dump_image {{{out/'kernel_log.bin'}}} {phys('__log_buf'):#x} 32768
''' + '''echo "UART_LCR [read_memory 0xf030002c 32 1]"
echo "UART_LSR [read_memory 0xf0300034 32 1]"
resume
echo LINUX_RESUMED
echo BOOT_OBSERVATION_COMPLETE
shutdown
''')
    if a.halt_linux:
        code = script.read_text()
        if code.count('resume\necho LINUX_RESUMED\n') != 1:
            raise ValueError('Unexpected Linux observation script')
        script.write_text(code.replace('resume\necho LINUX_RESUMED\n',
            'echo "LINUX_HALTED_PC [reg pc]"\necho LINUX_LEFT_HALTED\n'))
if a.uart_witness:
    witness = b'NEO_UART_WITNESS\r\n'
    script.write_text('''init
halt
set failed [catch {
    echo "UART_WITNESS_CONTEXT [reg pc] [reg priv] [reg satp]"
    if {[lindex [reg satp] 2] == 0} {error "Expected Linux address space"}
    riscv set_enable_virt2phys off
    if {[lindex [read_memory 0x08192802 16 1] 0] != 0x0073 || [lindex [read_memory 0x08192804 16 1] 0] != 0x1050 || [lindex [read_memory 0x0947d028 32 1] 0] != 3} {error "Running Linux fingerprint differs"}
    set lcr [lindex [read_memory 0xf030002c 32 1] 0]
    if {($lcr & 0x8f) != 3} {error "UART not in 8-bit TX register mode"}
    echo "UART_WITNESS_PC [reg pc]"
    echo "UART_WITNESS_LCR $lcr"
''' + '    foreach byte {'+' '.join(map(str,witness))+'''} {
        if {([lindex [read_memory 0xf0300034 32 1] 0]&0x60) != 0x60} {error "UART TX not idle"}
        write_memory 0xf0300020 32 [list $byte]
        sleep 20
    }
} reason]
resume
echo LINUX_RESUMED
if {$failed} {error $reason}
echo BOOT_OBSERVATION_COMPLETE
shutdown
''')
error = None
captured = bytearray()
with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    port = None
    stop = threading.Event()
    reader = None
    try:
        if a.uart_witness:
            sys.path.insert(0, str(ROOT/'tools/neo'))
            from console import UART, select_relay
            import serial
            port = serial.Serial(UART, 2000000, timeout=.1, exclusive=True)
            if a.debugger_help:
                help_data=bytearray()
                def receive_help(seconds):
                    end=time.monotonic()+seconds
                    while time.monotonic()<end: help_data.extend(port.read(4096))
                port.baudrate=115200
                receive_help(.2)
                port.write(b'\x18'); time.sleep(.2)
                port.write(b'\x03'); time.sleep(.2)
                port.write(b'\r\n'); receive_help(1.2)
                if b'TangConsole' not in help_data or b'/>' not in help_data:
                    raise RuntimeError('Debugger CLI did not acknowledge escape')
                port.write(b'help\r\n'); receive_help(1)
                (out/'debugger_help.log').write_bytes(help_data)
            (out/'relay.log').write_bytes(select_relay(port, 2000000))
            def read_serial():
                with (out/'uart.log').open('wb', buffering=0) as log:
                    while not stop.is_set():
                        chunk=port.read(4096)
                        captured.extend(chunk)
                        log.write(chunk)
            reader=threading.Thread(target=read_serial)
            reader.start()
        with (out/'openocd.log').open('w') as log:
            subprocess.run(['/usr/local/bin/openocd', '-f', str(ROOT/'tools/neo/ae350_espprog.cfg'),
                '-c', 'gdb_port disabled; tcl_port disabled; telnet_port disabled', '-f', str(script)],
                stdout=log, stderr=log, check=True, timeout=30)
        if a.uart_witness:
            time.sleep(.5)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        error = str(e)
    finally:
        stop.set()
        if reader: reader.join(2)
        if port: port.close()
raw = (out/'openocd.log').read_text()
report = dict(complete=error is None and 'BOOT_OBSERVATION_COMPLETE' in raw,
    bitstream_sha256=prior['bitstream_sha256'], error=error,
    script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
    probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    prior_result_sha256=hashlib.sha256((anchor/'result.json').read_bytes()).hexdigest(),
    sd_written=False, flash_written=False, registers_modified=False)
report['linux_resume_requested'] = a.inspect_linux_and_resume
report['linux_resumed'] = 'LINUX_RESUMED' in raw
report['linux_left_halted'] = 'LINUX_LEFT_HALTED' in raw
if a.uart_witness:
    report['uart_witness_received'] = witness in captured
    report['uart_bytes'] = len(captured)
    report['uart_hex'] = captured.hex()
    print(json.dumps({k:report[k] for k in ('uart_witness_received','uart_bytes','uart_hex')}))
if (out/'kernel_log.bin').exists():
    data = (out/'kernel_log.bin').read_bytes()
    report['kernel_log_sha256'] = hashlib.sha256(data).hexdigest()
    import re
    (out/'kernel_strings.txt').write_text('\n'.join(
        x.decode(errors='replace') for x in re.findall(rb'[\x20-\x7e\t]{8,}', data))+'\n')
(out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
print(raw)
if not report['complete']:
    raise SystemExit('Boot observation incomplete; inspect saved evidence and CPU state')
