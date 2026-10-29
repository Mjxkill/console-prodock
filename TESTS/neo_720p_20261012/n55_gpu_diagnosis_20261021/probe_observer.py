#!/usr/bin/env python3
"""Read the reviewed Neo observer on an already loaded, parked FPGA.

Require qualification or an exact reviewed setup-only diagnostic image.

Only register configuration and one volatile 4-KiB DDR scratch page are written.
No FPGA programming, CPU execution, drawing DMA, SD or flash operation.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/neo'))
from load_linux import check_fpga,recovery_commands
from probe_gpu_debug import target_cases,control_cases

# N56 requested explicitly; N56r1 is its reviewed three-control routing A/B.
# Exact names/hashes only. Shared qualification checks remain mandatory.
DIAGNOSTIC_IMAGES={
    'ecef1e120d9940bab6b28bac12557e87f0790e8610cf6788326220bd38db0f3a': 'console_neo_n56_observe',
    '426389b02a4c1c240a28a711546569315e5c4d9478199f12e1e38f46009d3d2d': 'console_neo_n56r1',
}


def suite():
    source={c['name']:c for c in target_cases()+control_cases()}
    result=[dict(name='legacy_affine_before',words=[0x0c000000]+[0]*7,accepted=True)]
    result += [source[name] for name in ('preflight','zero_width','preflight_again',
        'matrix_row0','matrix_invalid_row','light','material','texture','plane','invalidate')]
    result += [dict(name='legacy_affine_after',words=[0x0c000000]+[0]*7,accepted=True),
               dict(source['invalidate'],name='invalidate_repeat')]
    if any(len(c['words'])!=8 or c['words'][0]>>24 not in (12,22,24,25,26,30,31,33) for c in result):
        raise ValueError('Not a configuration-only suite')
    return result


def script_text(guard,out):
    if any(c in str(out) for c in '{}\\\r\n'):
        raise ValueError('Unsafe output path')
    commands=['riscv expose_csrs 1994,1996,2000',*guard,
        'reg priv 3','reg satp 0','reg mstatus 0','reg mie 0','reg csr1996 6','reg csr1994 0',
        'foreach address {0xe900000c 0xe9000014 0xe9000034 0xe9000044} {',
        '  if {[lindex [read_memory $address 32 1] 0] != 0} {error "Scanout must be disabled"}', '}',
        'if {[lindex [read_memory 0xe9001000 32 1] 0] != 0x424c5432} {error "Wrong GPU port"}',
        'if {[lindex [read_memory 0xe9005000 32 1] 0] != 0x4e474442} {error "Debug instrument absent"}',
        'if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU not idle"}',
        'set old_font [lindex [read_memory 0xe9001014 32 1] 0]',
        'write_memory 0xe9001014 32 {0x321}',
        'set font_test [lindex [read_memory 0xe9001014 32 1] 0]',
        'write_memory 0xe9001014 32 [list $old_font]',
        'if {$font_test != 0x321 || [lindex [read_memory 0xe9001014 32 1] 0] != $old_font} {error "MMIO font address witness differs"}',
        f'load_image {{{out/"pattern.bin"}}} 0x12000000 bin',
        f'dump_image {{{out/"memory_before.bin"}}} 0x12000000 4096',
        f'verify_image {{{out/"pattern.bin"}}} 0x12000000 bin',
        '''proc raw_observation {label} {
    if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "Raw observation needs idle GPU"}
    for {set i 0} {$i < 3} {incr i} {
        sleep 2
        echo "OBSERVER_RAW $label $i [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
    }
}''',
        '''proc snapshot_observation {label} {
    set status [lindex [read_memory 0xe9005004 32 1] 0]
    echo "OBSERVER_HANDSHAKE $label before $status [read_memory 0xe900500c 32 1] [read_memory 0xe9005040 32 1]"
    if {($status & 5) == 4} {write_memory 0xe9005004 32 {1}}
    for {set i 0} {$i < 30} {incr i} {
        sleep 1
        set status [lindex [read_memory 0xe9005004 32 1] 0]
        echo "OBSERVER_HANDSHAKE $label poll$i $status [read_memory 0xe900500c 32 1] [read_memory 0xe9005040 32 1]"
        if {($status & 3) == 2} {break}
    }
    raw_observation $label
}''',
        'echo "OBSERVER_GPU before [read_memory 0xe9001000 32 26]"',
        'set initial_errors [lindex [read_memory 0xe900100c 32 1] 0]',
        'set initial_lost [lindex [read_memory 0xe900101c 32 1] 0]',
        'set initial_host [lindex [read_memory 0xe9005008 32 1] 0]',
        'if {($initial_host & 7) != 0} {error "Partial host command"}',
        'raw_observation before', 'snapshot_observation snapshot_before']
    for case in suite():
        commands += ['set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]',
            'set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]',
            'set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]',
            *[f'write_memory 0xe9001010 32 {{{word:#x}}}' for word in case['words']],
            'set complete 0',
            'for {set i 0} {$i < 100} {incr i} {',
            '  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}',
            '  sleep 1', '}', 'if {!$complete} {error "Configuration fence timeout"}',
            'sleep 2',
            'set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]',
            'set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]',
            f'echo "OBSERVER_CONFIG {case["name"]} $delta $geometry_delta"',
            f'raw_observation {case["name"]}']
    commands += ['snapshot_observation snapshot_after1','snapshot_observation snapshot_after2',
        'echo "OBSERVER_GPU after [read_memory 0xe9001000 32 26]"',
        f'dump_image {{{out/"memory_after.bin"}}} 0x12000000 4096',
        f'verify_image {{{out/"pattern.bin"}}} 0x12000000 bin',
        'if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU not idle at exit"}',
        'if {[lindex [read_memory 0xe900100c 32 1] 0] != $initial_errors || [lindex [read_memory 0xe900101c 32 1] 0] != $initial_lost} {error "Transport error counters changed"}',
        f'if {{(([lindex [read_memory 0xe9005008 32 1] 0]-$initial_host)&0xffffffff) != {len(suite())*8}}} {{error "Host word delta differs"}}',
        'echo "OBSERVER_COMPLETE [reg pc]"','shutdown','']
    return '\n'.join(commands)


def decode_meta(value):
    return dict(request=value&1,req_s=(value>>1)&3,ack=(value>>3)&1,
        ack_s=(value>>4)&3,mem_up=(value>>6)&3,ready_s=(value>>8)&3,
        busy=(value>>10)&1,valid=(value>>11)&1,ext_command_opcode=(value>>16)&255)


def parse_observations(text):
    raw={}
    for label,index,words in re.findall(r'^OBSERVER_RAW (\w+) ([012]) (.+)$',text,re.M):
        values=[int(w,0) for w in words.split()]
        if len(values)!=3:
            raise ValueError('Invalid raw observation width')
        raw.setdefault(label,[]).append(dict(index=int(index),geometry_header=values[0],pixel_header=values[1],
            meta=values[2],decoded=decode_meta(values[2])))
    repeated={label:len(rows)==3 and [r['index'] for r in rows]==[0,1,2]
        and all((r['geometry_header'],r['pixel_header'],r['meta'])==
                (rows[0]['geometry_header'],rows[0]['pixel_header'],rows[0]['meta']) for r in rows)
        for label,rows in raw.items()}
    commands=[]
    for name,delta,geom in re.findall(r'^OBSERVER_CONFIG (\w+) (\d+) (\d+)$',text,re.M):
        case=next(c for c in suite() if c['name']==name)
        commands.append(dict(case,rejected_delta=int(delta),geometry_rejected_delta=int(geom),
            expectation_matches=int(delta)==int(not case['accepted']) and int(geom)==int(not case['accepted'] and case['words'][0]>>24>=31)))
    handshake=[dict(label=l,phase=p,status=int(s,0),sequence=int(q,0),meta=int(m,0),decoded=decode_meta(int(m,0)))
        for l,p,s,q,m in re.findall(r'^OBSERVER_HANDSHAKE (\w+) (\w+) (\S+) (\S+) (\S+)$',text,re.M)]
    expected_geometry=expected_pixels=None
    header_checks=[]
    for case in suite():
        op=case['words'][0]>>24
        if op>=22:
            expected_geometry=case['words'][0]
        if 22<=op<31:
            expected_pixels=case['words'][0]
        rows=raw.get(case['name'],[])
        if rows:
            header_checks.append(dict(name=case['name'],stable=repeated[case['name']],
                expected_geometry=expected_geometry,expected_pixels=expected_pixels,
                geometry_matches=None if expected_geometry is None else all(r['geometry_header']==expected_geometry for r in rows),
                pixel_matches=None if expected_pixels is None else all(r['pixel_header']==expected_pixels for r in rows),
                ext_opcode_matches=all(r['decoded']['ext_command_opcode']==op for r in rows)))
    return dict(raw=raw,repeated_samples_equal=repeated,configurations=commands,
        header_checks=header_checks,handshake=handshake)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True)
    p.add_argument('--failed-load',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--diagnostic-bitstream',choices=list(DIAGNOSTIC_IMAGES),
        help='Exact reviewed N56/N56r1 only; setup exception, qualification stays FAIL')
    a=p.parse_args()
    build=a.build.resolve(strict=True)
    if a.diagnostic_bitstream is not None and build.name!=DIAGNOSTIC_IMAGES[a.diagnostic_bitstream]:
        raise ValueError('Diagnostic image name and hash do not match')
    if build.name=='console_neo_n56r1':
        audit=json.loads((build/'local_controls_audit.json').read_text())
        if not audit['passed'] or not audit['same_synthesis_netlist']:
            raise ValueError('Three-control routing audit failed')
        for path,digest in audit['checks_sha256'].items():
            if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest:
                raise ValueError('Routing audit input changed: '+path)
    q,bit=check_fpga(build,diagnostic_bitstream=a.diagnostic_bitstream,preflight_only=True)
    marker=json.loads((build/'observer_build.json').read_text())
    manifest=json.loads((build/'sources.json').read_text())
    sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
    if marker['source_manifest_sha256']!=sha(build/'sources.json') or any(sha(build/'source'/name)!=wanted for name,wanted in manifest.items()):
        raise ValueError('Observer frozen sources differ')
    prior=json.loads((a.failed_load/'result.json').read_text())
    if prior.get('bitstream_sha256')!=q['bitstream_sha256']:
        raise ValueError('Loader anchor refers to another FPGA')
    guard=recovery_commands(a.failed_load)[:-3]
    out=a.out.resolve()
    script=script_text(guard,out)
    out.mkdir(parents=True,exist_ok=False)
    expected=struct.pack('<1024I',*[(0x12000000+i*4)^0xa5396c17 for i in range(1024)])
    (out/'pattern.bin').write_bytes(expected)
    (out/'probe.tcl').write_text(script)
    error=None
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with (out/'openocd.log').open('w') as log:
            try:
                subprocess.run(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
                    '-c','gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(out/'probe.tcl')],
                    stdout=log,stderr=log,check=True,timeout=60)
            except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as e:
                error=str(e)
    text=(out/'openocd.log').read_text()
    result=parse_observations(text)
    labels=['before','snapshot_before',*[c['name'] for c in suite()],
            'snapshot_after1','snapshot_after2']
    raw_complete=list(result['raw'])==labels and all(
        [r['index'] for r in result['raw'][label]]==[0,1,2] for label in labels)
    commands_complete=[c['name'] for c in result['configurations']]==[c['name'] for c in suite()]
    complete=error is None and 'OBSERVER_COMPLETE' in text and commands_complete and raw_complete
    memory={name:(out/name).is_file() and (out/name).read_bytes()==expected
            for name in ('memory_before.bin','memory_after.bin')}
    result.update(scope=__doc__,capture_complete=complete,transport_error=error,
        memory=memory,bitstream_sha256=q['bitstream_sha256'],bitstream_identity='preceding verified loader record; no FPGA readback',
        cpu_left_halted=True if complete else None,sd_written=False,flash_written=False,
        raw_observations_atomic=False,qualification_result=False,
        qualification_status=q['status'],
        qualification_mode='diagnostic_setup_violation' if a.diagnostic_bitstream else 'qualified',
        diagnostic_bitstream=a.diagnostic_bitstream,
        probe_sha256=sha(Path(__file__)),script_sha256=sha(out/'probe.tcl'))
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(capture_complete=complete,memory=memory,
        header_checks=result['header_checks'],repeated_samples_equal=result['repeated_samples_equal'],
        configs=[{k:v for k,v in c.items() if k!='words'} for c in result['configurations']],
        handshake=result['handshake'],transport_error=error),indent=2))
    if not complete:
        raise SystemExit('Incomplete observation; evidence saved')


if __name__=='__main__':
    main()
