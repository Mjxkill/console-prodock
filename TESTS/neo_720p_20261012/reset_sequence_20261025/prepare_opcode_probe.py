#!/usr/bin/env python3
"""One R17 observation candidate: R15 application, 32 GAO signals, no hardware."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
import prepare_pixel_probe as prior

HERE, ROOT, PARENT = prior.HERE, prior.ROOT, prior.PARENT
OUT = ROOT/'tang/impl/console_neo_n56r17_gao_opcode'
GAO_ID = '0101011010110001'
sha, manifest = prior.sha, prior.manifest
CONTROL_NAMES = ('pixel_capture_enable', 'pixel_reset_active_high', 'shader_start',
    'shader_done', 'pixel_idle', 'pixel_bad', 'pixel_finish', 'pixel_decode_wait',
    'pixel_decode', 'geometry_wait_pixels')


def probes(text):
    full = prior.probes(text)  # Recheck the real D/CE/reset pins and aliases.
    m = {stage:{bit:net for bit,net in full[stage].items() if int(bit)>=24}
         for stage in ('geometry_header','actual_pixel_D','pixel_Q')}
    m['controls'] = {key:full['controls'][key] for key in CONTROL_NAMES}
    m['unique_signals'] = list(dict.fromkeys(net for group in m.values() for net in group.values()))
    assert len(m['unique_signals']) == 32
    assert set(m['unique_signals']) < set(full['unique_signals'])
    return m


def prepare():
    prior.preflight()
    contract = prior.before_build('neo', candidate=True)
    failure = HERE/'r16_route_failure_01/result.json'
    failed = json.loads(failure.read_text())
    assert failed['route']['status']=='ROUTING_FAILED' and failed['application_cells_identical']
    evidence = HERE/'opcode_trace_check_01/result.json'
    tested = json.loads(evidence.read_text())
    assert tested['passed'] and tested['captures']==16
    for path,digest in tested['inputs'].items(): assert sha(Path(path))==digest, path
    assert tested['mapping']==probes((PARENT/'console_neo.vg').read_text())
    OUT.mkdir(exist_ok=False)
    shutil.copytree(PARENT/'source', OUT/'source')
    for name in ('console_neo.vg','font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex'):
        (OUT/name).parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(PARENT/name, OUT/name)
    config = ET.parse(prior.OUT/'source/tang/boards/neo/pixel_capture.gao').getroot()
    core = config.find('AoCore')
    assert core.attrib['sample_clock']=='gpu_clk' and core.attrib['storage_depth']=='512'
    m = tested['mapping']
    signals = core.find('SignalList')
    signals.clear()
    for net in m['unique_signals']: ET.SubElement(signals,'Signal',capture_enable='true').text=net
    config.find('GAO_ID').text=GAO_ID
    ET.indent(config,space='    ')
    (OUT/'source/tang/boards/neo/opcode_capture.gao').write_bytes(
        ET.tostring(config,encoding='utf-8',xml_declaration=True)+b'\n')
    current = manifest(OUT/'source')
    original = json.loads((PARENT/'sources.json').read_text())
    assert {k:v for k,v in current.items() if k in original}==original
    assert set(current)-set(original)=={'tang/boards/neo/opcode_capture.gao'}
    (OUT/'sources.json').write_text(json.dumps(current,indent=2)+'\n')
    tcl = (PARENT/'build.tcl').read_text().replace(str(PARENT),str(OUT))
    assert tcl.count('/reset_trial.gao}')==1
    tcl = tcl.replace('/reset_trial.gao}', '/opcode_capture.gao}')
    (OUT/'build.tcl').write_text(tcl)
    prior.record_build(OUT,contract)
    record = dict(candidate=True, qualification='PENDING', hardware_access=False, loaded=False,
        parent=str(PARENT), parent_bitstream_sha256=prior.BIT_SHA,
        same_application_netlist=sha(OUT/'console_neo.vg')==sha(PARENT/'console_neo.vg'),
        source_change='GAO configuration only: 32 probes; same R15 application, DDR 5.9/300 MHz, PLL, reset 50 ms, CST, SDC and PNR options',
        comparison_with_r16='Only the sampled signal subset and the GAO identity change; same clock, depth, trigger and capture settings',
        rationale='Observe opcode bits [31:24] at geometry Q, actual pixel D and pixel Q, with the capture controls and decode states. Smaller observation cone after four unrouted GAO nets; not proof of congestion cause.',
        mapping=m, observed_mask='0xff000000', gao_id=GAO_ID,
        limits=['Bits [23:0] and payload are not observed by GAO; complete captured headers remain readable over AHB.',
                'Four R16 unrouted nets are still unnamed; reducing probes is a targeted observation experiment, not a demonstrated router fix.',
                'Sample at the GPU clock assumes aligned pre-edge samples; no subcycle glitch/metastability conclusion.',
                'New instrumentation changes placement/routes; reproduce the GPU failure before attributing its cause.'],
        evidence={str(p):sha(p) for p in (failure,evidence,Path(__file__),HERE/'prepare_pixel_probe.py',HERE/'opcode_trace.py')},
        inputs={name:sha(OUT/name) for name in ('console_neo.vg','sources.json','build.tcl',
            'source/tang/boards/neo/neo.cst','source/tang/boards/neo/neo.sdc','source/tang/boards/neo/opcode_capture.gao',
            'font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex')})
    assert record['same_application_netlist']
    (OUT/'observation_preparation.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(prepared=str(OUT),signals=32,same_netlist=True,hardware_access=False)),flush=True)


def route():
    prior.preflight()
    contract=prior.before_build('neo',candidate=True)
    r=json.loads((OUT/'observation_preparation.json').read_text())
    for name,digest in r['inputs'].items(): assert sha(OUT/name)==digest,name
    for path,digest in r['evidence'].items(): assert sha(Path(path))==digest,path
    assert manifest(OUT/'source')==json.loads((OUT/'sources.json').read_text())
    assert sha(OUT/'console_neo.vg')==sha(PARENT/'console_neo.vg')
    with (OUT/'route.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        assert not (OUT/'route_launch.json').exists(), 'One attempt per candidate'
        prior.record_build(OUT,contract)
        tool=PARENT/'public_license_runtime/bin/gw_sh'
        assert sha(tool)==sha(prior.IDE/'bin/gw_sh')
        started=time.time()
        with (OUT/'build.log').open('x') as log:
            child=subprocess.Popen([str(tool),'build.tcl'],cwd=OUT,env=prior.environment(),stdout=log,stderr=log)
            (OUT/'route_launch.json').write_text(json.dumps(dict(pid=child.pid,started_unix=started,
                tool=str(tool),tool_sha256=sha(tool),candidate=str(OUT),loaded=False),indent=2)+'\n')
            print('R17_OPCODE_ROUTE_STARTED pid='+str(child.pid),flush=True)
            rc=child.wait()
        log=(OUT/'build.log').read_text()
        passed=rc==0 and not re.search(r'^ERROR',log,re.M) and 'Bitstream generation completed' in log
        (OUT/'route_result.json').write_text(json.dumps(dict(returncode=rc,
            status='ROUTED_NOT_QUALIFIED' if passed else 'ROUTING_FAILED',started_unix=started,
            finished_unix=time.time(),loaded=False),indent=2)+'\n')
        if not passed: raise SystemExit('R17 route failed; evidence retained')
        print('R17 complete; output audit, timing and hardware validation pending',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--route',action='store_true')
    a=p.parse_args()
    route() if a.route else prepare()
