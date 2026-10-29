#!/usr/bin/env python3
"""Neo console: SRAM FPGA + CRC-checked Linux in DDR/ILM, never SD or flash.

The first load quiesces the existing Linux shell and rejects mounted SD
partitions. Recovery from the observed failed ILM launcher requires both
its saved failure and a live JTAG fingerprint before FPGA reconfiguration.
The completed analyser DDR diagnostic has a separate, exact-code handoff;
it must still be halted, with its retained DTCM results unchanged.
"""
import argparse,fcntl,hashlib,json,math,random,re,struct,subprocess,threading,time
from pathlib import Path
import serial
from console import UART,select_relay
ROOT=Path(__file__).resolve().parents[2]
ANALYSER_DDR_DIAGNOSTIC_SHA256='f50e728fd07c8e6e98be867f21655b4e3bd9768452260cbe0831c44f1a709b36'
ANALYSER_L31R8_SHA256='5242c13a281f2df5dc5e558dd2ee99ed7ef1d9eef7ffbcd6eb70fd43ec6569be'
# Exact historical DDR reference requested on 2026-10-20. Its later GPU
# owner-model finding remains a qualification failure. This restoration is
# restricted to parked-CPU preflight, never Linux or an automatic candidate.
DDR59_REFERENCE=dict(
    bitstream_sha256='b734fb21868b4ac840944f944cb5473cbd36bbea256cf7ff88123eb826537ab4',
    owner_audit_sha256='b432cc43fe643ab227ac55aea5192c1eeabb1337ee33d1f4bb87c9b2bf3039fa',
    proof_sha256={
        'result.json':'082dd56b23c5d64a78133c5db7a107a11d8afc626ed340930bc5f6dd2df86f89',
        'openocd.log':'293caa4e6510602be2d0acb634a3a0778f2ef9a2606e6b4bd792a1956d3e43e8',
        'qualification_used.json':'44efb84a850a8282a4f857913091e3303a8a43fd085b904b3e2c9f3019baac58',
        'load.tcl':'3b5c70a8f69e4d83084f1838f5393e2c8061696c4ca4e90ea186b3b5f3b3094b'})
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(test,message):
    if not test:raise RuntimeError(message)
def gpu_error_guard_before():
    # Completion also advances when a command is rejected. Observe all GPU
    # rejection/loss counters before and after the harmless TARGET command.
    return ['set gpu_error_registers {0xe900100c 0xe900101c 0xe9001024 0xe9001034 0xe900104c}',
            'foreach address $gpu_error_registers {set gpu_error_before($address) [lindex [read_memory $address 32 1] 0]}']
def gpu_error_guard_after():
    return ['foreach address $gpu_error_registers {',
            '  set after [lindex [read_memory $address 32 1] 0]',
            '  if {$after != $gpu_error_before($address)} {error "GPU preflight command rejected/lost at $address: $gpu_error_before($address) -> $after"}',
            '}']
def routing_observation_only(name,audit):
    """Only known reset-route observations, never malformed mapped logic.

    The 2026-10-16 standalone JTAG A/B shows a passing reset can still be
    labelled LW in 1.9.12.03. Such labels remain qualification failures, but
    may be measured in a parked-CPU experiment for one explicit SHA.
    """
    patterns={
        'gpu_reset_tree':r'Reset (?:[0-9]|1[01]) still uses a global routing resource',
        'gpu_wide_controls':r'(?:gpu_debug_state\[(?:4[3-9]|5[0-5])\]|u_gpu/mrst\[1\]) still uses LW'}
    errors=audit.get('errors',[])
    return name in patterns and audit.get('passed') is False and bool(errors) and all(
        re.fullmatch(patterns[name],error) for error in errors)

