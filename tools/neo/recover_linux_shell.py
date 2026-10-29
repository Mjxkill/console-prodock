#!/usr/bin/env python3
"""Exit one stuck LA16 BusyBox process before replacing the Neo FPGA.

This one-off diagnostic is restricted to the observed userspace LR/SC loop
and its exact instruction fingerprint. It invokes Linux exit_group through
an existing ECALL instruction; it does not patch memory, SD or flash.
Linux init is expected to respawn the shell. Never use it on a running game.
"""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TCL = '''gdb_port disabled
tcl_port disabled
telnet_port disabled
init
halt
proc register_value {name} {return [lindex [reg $name] 2]}
set observed 0
for {set sample 0} {$sample < 16} {incr sample} {
    set sampled_pc [register_value pc]
    set sampled_priv [register_value priv]
    echo "NEO_RECOVERY_SAMPLE $sample pc=$sampled_pc priv=$sampled_priv"
    if {$sampled_priv == 0 && $sampled_pc >= 0x301ac && $sampled_pc <= 0x301c4} {
        set observed 1
        break
    }
    resume
    sleep 20
    halt
}
set saved_pc [register_value pc]
set saved_a0 [register_value a0]
set saved_a7 [register_value a7]
set modified 0
set failure [catch {
    if {!$observed || [register_value priv] != 0} {error "Not the observed userspace process"}
    if {$saved_pc < 0x301ac || $saved_pc > 0x301c4} {error "Not the observed BusyBox loop"}
    riscv set_enable_virt2phys on
    set code [read_memory 0x301ac 32 7]
    foreach actual $code expected {0x0106a783 0x0117f733 0x1606282f 0x00f81663 0x1ee625af 0xfe059ae3 0xff0794e3} {
        if {$actual != $expected} {error "BusyBox instruction fingerprint mismatch"}
    }
    if {[lindex [read_memory 0x2e5f0 32 1] 0] != 0x73} {error "ECALL instruction mismatch"}
    echo "NEO_STUCK_BUSYBOX pc=$saved_pc code=$code"
    set modified 1
    reg a0 0
    reg a7 94
    reg pc 0x2e5f0
} reason]
if {$failure} {
    if {$modified} {
        reg a0 $saved_a0
        reg a7 $saved_a7
        reg pc $saved_pc
    }
    resume
    echo "NEO_RECOVERY_REFUSED $reason"
} else {
    resume
    echo NEO_BUSYBOX_EXIT_REQUESTED
}
shutdown
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    probes = [p for p in Path('/sys/bus/usb/devices').iterdir()
              if (p / 'product').exists()
              and (p / 'product').read_text().strip() == 'Dual RS232-HS'
              and (p / 'idVendor').read_text().strip() == '0403'
              and (p / 'idProduct').read_text().strip() == '6010']
    if len(probes) != 1:
        raise RuntimeError('Expected exactly one Neo ESP-Prog')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    script = out / 'recover.tcl'
    script.write_text(TCL)
    with (out / 'openocd.log').open('w') as log:
        subprocess.run(['/usr/local/bin/openocd', '-f', str(ROOT / 'tools/neo/ae350_espprog.cfg'),
                        '-f', str(script)], stdout=log, stderr=subprocess.STDOUT,
                       check=True, timeout=30)
    transcript = (out / 'openocd.log').read_text()
    print(transcript)
    if 'NEO_BUSYBOX_EXIT_REQUESTED' not in transcript:
        raise RuntimeError('Recovery refused; no exit syscall requested')
    print('One process exit requested. Shell recovery still needs serial confirmation.')


if __name__ == '__main__':
    main()
