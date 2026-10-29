#!/usr/bin/env python3
"""Run standalone Neo reset probes in SRAM, then restore a checked console.

Requires an existing stopped-console recovery record. Never writes flash or
SD. The restore is attempted even if the UART capture or diagnostic fails.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

import serial

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from check_geometry_timing import inspect
from neo.load_linux import recovery_commands,check_fpga,check_program_status
from neo.console import UART,select_relay


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def qualify(build):
    manifest=json.loads((build/'manifest.json').read_text())
    telemetry=manifest.get('telemetry','uart')
    if telemetry not in ('uart','jtag'):raise ValueError('Unknown probe telemetry')
    expected={'neo_reset_probe.v','uart_tx.v','probe.cst','probe.sdc'}
    if telemetry=='jtag':expected.add('neo_reset_jtag.v')
    if set(manifest['sha256'])!=expected:
        raise ValueError('Unexpected probe source set')
    for rel,digest in manifest['sha256'].items():
        if sha(build/rel)!=digest:raise ValueError('Changed frozen probe '+rel)
    sources=[('neo_reset_probe.v',ROOT/'TESTS/rtl/neo_reset_probe.v'),
             ('uart_tx.v',ROOT/'tang/boards/neo/vendor/uart_tx.v')]
    if telemetry=='jtag':sources.append(('neo_reset_jtag.v',ROOT/'TESTS/rtl/neo_reset_jtag.v'))
    for name,original in sources:
        if sha(build/name)!=sha(original):raise ValueError('Unrecognized probe source '+name)
    log=(build/'build.log').read_text()
    if re.search(r'^ERROR',log,re.M) or 'Bitstream generation completed' not in log:
        raise ValueError('Incomplete probe build')
    if 'EX2478' in log:raise ValueError('Unresolved register initialization warning')
    if '<Part Number>: GW5AST-LV138PG484AC1/I0' not in (build/'impl/pnr/probe.tr').read_text():
        raise ValueError('Wrong probe FPGA')
    q=inspect(build,'probe')
    if q['status']!='PASS':raise ValueError('Probe must pass timing; no diagnostic waiver')
    text=(build/'impl/pnr/probe.rpt.txt').read_text()
    clocks=re.search(r'^\s*6\. Global Clock Signals\s*$(.*?)^\s*7\. ',text,re.M|re.S)
    if not clocks:raise ValueError('Missing routing report')
    q['routing_table']=clocks[1].strip()
    net=(build/'impl/gwsynthesis/probe.vg').read_text()
    if telemetry=='jtag':
        q['mailbox']=audit_mailbox(build,net)
    drivers=[]
    for name in ['mrst_1_s0']+[f'copies_{i}_s0' for i in range(4)]:
        m=re.findall(r'\bDFFCE '+name+r'\s*\((.*?)\);',net,re.S)
        if len(m)!=1:raise ValueError('Unknown probe reset mapping: '+name)
        d=dict(re.findall(r'\.(\w+)\(([^()]*)\)',m[0]))
        if d.get('D')!='reference_reset[0]' or d.get('CLK')!='clk_d' or d.get('CE')!='VCC':
            raise ValueError('Mismatched reset driver input')
        drivers.append(d)
    if len({d.get('CLEAR') for d in drivers})!=1 or len({d.get('Q') for d in drivers})!=5:
        raise ValueError('Merged or independently cleared reset copies')
    q.update(drivers=drivers,telemetry=telemetry,bitstream_sha256=sha(build/'impl/pnr/probe.fs'))
    return q


def audit_mailbox(build,net):
    """Require exactly two FFs per toggle crossing and narrow first-stage cuts."""
    record={}
    for prefix,clock,source,kind,reset_port in [('request','clk_d','request_toggle','DFFCE','CLEAR'),
                                ('response','tck_d','response_toggle','DFFRE','RESET')]:
        for index in (0,1):
            cell=f'{prefix}_sync_{index}_s0'
            found=re.findall(r'\b'+kind+' '+cell+r'\s*\((.*?)\);',net,re.S)
            if len(found)!=1:raise ValueError('Missing mailbox synchronizer '+cell)
            ports=dict(re.findall(r'\.(\w+)\(([^()]*)\)',found[0]))
            expected=dict(Q=f'{prefix}_sync[{index}]',
                D=source if index==0 else f'{prefix}_sync[0]',CLK=clock,CE='VCC')
            expected[reset_port]='GND'
            if ports!=expected:raise ValueError('Changed mailbox synchronizer '+cell)
            record[cell]=ports
    sdc=(build/'probe.sdc').read_text()
    cuts=[line for line in sdc.splitlines() if line.startswith('set_false_path')]
    expected=[f'set_false_path -from [get_regs {{{p}_toggle*}}] -to [get_regs {{{p}_sync_0_s0}}]'
              for p in ('request','response')]
    if cuts!=expected:raise ValueError('Mailbox CDC exceptions changed')
    for cmd,value in [('set_max_delay',100),('set_min_delay',0)]:
        if f'{cmd} {value} -from [get_regs {{snapshot_hold*}}] -to [get_regs {{dr*}}]' not in sdc:
            raise ValueError('Missing held-data timing bound')
    return record


def decode(raw):
    frames=[]
    for line in raw.splitlines():
        if not re.fullmatch(rb'R[0-9a-f]{40}',line):continue
        data=bytes.fromhex(line[1:].decode())
        if data[:2]!=b'RQ' or data[3]&0xfc:continue
        frames.append(dict(mask=data[2]>>4,copies=data[2]&15,reference=data[3]&3,
            epoch=int.from_bytes(data[4:8],'big'),errors=int.from_bytes(data[8:12],'big'),
            signatures=data[12:].hex()))
    return frames


def decode_jtag(log):
    frames=[]
    previous=None
    for index,value in re.findall(r'^RESET_JTAG (\d+) ([0-9a-fA-F]+)\s*$',log,re.M):
        word=int(value,16)
        if word>>163 or not word&(1<<160) or ((word>>161)&1)!=((word>>162)&1):
            raise ValueError('Incomplete or invalid JTAG snapshot '+index)
        toggle=(word>>162)&1
        if previous is not None and toggle==previous:raise ValueError('Repeated JTAG snapshot '+index)
        previous=toggle
        frame=decode(('R'+f'{word&((1<<160)-1):040x}'+'\n').encode())
        if len(frame)!=1:raise ValueError('Invalid JTAG snapshot signature '+index)
        frames+=frame
    return frames


def capture_jtag(trial,seconds):
    script=trial/'capture.tcl'
    script.write_text('''adapter driver ftdi
ftdi vid_pid 0x0403 0x6010
ftdi channel 0
ftdi layout_init 0x0008 0xf00b
ftdi device_desc "Dual RS232-HS"
transport select jtag
adapter speed 1000
gdb_port disabled
tcl_port disabled
telnet_port disabled
jtag newtap resetprobe tap -irlen 5 -expected-id 0x1000563d
init
''' + f'''for {{set i 0}} {{$i < {int(seconds*50)}}} {{incr i}} {{
    irscan resetprobe.tap 2
    runtest 20
    echo "RESET_JTAG $i [drscan resetprobe.tap 163 0]"
    sleep 20
}}
shutdown
''')
    with (trial/'jtag.log').open('w') as log:
        subprocess.run(['/usr/local/bin/openocd','-f',str(script)],stdout=log,
                       stderr=subprocess.STDOUT,check=True,timeout=seconds*3+15)
    frames=decode_jtag((trial/'jtag.log').read_text())
    if len(frames)!=int(seconds*50):raise ValueError('Incomplete JTAG capture')
    return frames


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,action='append',required=True)
    p.add_argument('--recover-failed-load',type=Path,required=True)
    p.add_argument('--restore-build',type=Path,required=True)
    p.add_argument('--restore-sha256',required=True)
    p.add_argument('--seconds',type=float,default=20)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if not 5<=a.seconds<=30:p.error('Capture must last 5..30 seconds per variant')
    builds=[b.resolve(strict=True) for b in a.build]
    qualifications=[qualify(b) for b in builds]
    restore=a.restore_build.resolve(strict=True)
    restore_qualification=json.loads((restore/'qualification.json').read_text())
    restore_diagnostic=a.restore_sha256 if restore_qualification['status']=='FAIL' else None
    q,restore_bit=check_fpga(restore,restore_diagnostic)
    if sha(restore_bit)!=a.restore_sha256:raise ValueError('Unexpected restore bitstream')
    guard=recovery_commands(a.recover_failed_load)
    devices=[d for d in Path('/sys/bus/usb/devices').iterdir()
             if (d/'serial').exists() and (d/'serial').read_text().strip()=='2025041420']
    if len(devices)!=1:raise ValueError('Expected one Neo programmer 2025041420')
    d=devices[0]
    if (d/'idVendor').read_text().strip()!='0403' or (d/'idProduct').read_text().strip()!='6010':
        raise ValueError('Wrong Neo programmer VID/PID')
    busdev=':'.join((d/n).read_text().strip() for n in ['busnum','devnum'])
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    (out/'guard.tcl').write_text('\n'.join(guard))
    with (out/'guard.log').open('w') as log:
        subprocess.run(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
            '-c','gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(out/'guard.tcl')],
            stdout=log,stderr=subprocess.STDOUT,check=True,timeout=30)
    if 'NEO_FAILED_LAUNCHER_CONFIRMED' not in (out/'guard.log').read_text():
        raise RuntimeError('Live stopped CPU guard incomplete')
    def program(bit,logpath):
        with logpath.open('w') as log:
            subprocess.run([str(Path.home()/'.local/bin/openFPGALoader'),'--busdev-num',busdev,
                '-b','tangconsole','-m','--verbose','--freq','6000000',str(bit)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        status=check_program_status(logpath.read_text())
        logpath.with_suffix('.status.json').write_text(json.dumps(status,indent=2)+'\n')
    results=dict(flash_written=False,sd_written=False,tests=[],restore_ok=False,error=None)
    try:
        for build,qualification in zip(builds,qualifications):
            trial=out/build.name;trial.mkdir()
            (trial/'qualification.json').write_text(json.dumps(qualification,indent=2)+'\n')
            program(build/'impl/pnr/probe.fs',trial/'program.log')
            print('Loaded '+build.name,flush=True)
            if qualification['telemetry']=='jtag':
                frames=capture_jtag(trial,a.seconds)
            else:
                with serial.Serial(UART,2000000,timeout=.1,exclusive=True) as link:
                    (trial/'relay.log').write_bytes(select_relay(link,2000000))
                    raw=bytearray();end=time.monotonic()+a.seconds
                    while time.monotonic()<end:raw.extend(link.read(4096))
                    if not raw:
                        # A silent relay is not a measured FPGA pass/failure.
                        # Keep the empty first capture and retry route selection once.
                        (trial/'uart_first_empty.log').write_bytes(raw)
                        (trial/'relay_retry.log').write_bytes(select_relay(link,2000000))
                        end=time.monotonic()+a.seconds
                        while time.monotonic()<end:raw.extend(link.read(4096))
                (trial/'uart.log').write_bytes(raw)
                frames=decode(raw)
            epochs={f['epoch'] for f in frames}
            result=dict(build=build.name,bitstream_sha256=qualification['bitstream_sha256'],
                frames=len(frames),epochs=len(epochs),max_errors=max((f['errors'] for f in frames),default=None),
                masks=sorted({f['mask'] for f in frames}),copies=sorted({f['copies'] for f in frames}),
                observation='captured' if frames else 'no_uart_observation',
                passed=len(frames)>=100 and len(epochs)>=10 and
                    all(f['mask']==0 and f['errors']==0 and f['reference']==3 and f['copies']==15 for f in frames))
            (trial/'frames.json').write_text(json.dumps(frames,indent=2)+'\n')
            (trial/'result.json').write_text(json.dumps(result,indent=2)+'\n')
            results['tests'].append(result);print(json.dumps(result),flush=True)
    except Exception as e:results['error']=repr(e)
    finally:
        try:
            if sha(restore_bit)!=a.restore_sha256:raise ValueError('Restore bitstream changed')
            program(restore_bit,out/'restore_program.log')
            subprocess.run([sys.executable,str(ROOT/'tools/neo/load_linux.py'),
                '--build',str(restore),'--already-programmed','--preflight-only',
                *(['--diagnostic-bitstream',a.restore_sha256] if restore_diagnostic else []),
                '--out',str(out/'restored_console')],check=True,timeout=120)
            results['restore_ok']=True
        except Exception as e:results['restore_error']=repr(e)
        (out/'result.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))
    if results['error'] or not results['restore_ok'] or not all(t['passed'] for t in results['tests']):
        raise SystemExit(1)


if __name__=='__main__':main()