def check_fpga(build, diagnostic_bitstream=None, diagnostic_gpu_routing=False,
               *, diagnostic_recovery_min_ns=None, preflight_only=False,
               restore_ddr59_reference=None):
    """An explicit diagnostic may waive setup or known routing labels.

    Qualification stays FAIL. Hold, pulse, removal, mapped logic and hashes
    remain mandatory. A user-requested recovery experiment additionally needs
    an explicit finite negative slack floor, exact SHA and parked-CPU mode.
    Automatic callers never supply this exception. It cannot be combined
    with the known-LW routing observation or used to boot Linux.
    """
    q=json.loads((build/'qualification.json').read_text())
    bit=build/'impl/pnr/console_neo.fs'
    require(sha(bit)==q['bitstream_sha256'],'Changed FPGA bitstream')
    require(sha(build/'impl/pnr/console_neo.tr')==q['timing_sha256'],'Changed timing report')
    owner=q.get('synthesis_audits',{}).get('gpu_owner_replication',{})
    require(sha(build/'impl/pnr/console_neo.vo')==owner.get('netlist_sha256'),
            'Changed post-route GPU-owner audit input')
    require(set(q.get('timing_checks_ns',{}))=={'setup','hold','recovery','removal'},
            'Re-run tools/check_neo_timing.py: separate reset timing checks are required')
    if restore_ddr59_reference is not None:
        require(preflight_only and diagnostic_bitstream is None and not diagnostic_gpu_routing
                and diagnostic_recovery_min_ns is None,
                'DDR5.9 reference restoration requires preflight-only and no other diagnostic waiver')
        require(q['bitstream_sha256']==DDR59_REFERENCE['bitstream_sha256'],
                'Only the retained N38 DDR5.9 bitstream may be restored')
        proof=Path(restore_ddr59_reference)
        require(all(sha(proof/name)==expected
                    for name,expected in DDR59_REFERENCE['proof_sha256'].items()),
                'Changed historical DDR5.9 preflight evidence')
        previous=json.loads((proof/'result.json').read_text())
        require(previous.get('passed') is True and previous.get('run_mode')=='preflight_only'
                and previous.get('cpu_left_halted') is True
                and previous.get('bitstream_sha256')==q['bitstream_sha256'],
                'Reference was not a successful stopped preflight')
        digest=hashlib.sha256(json.dumps(owner,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        require(q['status']=='FAIL' and owner.get('passed') is False
                and digest==DDR59_REFERENCE['owner_audit_sha256'],
                'DDR5.9 reference owner finding differs from the recorded observation')
        require(q['minimum_slack_ns']>=0 and q['minimum_pulse_slack_ns']>=0
                and q['violated_endpoints']==dict(setup=0,hold=0)
                and all(value>=0 for value in q['timing_checks_ns'].values()),
                'DDR5.9 reference restoration does not waive timing failures')
        require(all(a.get('passed') is True for name,a in q['synthesis_audits'].items()
                    if name!='gpu_owner_replication'),
                'DDR5.9 reference restoration does not waive other synthesis audits')
        require(q.get('ddr_profile',{}).get('passed') is True
                and q['ddr_profile'].get('variant')=='neo-fifo-registers'
                and q.get('clock_mhz',{}).get('ddr3_mem_clk')==300.03
                and q['clock_mhz'].get('ddr3_sys_clk')==75.002,
                'DDR5.9 reference profile or clocks differ')
        return q,bit
    require(owner.get('passed') is True,
            'Re-run qualification: routed GPU-owner replication must preserve its register function')
    recovery_experiment=diagnostic_recovery_min_ns is not None
    if recovery_experiment:
        require(diagnostic_bitstream is not None and preflight_only and not diagnostic_gpu_routing,
                'Recovery experiment requires exact diagnostic SHA and preflight-only, without routing waivers')
        require(math.isfinite(diagnostic_recovery_min_ns) and diagnostic_recovery_min_ns<0,
                'Recovery experiment requires a finite negative slack floor')
        require(diagnostic_recovery_min_ns<=q['timing_checks_ns']['recovery']<0,
                'Recovery slack is outside the explicitly requested experiment')
    if diagnostic_bitstream is None:
        require(not diagnostic_gpu_routing,'Routing observation requires an exact diagnostic bitstream')
        require(q['status']=='PASS','Unqualified FPGA')
    else:
        require(diagnostic_bitstream==q['bitstream_sha256'],'Diagnostic bitstream hash differs')
        setup_failure=(q['minimum_slack_ns']<0 and q['violated_endpoints']['setup']>0
                       and q['timing_checks_ns']['setup']<0)
        routing_only=(diagnostic_gpu_routing and q['minimum_slack_ns']>=0
                      and q['violated_endpoints']['setup']==0
                      and q['timing_checks_ns']['setup']>=0
                      and any(routing_observation_only(name,a)
                              for name,a in q.get('synthesis_audits',{}).items()))
        require(q['status']=='FAIL' and (setup_failure or routing_only),
                'Diagnostic requires a recorded setup failure or explicit routing-only observation')
        require(q['violated_endpoints']['hold']==0 and q['minimum_pulse_slack_ns']>=0,
                'Diagnostic mode does not waive hold or pulse failures')
        require(set(q.get('timing_checks_ns',{}))=={'setup','hold','recovery','removal'} and
                all(q['timing_checks_ns'][kind]>=0 for kind in ('hold','removal')) and
                (q['timing_checks_ns']['recovery']>=0 or recovery_experiment),
                'Diagnostic mode does not waive reset recovery/removal; complete checks required')
        require(q.get('synthesis_audits') and
                all(a.get('passed') is True or (diagnostic_gpu_routing and routing_observation_only(name,a))
                    for name,a in q['synthesis_audits'].items()),
                'Diagnostic mode does not waive synthesis audits')
        require(q.get('ddr_profile',{}).get('passed') is True,
                'Diagnostic mode requires the frozen DDR profile')
    return q,bit
def recovery_commands(previous):
    """Match a saved stopped loader and its live PC; never assume Linux is idle."""
    failed=json.loads((previous/'result.json').read_text())
    diagnostic=(failed.get('passed') is True and failed.get('run_mode')=='preflight_only'
                and failed.get('cpu_left_halted') is True and failed.get('load_error') is None
                and failed.get('recovery_state')=='parked_after_preflight')
    require((failed.get('passed') is False or diagnostic) and failed.get('sd_written') is False
            and failed.get('flash_written') is False,
            'Recovery requires a saved stopped diagnostic/load without SD/flash writes')
    common=['init','halt','riscv set_enable_virt2phys off']
    if not diagnostic and b'LINUX FAIL compact transport' in (previous/'console.log').read_bytes():
        checks=[
            'if {[lindex [reg pc] 2] != 0xa00001e8 || [lindex [reg priv] 2] != 3} {error "Not the failed ILM launcher"}',
            'if {([lindex [read_memory 0xa00001e8 32 1] 0] & 0xffff) != 0xa001} {error "Failed loop fingerprint differs"}']
    else:
        log=(previous/'openocd.log').read_text()
        completed=(diagnostic and 'NEO_PREFLIGHT_ONLY_COMPLETE' in log and 'NEO_PAYLOAD_BEGIN' not in log)
        rejected=(failed.get('recovery_state')=='parked_before_resume' and failed.get('load_error'))
        require((completed or rejected) and 'NEO_MEMORY_PREFLIGHT_BEGIN' in log
                and 'NEO_LAUNCH_BEGIN' not in log,
                'Saved load does not prove a failure before CPU resume')
        checks=[
            'set pc [lindex [reg pc] 2]',
            'if {($pc != 0x80000000 && $pc != 0x80000004) || [lindex [reg priv] 2] != 3} {error "CPU is not in the boot parking loop"}',
            'set parking [read_memory 0x80000000 32 2]',
            'if {[lindex $parking 0] != 0x10500073 || [lindex $parking 1] != 0xffdff06f} {error "Boot parking fingerprint differs"}']
    return common+checks+['echo NEO_FAILED_LAUNCHER_CONFIRMED','shutdown','']

def unexamined_preflight(previous):
    """Recognize a just-programmed SRAM diagnostic that never reached AE350.

    There is no live CPU fingerprint when TAP reads all zeroes. This narrow
    recovery instead requires the prior live quiescence guard, successful
    SRAM programming, a preflight-only script and no target examination or
    payload execution. It is never an entry from an arbitrary running OS.
    """
    result=json.loads((previous/'result.json').read_text())
    require(result.get('passed') is False and result.get('run_mode')=='preflight_only'
            and result.get('load_error') and result.get('sd_written') is False
            and result.get('flash_written') is False,'Not a failed preflight-only load')
    require('NEO_FAILED_LAUNCHER_CONFIRMED' in (previous/'recovery.log').read_text(),
            'Previous load did not verify a stopped CPU before programming')
    qualification=json.loads((previous/'qualification_used.json').read_text())
    require(qualification['bitstream_sha256']==result['bitstream_sha256'],
            'Failed preflight bitstream identity differs')
    script=(previous/'load.tcl').read_text()
    require('NEO_PREFLIGHT_ONLY_COMPLETE' in script and 'NEO_PAYLOAD_BEGIN' not in script
            and not re.search(r'^\s*resume\b',script,re.M),'Previous script could resume a payload')
    log=(previous/'openocd.log').read_text()
    require('JTAG scan chain interrogation failed: all zeroes' in log
            and 'Target not examined yet' in log
            and all(marker not in log for marker in
                    ('Target successfully examined','NEO_MEMORY_PREFLIGHT_BEGIN','NEO_PAYLOAD_BEGIN','NEO_LAUNCH_BEGIN')),
            'Failure was not confined to initial TAP examination')
    status=check_program_status((previous/'program.log').read_text())
    recorded=json.loads((previous/'program_status.json').read_text())
    require(all(recorded.get(k)==v for k,v in status.items()),'Previous programming record differs')
    return dict(previous=str(previous),bitstream_sha256=result['bitstream_sha256'],
                live_cpu_observation=False,reason='Quiesced SRAM diagnostic failed before AE350 examination')
def stop_after_preflight(script):
    """Cut at the explicit payload boundary, keeping the CPU halted."""
    boundary='echo NEO_PAYLOAD_BEGIN\n'
    require(script.count(boundary)==1,'Missing/ambiguous payload boundary')
    prefix=script.split(boundary)[0]
    require('echo NEO_MEMORY_PREFLIGHT_BEGIN\n' in prefix
            and 'echo NEO_GPU_PREFLIGHT_OK\n' in prefix
            and not re.search(r'^\s*resume\b',prefix,re.M),'Unsafe preflight script')
    return prefix+'echo NEO_PREFLIGHT_ONLY_COMPLETE\nshutdown\n'
def analyser_diagnostic_commands(previous):
    """Recognize the completed L31r8 DDR test; never halt an unknown OS.

    This entry is intentionally restricted to the retained version-1 test
    executable and its terminal loop. It neither loads nor runs that test.
    """
    previous=Path(previous).resolve()
    require(not any(c in str(previous) for c in '{}\\\r\n'), 'Unsafe diagnostic path')
    record=json.loads((previous/'result.json').read_text())
    require(record.get('passed') is True and record.get('cpu_left_halted') is True
            and record.get('flash_changed') is False and record.get('sd_changed') is False,
            'Expected a completed analyser DDR test without storage writes')
    require(record.get('bitstream_sha256')==ANALYSER_L31R8_SHA256
            and record.get('diagnostic_sha256')==ANALYSER_DDR_DIAGNOSTIC_SHA256
            and sha(previous/'ddr_diag.elf')==ANALYSER_DDR_DIAGNOSTIC_SHA256,
            'Unknown analyser DDR diagnostic')
    raw=(previous/'results.bin').read_bytes()
    require(len(raw)==2048,'Incomplete analyser DDR results')
    r=struct.unpack('<512I',raw)
    require(r[:3]==(0x44445254,1,2) and r[6]==0 and r[18]==9
            and r[19]==0x40000000 and r[8]&3==0 and r[15:18]==(0,0,0)
            and all(r[32+i*4]==0 and r[35+i*4]==0x444f4e45 for i in range(9)),
            'Analyser diagnostic did not complete successfully')
    require(r[10]==record.get('checks')==record.get('expected_checks')
            and r[11]==record.get('writes')==record.get('expected_writes')
            and record.get('status')==2 and record.get('errors')==0
            and record.get('stages_completed')==9,
            'Inconsistent analyser DDR result record')
    return ['init','poll',
        'if {[nds.cpu curstate] ne "halted"} {error "Analyser CPU is not already halted"}',
        'if {[lindex [reg priv] 2] != 3 || [lindex [reg satp] 2] != 0} {error "Not the standalone DDR diagnostic"}',
        'set pc [lindex [reg pc] 2]',
        'if {$pc != 0xa000086a && $pc != 0xa000086c && $pc != 0xa000086e} {error "Not the DDR diagnostic terminal loop"}',
        'riscv set_enable_virt2phys off',
        f'verify_image {{{previous/"ddr_diag.elf"}}}',
        f'verify_image {{{previous/"results.bin"}}} 0xa0201000 bin',
        'echo NEO_ANALYSER_DDR_DIAGNOSTIC_CONFIRMED','shutdown','']
def collect(port,seconds):
    data=bytearray();deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:data.extend(port.read(4096))
    return bytes(data)

def check_program_status(log):
    """Check the reported GW5AST final status, not only the process exit code.

    openFPGALoader 1.1.1 skips its software checksum comparison for GW5 and
    programSRAM can return after a false writeSRAM result without throwing.
    This checks DONE and the reported error flags; it is not SRAM readback.
    """
    values=re.findall(r'^after program sram: displayReadReg ([0-9a-fA-F]{8})\s*$',log,re.M)
    require(len(values)==1,'Missing or ambiguous final FPGA configuration status')
    value=int(values[0],16)
    names={0:'crc_error',1:'bad_command',2:'id_verify_failed',3:'timeout',
           19:'crc_comparison_error',21:'serial_ecc_uncorrectable'}
    errors=[name for bit,name in names.items() if value&(1<<bit)]
    require(bool(value&(1<<13)),'FPGA configuration DONE is not asserted')
    require(not errors,'FPGA configuration error flags: '+', '.join(errors))
    require(not re.search(r'\bFAIL\b',log),'Programmer reported a failed operation')
    return dict(raw_status=f'0x{value:08x}',done=True,error_flags=errors,
                sram_readback_verified=False,
                software_checksum_verified=False)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True)
    p.add_argument('--pack',type=Path,default=ROOT/'linux/build-neo');p.add_argument('--out',type=Path,required=True)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--already-programmed',action='store_true')
    mode.add_argument('--recover-failed-load',type=Path,
                      help='Saved failed load; verify its live ILM/boot loop before reprogramming SRAM')
    mode.add_argument('--recover-unexamined-preflight',type=Path,
                      help='Recover a quiesced, programmed preflight whose AE350 TAP stayed all zeroes; preflight-only required')
    mode.add_argument('--after-analyser-ddr-test',type=Path,
                      help='Completed L31r8 version-1 DDR test; verify halted CPU, ILM code and DTCM results before SRAM loading')
    p.add_argument('--diagnostic-bitstream', metavar='SHA256',
                   help='Exact diagnostic bitstream: permit setup failure or explicit GPU routing observation; keep qualification FAIL')
    p.add_argument('--preflight-only', action='store_true',
                   help='Test memory/GPU then remain halted; do not transfer the Linux payload or start it')
    p.add_argument('--diagnostic-gpu-routing',action='store_true',
                   help='Observe known LW reset labels with exact diagnostic SHA and --preflight-only; never qualify or boot Linux')
    p.add_argument('--diagnostic-recovery-min-ns',type=float,
                   help='User-requested recovery experiment: explicit negative slack floor, exact diagnostic SHA and preflight-only; never qualify or boot Linux')
    p.add_argument('--restore-ddr59-reference',type=Path,metavar='SAVED_PREFLIGHT',
                   help='Restore exact N38 DDR5.9/300 MHz reference from pinned successful preflight evidence; preflight-only, qualification stays FAIL')
    p.add_argument('--jtag-frequency',type=int,choices=(1000000,6000000),default=6000000,
                   help='SRAM programming TCK only; never changes FPGA operating clocks')
    p.add_argument('--preserve-uart-route',action='store_true',
                   help='Keep the debugger UART route after a cold start; do not enter its CLI (the relay may become silent)')
    a=p.parse_args()
    if a.restore_ddr59_reference is not None and not (
            a.preflight_only and a.diagnostic_bitstream is None
            and not a.diagnostic_gpu_routing and a.diagnostic_recovery_min_ns is None):
        p.error('DDR5.9 reference restoration requires --preflight-only and no other diagnostic waiver')
    if a.diagnostic_gpu_routing and not (a.diagnostic_bitstream and a.preflight_only):
        p.error('GPU routing observation requires --diagnostic-bitstream SHA256 and --preflight-only')
    if a.recover_unexamined_preflight and not a.preflight_only:
        p.error('Unexamined preflight recovery requires --preflight-only')
    if a.diagnostic_recovery_min_ns is not None and not (
            a.diagnostic_bitstream and a.preflight_only and not a.diagnostic_gpu_routing
            and math.isfinite(a.diagnostic_recovery_min_ns) and a.diagnostic_recovery_min_ns<0):
        p.error('Recovery experiment requires a finite negative floor, exact diagnostic SHA, preflight-only and no routing waiver')
    # Hold through programming and the final OpenOCD exit: a second loader
    # must never reconfigure the FPGA while the first is still examining it.
    with (ROOT/'TESTS/neo_board.lock').open('a') as board_lock:
        fcntl.flock(board_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        load(a)

def load(a):
    build=a.build.resolve();pack=a.pack.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    if a.diagnostic_bitstream or a.restore_ddr59_reference is not None:
        # Re-run every normal structural/source/constraint check. A failure
        # before the checker emits its complete JSON cannot use a stale file.
        checked=subprocess.run(['python3',str(ROOT/'tools/check_neo_timing.py'),str(build)],
                               capture_output=True,text=True,timeout=120)
        (out/'diagnostic_qualification.log').write_text(checked.stdout+checked.stderr)
        require(checked.returncode==1,'Diagnostic needs a completed failing qualification')
        require(json.loads(checked.stdout)==json.loads((build/'qualification.json').read_text()),
                'Incomplete diagnostic qualification')
    q,bit=check_fpga(build,a.diagnostic_bitstream,a.diagnostic_gpu_routing,
                     diagnostic_recovery_min_ns=a.diagnostic_recovery_min_ns,
                     preflight_only=a.preflight_only,
                     restore_ddr59_reference=a.restore_ddr59_reference)
    qualification_mode=(('diagnostic_reset_routing' if q['timing_checks_ns']['setup']>=0 else
                         'diagnostic_setup_and_reset_routing') if a.diagnostic_gpu_routing else
                        'diagnostic_setup_violation' if a.diagnostic_bitstream else 'qualified')
    if a.diagnostic_recovery_min_ns is not None:
        qualification_mode='diagnostic_setup_and_recovery_violation'
    reference_observation=None
    if a.restore_ddr59_reference is not None:
        qualification_mode='diagnostic_ddr59_reference'
        reference_observation=dict(proof=str(a.restore_ddr59_reference.resolve()),
            proof_sha256=DDR59_REFERENCE['proof_sha256'],
            owner_finding=q['synthesis_audits']['gpu_owner_replication'])
    (out/'qualification_used.json').write_text(json.dumps(dict(mode=qualification_mode,
        status=q['status'],bitstream_sha256=q['bitstream_sha256'],timing_sha256=q['timing_sha256'],
        minimum_slack_ns=q['minimum_slack_ns'],violated_endpoints=q['violated_endpoints'],
        timing_checks_ns=q['timing_checks_ns'],
        diagnostic_recovery_min_ns=a.diagnostic_recovery_min_ns,
        ddr59_reference=reference_observation,
        routing_observations={k:v['errors'] for k,v in q.get('synthesis_audits',{}).items()
                              if a.diagnostic_gpu_routing and routing_observation_only(k,v)}),indent=2)+'\n')
    require(q.get('features',{}).get('soft_usb_hs') and q.get('features',{}).get('gamepads'),'Current Neo Linux requires SOFT-USB and two gamepad ports')
    require(sha(build/'impl/pnr/console_neo.tr')==q['timing_sha256'],'Changed timing report')
    m=json.loads((pack/'manifest.json').read_text());require(m.get('profile')=='neo' and m['abi']==1,'Wrong Linux target')
    for rel,meta in m['files'].items():
        f=pack/rel;require(f.stat().st_size==meta['bytes'] and sha(f)==meta['sha256'],'Changed package '+rel)
    launch=pack/'launch_packed.bin';lm=m['launcher_packed'];download=pack/'payload.rle.bin'
    require(lm['load']==0xa0000000 and lm['entry']==0xa000000c and lm['stage']==0x10000000,'Wrong launcher addresses')
    require(m['load']==m['entry']==0x07c00000 and m['kernel']==0x08000000,'Wrong payload addresses')
    require(12 < launch.stat().st_size <= 65536,'Launcher exceeds ILM')
    require(0 < download.stat().st_size <= 0x02000000,'Packed payload too large')
    require(m['files']['opensbi/platform/generic/firmware/fw_payload.bin']['bytes'] <= 0x02000000,'Decoded payload too large')
    require(launch.stat().st_size==lm['bytes'] and sha(launch)==lm['sha256'],'Changed launcher')
    devices=[]
    for d in Path('/sys/bus/usb/devices').iterdir():
        if (d/'serial').exists() and (d/'serial').read_text().strip()=='2025041420':
            require((d/'idVendor').read_text().strip()=='0403' and (d/'idProduct').read_text().strip()=='6010','Unexpected programmer')
            devices.append(d)
    require(len(devices)==1,'Expected exactly one Sipeed programmer 2025041420')
    probes=[d for d in Path('/sys/bus/usb/devices').iterdir()
            if (d/'product').exists() and (d/'product').read_text().strip()=='Dual RS232-HS'
            and (d/'idVendor').read_text().strip()=='0403'
            and (d/'idProduct').read_text().strip()=='6010']
    require(len(probes)==1,'Expected exactly one ESP-Prog matching the AE350 JTAG configuration')
    busdev=':'.join((devices[0]/n).read_text().strip() for n in ['busnum','devnum'])
    if not a.already_programmed:
        if a.after_analyser_ddr_test:
            # Freeze the evidence before constructing the live read-only guard.
            analyser_diagnostic_commands(a.after_analyser_ddr_test)
            reference=out/'analyser_ddr_reference';reference.mkdir()
            for name in ('result.json','ddr_diag.elf','results.bin'):
                (reference/name).write_bytes((a.after_analyser_ddr_test/name).read_bytes())
            guard=out/'analyser_guard.tcl'
            guard.write_text('\n'.join(analyser_diagnostic_commands(reference)))
            with (out/'analyser_guard.log').open('w') as log:
                subprocess.run(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
                    '-c','gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(guard)],
                    stdout=log,stderr=subprocess.STDOUT,check=True,timeout=30)
            require('NEO_ANALYSER_DDR_DIAGNOSTIC_CONFIRMED' in (out/'analyser_guard.log').read_text(),
                    'Live analyser DDR diagnostic check did not complete')
        elif a.recover_unexamined_preflight:
            record=unexamined_preflight(a.recover_unexamined_preflight)
            (out/'unexamined_recovery.json').write_text(json.dumps(record,indent=2)+'\n')
        elif a.recover_failed_load:
            guard=out/'recovery.tcl'
            guard.write_text('\n'.join(recovery_commands(a.recover_failed_load)))
            with (out/'recovery.log').open('w') as log:
                subprocess.run(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
                    '-c','gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(guard)],
                    stdout=log,stderr=subprocess.STDOUT,check=True,timeout=30)
            require('NEO_FAILED_LAUNCHER_CONFIRMED' in (out/'recovery.log').read_text(),
                    'Live failed-launcher check did not complete')
        else:
            with serial.Serial(UART,2000000,timeout=.1,exclusive=True) as port:
                port.write(b'\x03');collect(port,.3)
                port.write(b'sync; umount /mnt/sd 2>/dev/null; cat /proc/mounts; echo NEO_QUIESCED\r')
                before=collect(port,3);(out/'before.log').write_bytes(before)
                require(b'\nNEO_QUIESCED\n' in before.replace(b'\r',b''),'Existing Linux shell did not acknowledge quiescence')
                require(not re.search(rb'^/dev/mmc\S*\s',before,re.M),'SD remains mounted')
        with (out/'program.log').open('w') as log:
            subprocess.run([str(Path.home()/'.local/bin/openFPGALoader'),'--busdev-num',busdev,'-b','tangconsole','-m','--verbose','--freq',str(a.jtag_frequency),str(bit)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        status=check_program_status((out/'program.log').read_text())
        status['requested_jtag_frequency_hz']=a.jtag_frequency
        (out/'program_status.json').write_text(json.dumps(status,indent=2)+'\n')
        print('Neo FPGA loaded into SRAM',flush=True)
    # Disable translations/caches before physical JTAG writes. The ordinary
    # console ILM startup initializes PMP/cache attributes and checks CRCs.
    rng=random.Random(138)
    words=([0,0xffffffff,0xaaaaaaaa,0x55555555]*64 +
           [1<<i for i in range(32)]*8 + [rng.getrandbits(32) for _ in range(512)])
    pattern=out/'memory_pattern.bin';pattern.write_bytes(struct.pack('<1024I',*words))
    preflight=[]
    # Test both ends of the actual transport span before a long transfer.
    # ILM is the control; all three regions are overwritten by this load.
    for addr in (0xa0000000,0x10000000,0x10000000+(download.stat().st_size-1)//4096*4096):
        preflight.append(f'load_image {{{pattern}}} {addr:#x} bin')
        for attempt in range(2):
            preflight.append(f'verify_image {{{pattern}}} {addr:#x} bin')
        preflight.append(f'echo "NEO_MEMORY_PREFLIGHT_OK {addr:#x}"')
    # TARGET changes only the GPU target registers. It exercises the command
    # FIFO and completion crossing without starting DMA or touching scanout.
    # A known-stalled GPU must be diagnosed before transferring the kernel.
    preflight += [
        'if {[lindex [read_memory 0xe9001000 32 1] 0] != 0x424c5432} {error "Wrong GPU command ABI"}',
        'set done_before [expr {[lindex [read_memory 0xe9001008 32 1] 0] & 0xffff}]',
        *gpu_error_guard_before()]
    preflight += [f'write_memory 0xe9001010 32 {{{word:#x}}}' for word in
                  [22<<24,0x12000000,0x12001000,(32<<16)|64,(64<<16)|64,0,0,0]]
    preflight += [
        'sleep 20',
        'echo "NEO_GPU_PREFLIGHT_STATUS [read_memory 0xe9001000 32 18]"',
        'if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) != (($done_before+1)&0xffff)} {error "GPU preflight command did not complete"}',
        *gpu_error_guard_after(),
        'echo NEO_GPU_PREFLIGHT_OK',
        'echo "NEO_USB_PREFLIGHT_STATUS [read_memory 0xe9003000 32 2]"']
    tcl=out/'load.tcl'
    tcl.write_text('\n'.join(['riscv expose_csrs 1994,1996,2000','init','halt','riscv set_enable_virt2phys off',
        'reg priv 3','reg satp 0','reg mstatus 0','reg mie 0','reg csr1996 6','reg csr1994 0',
        'set geometry [read_memory 0xe9000070 32 2]',
        'if {[lindex $geometry 0] != 0x02d00500 || [lindex $geometry 1] != 0x02ee0672} {error "Wrong live GPU geometry"}',
        'set parking [read_memory 0x80000000 32 2]',
        'if {[lindex $parking 0] != 0x10500073 || [lindex $parking 1] != 0xffdff06f} {error "Boot RAM initialization mismatch"}',
        'set pads [read_memory 0xe9004000 32 2]',
        'if {[lindex $pads 0] != 0x4e504144 || [lindex $pads 1] != 0x00010002} { error "Wrong Neo gamepad ABI" }',
        'set usb [read_memory 0xe9003000 32 1]',
        'if {[lindex $usb 0] != 0x554d5343} { error "Missing SOFT-USB MMIO" }',
        'echo "NEO_GEOMETRY_AND_BOOT_RAM_OK"',
        'echo NEO_MEMORY_PREFLIGHT_BEGIN']+preflight+[
        'echo NEO_PAYLOAD_BEGIN',
        f'load_image {{{download}}} 0x10000000 bin',
        'echo "NEO_TRANSPORT_HEADER [read_memory 0x10000000 32 8]"',
        f'verify_image {{{download}}} 0x10000000 bin',
        f'load_image {{{launch}}} 0xa0000000 bin',f'verify_image {{{launch}}} 0xa0000000 bin',
        'echo "NEO_PAD0_BEFORE [read_memory 0xe9004020 32 5]"',
        'echo "NEO_PAD1_BEFORE [read_memory 0xe9004040 32 5]"',
        'sleep 200',
        'echo "NEO_PAD0_AFTER [read_memory 0xe9004020 32 5]"',
        'echo "NEO_PAD1_AFTER [read_memory 0xe9004040 32 5]"',
        'reg a0 0','reg a1 0','reg a2 0','echo NEO_LAUNCH_BEGIN',
        'resume 0xa000000c','shutdown','']))
    if a.preflight_only:
        tcl.write_text(stop_after_preflight(tcl.read_text()))
    stop=threading.Event();received=bytearray();errors=[];start=time.monotonic();load_error=None
    with serial.Serial(UART,2000000,timeout=.1,exclusive=True) as port:
        if a.preserve_uart_route:
            (out/'relay.log').write_text('UART route preserved; no debugger CLI commands sent. Host rate: 2000000 8N1.\n')
        else:
            (out/'relay.log').write_bytes(select_relay(port,2000000))
        with (out/'console.log').open('wb',buffering=0) as log:
            def read():
                try:
                    while not stop.is_set():
                        data=port.read(4096);received.extend(data);log.write(data)
                except Exception as e:errors.append(str(e))
            reader=threading.Thread(target=read);reader.start()
            try:
                print('Checking Neo preflight only...' if a.preflight_only else
                      'Loading compact Linux payload through ESP-Prog...',flush=True)
                with (out/'openocd.log').open('w') as f:
                    subprocess.run(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),'-c','gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(tcl)],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1200)
                deadline=time.monotonic()+120
                while not a.preflight_only and time.monotonic()<deadline and b'PRODOCK_LINUX_READY' not in received and b'LINUX FAIL' not in received and b'Kernel panic' not in received:time.sleep(.2)
            except (OSError,subprocess.SubprocessError) as e:load_error=str(e)
            finally:stop.set();reader.join(2)
    ok=b'PRODOCK_LINUX_READY' in received and b'CRC OK' in received and b'Linux version' in received and not errors and load_error is None
    # The autonomous hosts keep polling while the CPU is halted for loading.
    # Capture their actual wire identity/counters without requiring a button
    # press or changing CPU state again after Linux has started.
    pads={}
    jtag_log=(out/'openocd.log').read_text()
    if a.preflight_only:
        ok=(load_error is None and not errors and 'NEO_PREFLIGHT_ONLY_COMPLETE' in jtag_log
            and 'NEO_PAYLOAD_BEGIN' not in jtag_log and 'NEO_LAUNCH_BEGIN' not in jtag_log)
    for port,when,words in re.findall(r'^NEO_PAD([01])_(BEFORE|AFTER) (.+)$',
                                     jtag_log,re.M):
        values=[int(v,0) for v in words.split()]
        require(len(values)==5,'Incomplete gamepad MMIO snapshot')
        pads.setdefault(port,{})[when.lower()]=values
    recovery_state=('parked_before_resume' if load_error and 'NEO_MEMORY_PREFLIGHT_BEGIN' in jtag_log
                    and 'NEO_LAUNCH_BEGIN' not in jtag_log else None)
    if a.preflight_only and ok:
        recovery_state='parked_after_preflight'
    (out/'result.json').write_text(json.dumps(dict(passed=ok,qualification_mode=qualification_mode,
        uart_route='preserved' if a.preserve_uart_route else 'selected_by_debugger_cli',
        diagnostic_recovery_min_ns=a.diagnostic_recovery_min_ns,
        ddr59_reference=reference_observation,
        run_mode='preflight_only' if a.preflight_only else 'linux',cpu_left_halted=(a.preflight_only if ok else None),
        qualification_status=q['status'],seconds=time.monotonic()-start,reader_errors=errors,load_error=load_error,recovery_state=recovery_state,bitstream_sha256=sha(bit),manifest=m,gamepad_snapshots=pads,sd_written=False,flash_written=False),indent=2)+'\n')
    print(received.decode(errors='replace'),flush=True)
    require(ok,'Preflight failed; inspect saved logs' if a.preflight_only else 'Boot not confirmed; inspect saved logs')
    if a.preflight_only:print('Neo preflight passed; CPU remains halted, Linux not started.',flush=True)
if __name__=='__main__':main()
