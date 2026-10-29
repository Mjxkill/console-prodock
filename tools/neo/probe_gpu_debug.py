#!/usr/bin/env python3
"""Read Neo GPU diagnostic snapshots; optional TARGET words never request DMA."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from load_linux import recovery_commands

ROOT=Path(__file__).resolve().parents[2]


def target_cases():
    """Configuration only: no draw, clear, texture read or memory command."""
    cases=[]
    def add(name,color,depth,width,height,stride,wanted):
        cases.append(dict(name=name,words=[0x16000000,color,depth,
            (width<<16)|height,(stride<<16)|stride,0,0,0],accepted=wanted))
    add('preflight',0x12000000,0x12001000,32,64,64,True)
    add('maximum',0x00800000,0x00900000,1024,512,2048,True)
    add('small',0,0x1000,8,16,32,True)
    add('zero_width',0,0x1000,0,16,32,False)
    add('zero_height',0,0x1000,8,0,32,False)
    add('unaligned_color',1,0x1000,8,16,32,False)
    add('unaligned_depth',0,3,8,16,32,False)
    add('overlap',0,0,8,16,32,False)
    add('short_stride',0,0x1000,32,16,32,False)
    add('overflow',0x3fffffe0,0x1000,8,16,32,False)
    for base in (0,0x00800000,0x10000000,0x12000000,0x20000000,0x30000000):
        for width,height,stride in ((8,16,32),(32,64,64),(400,240,800)):
            add(f'base_{base:08x}_{width}x{height}',base,base+0x100000,width,height,stride,True)
    add('preflight_again',0x12000000,0x12001000,32,64,64,True)
    return cases


def control_cases():
    """Only register/cache configuration opcodes, with no memory requests."""
    cases=[]
    def add(name,words,accepted=True):
        cases.append(dict(name=name,words=words+[0]*(8-len(words)),accepted=accepted))
    for row in range(3):
        add(f'matrix_row{row}',[31<<24,row]+[65536 if row==i else 0 for i in range(4)])
    add('matrix_invalid_row',[31<<24,3],False)
    add('light',[33<<24,0,0,256])
    add('invalidate',[30<<24])
    add('material',[25<<24,0,256,65535,0x04020100])
    add('material_invalid_alpha',[25<<24,0,257,65535,0x04020100],False)
    add('texture',[24<<24,0x01700000,0x00010001,32])
    add('plane',[26<<24,65536])
    add('invalidate_again',[30<<24])
    return cases


def decode(values):
    if len(values)!=16 or values[0]!=0x4e474442 or values[1]!=6:
        raise ValueError('Incomplete/unacknowledged GPU snapshot')
    flags=values[9];blit=values[11];state=(values[13]<<32)|values[12]
    return dict(sequence=values[3],host_words=values[2],received_words=values[4],
                last_received_word=values[5],done=values[8]&65535,
                engine_resetn=(flags>>12)&15,child_resetn=(flags>>16)&255,mrst=(flags>>10)&3,
                command_word=(flags>>7)&7,queue_valid=bool(flags&64),
                queue_pop=bool(flags&32),command_we=bool(flags&16),command_full=bool(flags&8),
                blitter_busy=bool(flags&4),ext_start=bool(flags&2),ext_active=bool(flags&1),
                command_bad=values[10]>>16,command_lost=values[10]&65535,
                blitter_wp=blit>>24,blitter_rp=(blit>>16)&255,opcode=(blit>>8)&255,
                blitter_reset=bool(blit&128),blitter_cmd_we=bool(blit&64),
                blitter_full=bool(blit&32),blitter_available=bool(blit&16),
                state=state,state_bits=[i for i in range(64) if state&(1<<i)],
                queue_data=values[14],extended_word0=values[15])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--failed-load',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--target-steps',action='store_true')
    mode.add_argument('--target-suite',action='store_true',help='Compare safe TARGET descriptors; no DMA')
    mode.add_argument('--control-suite',action='store_true',help='Compare register-only geometry/pixel commands; no DMA')
    a=p.parse_args();guard=recovery_commands(a.failed_load)[:-3]
    suite=a.target_suite or a.control_suite
    cases=control_cases() if a.control_suite else target_cases()
    out=a.out.resolve()
    if any(c in str(out) for c in '{}\\\r\n'):p.error('Unsafe output path')
    out.mkdir(parents=True,exist_ok=False)
    commands=[*guard,
        'if {[lindex [read_memory 0xe9005000 32 1] 0] != 0x4e474442} {error "GPU instrumentation is absent"}',
        '''proc snapshot {label} {
    if {([lindex [read_memory 0xe9005004 32 1] 0] & 5) != 4} {error "Debug source not ready or busy"}
    set expected [expr {([lindex [read_memory 0xe900500c 32 1] 0] + 1) & 0xffffffff}]
    write_memory 0xe9005004 32 {1}
    set complete 0
    for {set i 0} {$i < 50} {incr i} {
        sleep 1
        if {[lindex [read_memory 0xe9005004 32 1] 0] == 6 && [lindex [read_memory 0xe900500c 32 1] 0] == $expected} {
            set complete 1
            break
        }
    }
    if {!$complete} {error "GPU snapshot timeout"}
    echo "GPU_SNAPSHOT $label [read_memory 0xe9005000 32 16]"
}''', 'snapshot before']
    if a.target_steps:
        commands += [
            'if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU is not idle"}',
            'set sent [lindex [read_memory 0xe9005008 32 1] 0]',
            'if {($sent & 7) != 0 || $sent != [lindex [read_memory 0xe9005010 32 1] 0]} {error "Pending/partial command"}']
        for index,word in enumerate((0x16000000,0x12000000,0x12001000,0x00200040,0x00400040,0,0,0)):
            commands += [f'write_memory 0xe9001010 32 {{{word:#x}}}', 'sleep 2', f'snapshot word{index}']
    if suite:
        commands += [
            'if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU is not idle"}',
            'set sent [lindex [read_memory 0xe9005008 32 1] 0]',
            'if {($sent & 7) != 0 || $sent != [lindex [read_memory 0xe9005010 32 1] 0]} {error "Pending/partial command"}',
            'foreach address {0xe900000c 0xe9000014 0xe9000034 0xe9000044} {',
            '  if {[lindex [read_memory $address 32 1] 0] != 0} {error "Scanout must be disabled"}',
            '}']
        for case in cases:
            commands += ['set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]',
                'set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]',
                'set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]']
            commands += [f'write_memory 0xe9001010 32 {{{word:#x}}}' for word in case['words']]
            commands += ['set complete 0',
                'for {set i 0} {$i < 50} {incr i} {',
                '  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}',
                '  sleep 1', '}',
                'if {!$complete} {error "TARGET fence timeout"}',
                'set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]',
                'set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]',
                f'echo "GPU_TARGET {case["name"]} $delta $geometry_delta"']
        commands += ['snapshot after']
    commands += ['echo GPU_SNAPSHOT_COMPLETE','shutdown','']
    script=out/'probe.tcl';script.write_text('\n'.join(commands))
    error=None
    with (out/'openocd.log').open('w') as log:
        try:
            subprocess.run(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
                '-c','gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(script)],
                stdout=log,stderr=subprocess.STDOUT,check=True,timeout=30)
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as e:error=str(e)
    text=(out/'openocd.log').read_text();snapshots={}
    for label,words in re.findall(r'^GPU_SNAPSHOT (\w+) (.+)$',text,re.M):
        values=[int(w,0) for w in words.split()]
        if label in snapshots:raise ValueError('Duplicate snapshot label')
        snapshots[label]=dict(raw=values,decoded=decode(values))
    expected=['before']+([f'word{i}' for i in range(8)] if a.target_steps else ['after'] if suite else [])
    complete=error is None and list(snapshots)==expected and 'GPU_SNAPSHOT_COMPLETE' in text
    prior=json.loads((a.failed_load/'result.json').read_text())
    result=dict(capture_complete=complete,scope='Observation only; not a GPU qualification',
                bitstream_sha256=prior['bitstream_sha256'],snapshots=snapshots,
                cpu_left_halted=True if complete else None,transport_error=error,
                target_steps=a.target_steps,sd_written=False,flash_written=False)
    if suite:
        observations=re.findall(r'^GPU_TARGET (\w+) (\d+) (\d+)$',text,re.M)
        suite_complete=complete and [name for name,_,_ in observations]==[c['name'] for c in cases]
        result['suite_kind']='control' if a.control_suite else 'target'
        result['target_suite']=[dict(case,rejected_delta=int(delta),geometry_rejected_delta=int(geom),
            matches=int(delta)==int(not case['accepted']) and
            int(geom)==int(not case['accepted'] and case['words'][0]>>24>=31))
            for case,(name,delta,geom) in zip(cases,observations)]
        transport_ok=False
        if complete:
            before=snapshots['before']['decoded'];after=snapshots['after']['decoded']
            transport_ok=(after['command_bad']==before['command_bad'] and
                after['command_lost']==before['command_lost'] and
                (after['host_words']-before['host_words'])&0xffffffff==len(cases)*8 and
                (after['received_words']-before['received_words'])&0xffffffff==len(cases)*8 and
                after['done']==(before['done']+len(cases))&0xffff and
                not after['blitter_busy'] and after['command_word']==0)
        result['target_suite_complete']=suite_complete
        result['command_transport_passed']=transport_ok
        result['passed']=suite_complete and transport_ok and all(c['matches'] for c in result['target_suite'])
    result['probe_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result['script_sha256']=hashlib.sha256(script.read_bytes()).hexdigest()
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(capture_complete=complete,snapshots={k:v['decoded'] for k,v in snapshots.items()},
        **(dict(passed=result['passed'],command_transport_passed=result['command_transport_passed'],
            cases=[{k:v for k,v in case.items() if k!='words'} for case in result['target_suite']]) if suite else {})),indent=2))
    if not complete:raise SystemExit('Incomplete capture; partial evidence saved')
    if suite and not result['passed']:raise SystemExit('Configuration suite mismatch; evidence saved')


if __name__=='__main__':main()
