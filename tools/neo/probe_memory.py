#!/usr/bin/env python3
"""Diagnose the failed Neo Linux transport in volatile DDR; never SD/flash."""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import struct
import subprocess
from load_linux import recovery_commands

ROOT = Path(__file__).resolve().parents[2]


def region_patterns():
    """Distinct signatures, held simultaneously across all 16 DDR regions."""
    result=[]
    for region in range(16):
        for edge,offset in enumerate((0x100000,0x3fff000)):
            address=region*0x4000000+offset
            words=[(address+i*4)^0xa5396c17 for i in range(1024)]
            result.append((f'region_{region:02d}_{edge}.bin',address,struct.pack('<1024I',*words)))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--failed-load', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cpu', action='store_true',
                        help='Also compare CPU reads and writes using a verified ILM diagnostic')
    parser.add_argument('--clock', action='store_true',
                        help='Also sample the free-running platform timer across host-timed seconds')
    parser.add_argument('--gpu', action='store_true',
                        help='Compare native GPU fills with CPU/JTAG DDR writes in the same scratch page')
    parser.add_argument('--gpu-cpu', action='store_true',
                        help='Also issue a GPU TARGET through CPU stores in the ILM diagnostic; no GPU DMA')
    parser.add_argument('--gpu-step', action='store_true',
                        help='With --gpu, read BUSY/done/errors after each word of TARGET; no later fill commands')
    parser.add_argument('--regions', action='store_true',
                        help='Write then read 32 distinct 4-KiB pages distributed across the 1-GiB DDR')
    parser.add_argument('--status-only', action='store_true',
                        help='Read scanout, GPU, USB and gamepad status twice; no DDR/ILM writes')
    args = parser.parse_args()
    if args.gpu_step and not args.gpu:
        parser.error('--gpu-step requires --gpu')
    if args.gpu_cpu:
        args.cpu = True
    if args.status_only and (args.cpu or args.clock or args.gpu or args.regions):
        parser.error('--status-only cannot be combined with active probes')
    previous = json.loads((args.failed_load/'result.json').read_text())
    if previous['passed'] and previous.get('run_mode') != 'preflight_only':
        raise SystemExit('Refusing to halt a successfully booted Linux')
    # Only after a verified failed launcher attempt. This scratch region is
    # outside both the staged payload and decoded kernel/initramfs.
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    if args.status_only:
        commands=recovery_commands(args.failed_load)[:-3]
        for when in ('BEFORE','AFTER'):
            if when=='AFTER':commands.append('sleep 1000')
            for name,address,count in [('SCAN',0xe9000000,30),('GPU',0xe9001000,26),
                                       ('USB',0xe9003000,2),('PAD0',0xe9004020,5),
                                       ('PAD1',0xe9004040,5)]:
                commands.append(f'echo "NEO_{name}_{when} [read_memory {address:#x} 32 {count}]"')
        commands+=['shutdown','']
        script=out/'status.tcl';script.write_text('\n'.join(commands))
        with (out/'openocd.log').open('w') as log:
            subprocess.run(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
                            '-c','gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(script)],
                           stdout=log,stderr=subprocess.STDOUT,check=True,timeout=30)
        import re
        samples={key:[int(v,0) for v in values.split()] for key,values in re.findall(
            r'^NEO_(\w+) (.+)$',(out/'openocd.log').read_text(),re.M)}
        result=dict(samples=samples,sd_written=False,flash_written=False,
                    writes=['Gamepad STATUS reads latch report snapshots only'],
                    scan_frames_delta=(samples['SCAN_AFTER'][6]-samples['SCAN_BEFORE'][6])&0xffffffff,
                    pad_reports_delta=[(samples[f'PAD{i}_AFTER'][2]-samples[f'PAD{i}_BEFORE'][2])&0xffffffff for i in range(2)])
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2));return
    rng = random.Random(138)
    words = ([0, 0xffffffff, 0xaaaaaaaa, 0x55555555] * 64 +
             [1 << i for i in range(32)] * 8 + [rng.getrandbits(32) for _ in range(512)])
    expected = struct.pack('<'+'I'*len(words), *words)
    (out/'pattern.bin').write_bytes(expected)
    cpu_commands=[];gpu_commands=[];gpu_expected={};region_commands=[]
    region_expected={}
    if args.regions:
        for filename,address,pattern in region_patterns():
            (out/('seed_'+filename)).write_bytes(pattern)
            region_commands.append(f'load_image {{{out/("seed_"+filename)}}} {address:#x} bin')
            region_expected[filename]=pattern
        # Never verify immediately after each write: aliases must remain
        # simultaneously occupied by different signatures before any read.
        for filename,address,pattern in region_patterns():
            region_commands.append(f'dump_image {{{out/filename}}} {address:#x} {len(pattern)}')
    if args.gpu:
        gpu_commands=['if {[lindex [read_memory 0xe9001000 32 1] 0] != 0x424c5432} {error "Wrong GPU command port"}',
                      'set old_font [lindex [read_memory 0xe9001014 32 1] 0]',
                      'write_memory 0xe9001014 32 {0x321}',
                      'echo "NEO_GPU_FONT_WRITE [read_memory 0xe9001014 32 1]"',
                      'write_memory 0xe9001014 32 [list $old_font]']
        def emit(words):
            gpu_commands.append('set done_before [expr {[lindex [read_memory 0xe9001008 32 1] 0] & 0xffff}]')
            for index,word in enumerate(words):
                gpu_commands.append(f'write_memory 0xe9001010 32 {{{word:#x}}}')
                if args.gpu_step:
                    gpu_commands.extend(['sleep 2',
                        f'echo "NEO_GPU_WORD_{index} [read_memory 0xe9001004 32 3]"'])
            gpu_commands.extend(['sleep 20',
                'echo "NEO_GPU_COMMAND_STATUS [read_memory 0xe9001000 32 18]"',
                'if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) != (($done_before+1)&0xffff)} {error "GPU command did not complete"}'])
        emit([22<<24,0x12000000,0x12001000,(32<<16)|64,(64<<16)|64,0,0,0])
        for color in (() if args.gpu_step else (0xffff,0,0xaaaa,0x5555)):
            emit([28<<24,1,color,0,0,(32<<16)|64,0,0])
            name=f'gpu_{color:04x}.bin'
            gpu_expected[name]=struct.pack('<H',color)*2048
            gpu_commands.append(f'dump_image {{{out/name}}} 0x12000000 4096')
        gpu_commands.append('echo "NEO_GPU_ERRORS [read_memory 0xe900100c 32 1] [read_memory 0xe900101c 32 1] [read_memory 0xe9001024 32 1]"')
    if args.cpu:
        toolchain=Path.home()/'gowin/GMD_2025.01_linux/GMD/toolchain/gowin/gcc_riscv/bin'
        elf=out/'memory_probe.elf';binary=out/'memory_probe.bin'
        source=ROOT/'tools/neo/memory_probe.S'
        (out/'memory_probe.S').write_bytes(source.read_bytes())
        subprocess.run([str(toolchain/'riscv-none-elf-gcc'),'-march=rv32imac_zicsr','-mabi=ilp32',
                        *(['-DPROBE_GPU'] if args.gpu_cpu else []),
                        '-nostdlib','-nostartfiles','-Wl,-Ttext=0xa0000000',
                        '-Wl,--build-id=none',str(out/'memory_probe.S'),'-o',str(elf)],check=True)
        subprocess.run([str(toolchain/'riscv-none-elf-objcopy'),'-O','binary',str(elf),str(binary)],check=True)
        if binary.stat().st_size>4096:raise RuntimeError('Diagnostic exceeds its ILM code page')
        cpu_commands=[f'load_image {{{out}/pattern.bin}} 0xa000c000 bin',
                      f'verify_image {{{out}/pattern.bin}} 0xa000c000 bin',
                      f'load_image {{{binary}}} 0xa0000000 bin',
                      f'verify_image {{{binary}}} 0xa0000000 bin',
                      'resume 0xa0000000','sleep 500','halt',
                      'echo "NEO_CPU_PROBE_PC [reg pc]"',
                      'echo "NEO_CPU_PROBE_STATUS [read_memory 0xa000e000 32 4]"',
                      *(['echo "NEO_GPU_CPU_STATUS [read_memory 0xa000e010 32 4]"'] if args.gpu_cpu else []),
                      f'dump_image {{{out}/cpu_jtag_written.bin}} 0xa000b000 4096',
                      f'dump_image {{{out}/cpu_written.bin}} 0xa000d000 4096',
                      f'dump_image {{{out}/jtag_cpu_written.bin}} 0x12000000 4096']
    script = out/'probe.tcl'
    script.write_text('\n'.join([
        'riscv expose_csrs 1994,1996,2000',
        *recovery_commands(args.failed_load)[:-3],
        'echo "NEO_PC [reg pc]"', 'reg priv 3', 'reg satp 0', 'reg mstatus 0', 'reg mie 0',
        'reg csr1996 6', 'reg csr1994 0',
        'echo "NEO_GPU_BEFORE [read_memory 0xe9001000 32 26]"',
        'echo "NEO_USB_MSC [read_memory 0xe9003000 32 2]"',
        'echo "NEO_USB_TRACE_BEFORE [read_memory 0xe9002000 32 3]"',
        'write_memory 0xe900200c 32 {2}', 'sleep 20',
        'echo "NEO_USB_TRACE_AFTER [read_memory 0xe9002000 32 3]"',
        'echo "NEO_USB_TRACE_SNAPSHOT [read_memory 0xe9002040 32 32]"',
        f'load_image {{{out}/pattern.bin}} 0x12000000 bin',
        f'dump_image {{{out}/read1.bin}} 0x12000000 {len(expected)}',
        f'dump_image {{{out}/read2.bin}} 0x12000000 {len(expected)}',
        f'dump_image {{{out}/stage_head.bin}} 0x10000000 4096',
        # Last 4 KiB of the hard ILM: a control for the JTAG path. This
        # overwrites the failed launcher's stack, so reload before resuming.
        f'load_image {{{out}/pattern.bin}} 0xa000f000 bin',
        f'dump_image {{{out}/ilm_read.bin}} 0xa000f000 {len(expected)}',
        # Keep the already failed launcher halted for subsequent inspection.
        *region_commands,*cpu_commands,*gpu_commands,
        *(['set pc [lindex [reg pc] 2]',
           'if {$pc != 0x80000000 && $pc != 0x80000004} {error "Clock test needs the boot parking loop"}',
           'echo "NEO_TIMER0 [read_memory 0xe6000000 32 2]"',
           'resume 0x80000000','sleep 1000','halt',
           'echo "NEO_TIMER1 [read_memory 0xe6000000 32 2]"',
           'resume 0x80000000','sleep 1000','halt',
           'echo "NEO_TIMER2 [read_memory 0xe6000000 32 2]"'] if args.clock else []),
        'shutdown', '']))
    transport_error = None
    with (out/'openocd.log').open('w') as log:
        try:
            subprocess.run(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
                            '-c','gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(script)],
                           stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            # A failed GPU fence must stop further GPU commands, but must not
            # discard DDR/ILM evidence already captured earlier in the script.
            transport_error = str(error)
    result = dict(writes=['4096 bytes at volatile DDR 0x12000000',
                          '4096 bytes at hard ILM 0xa000f000; reload launcher before resume',
                          'USB diagnostic snapshot command only'], sd_written=False, flash_written=False,
                  writes_note='Requested operations; openocd.log records how far execution reached.',
                  transport_error=transport_error, passed=transport_error is None)
    result['bitstream_sha256']=previous.get('bitstream_sha256')
    result['bitstream_identity']='From the preceding load record; no independent FPGA readback'
    if args.clock:
        import re
        samples=[]
        for _,values in re.findall(r'^NEO_TIMER([012]) (.+)$',(out/'openocd.log').read_text(),re.M):
            lo,hi=(int(v,0) for v in values.split());samples.append((hi<<32)|lo)
        result['timer_samples']=samples
        result['timer_ticks_per_host_second']=[b-a for a,b in zip(samples,samples[1:])]
        result['timer_note']='Approximate rate while running the known parking loop: includes resume/halt overhead; not a precision frequency meter.'
    filenames=['read1.bin','read2.bin','ilm_read.bin']
    if args.regions:
        filenames.extend(region_expected)
        result['regions']=[dict(file=name,address=hex(address),bytes=len(pattern))
                           for name,address,pattern in region_patterns()]
        result['writes'].append('32 x 4096 bytes of distinct signatures across DDR 0..0x3fffffff, all written before any region readback')
    if args.gpu:
        import re
        hit=re.search(r'^NEO_GPU_ERRORS (.+)$',(out/'openocd.log').read_text(),re.M)
        result['gpu_errors']=[] if hit is None else [int(x,0) for x in hit[1].split()]
        result['writes'].append('GPU TARGET only, no DMA' if args.gpu_step else
            'GPU target then up to four native fills of scratch DDR 0x12000000..0x12000fff; stop on failed fence')
        if args.gpu_step:
            result['gpu_word_status']={index:[int(v,0) for v in values.split()]
                for index,values in re.findall(r'^NEO_GPU_WORD_(\d+) (.+)$',(out/'openocd.log').read_text(),re.M)}
        filenames.extend(gpu_expected)
    if args.cpu:
        import re
        log=(out/'openocd.log').read_text()
        status=re.search(r'^NEO_CPU_PROBE_STATUS (.+)$',log,re.M)
        values=[] if status is None else [int(x,0) for x in status[1].split()]
        result['cpu_status']=values
        result['cpu_completed']=values==[0x4d435055,3,0,0]
        result['passed'] &= result['cpu_completed']
        result['writes'].append('CPU diagnostic in ILM; 4096-byte pattern in volatile DDR 0x12000000')
        if args.gpu_cpu:
            status=re.search(r'^NEO_GPU_CPU_STATUS (.+)$',log,re.M)
            values=[] if status is None else [int(x,0) for x in status[1].split()]
            result['gpu_cpu_status']=values
            result['gpu_cpu_completed']=(len(values)==4 and values[2]==0x424c5432 and
                                         values[3]==1 and (values[1]&0xffff)==((values[0]+1)&0xffff))
            result['passed'] &= result['gpu_cpu_completed']
            result['writes'].append('CPU GPU TARGET only, no DMA')
        if result['cpu_completed']:
            filenames+=['cpu_jtag_written.bin','cpu_written.bin','jtag_cpu_written.bin']
    for filename in filenames:
        if not (out/filename).exists():
            result[filename] = dict(error='Readback missing; probe stopped before capture')
            result['passed'] = False
            continue
        actual = (out/filename).read_bytes()
        reference=region_expected.get(filename,gpu_expected.get(filename,expected))
        if len(actual) != len(reference):
            result[filename] = dict(error='Incomplete readback', bytes=len(actual), expected_bytes=len(reference))
            result['passed'] = False
            continue
        errors = [(i,a,b) for i,(a,b) in enumerate(zip(actual,reference)) if a != b]
        result['passed'] &= not errors
        result[filename] = dict(error_bytes=len(errors), first=errors[:20],
                               byte_lanes=dict(Counter(i % 8 for i,a,b in errors)),
                               bits=dict(Counter(i % 4 * 8 + bit for i,a,b in errors for bit in range(8) if (a^b)&(1<<bit))))
    if all((out/name).is_file() for name in ('read1.bin','read2.bin')):
        result['repeated_reads_identical'] = (out/'read1.bin').read_bytes() == (out/'read2.bin').read_bytes()
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if not result['passed']:
        raise SystemExit('Neo probe failed; partial evidence preserved in '+str(out/'result.json'))


if __name__ == '__main__':
    main()
