#!/usr/bin/env python3
"""Bounded Neo D* diagnostic. Requires an exact post-route review before access."""
import argparse
import fcntl
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import re
import shutil
import signal
import struct
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = HERE.parent / 'local_capture_20261026'
sys.path.insert(0, str(HERE.parent/'reset_sequence_20261025'))
sys.path.insert(0, str(OLD))
from board_trial_r19 import BASE_GUARD, DISABLED, DEST as R19, BIT_SHA as R19_SHA, hw
from framebuffer_trial import CACHE
from isolate_r19_clear import ARM, CAPTURE, PACKET
from observe_r19_clear import SNAPSHOT
from z_cpu_probe_r19 import CSRS, UNCACHED

# The old trial modules import the C1 decoder. Load D* under a distinct name.
spec = importlib.util.spec_from_file_location('decode_memory_capture', HERE/'decode_capture.py')
decoder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decoder)
assert Path(sys.modules['decode_capture'].__file__).resolve().parent == OLD
assert list(inspect.signature(decoder.decode).parameters) == ['value','epoch','expected_width']

ANCHOR = OLD/'r19_copy_20261027_000303/result.json'
ANCHOR_SHA = '22f897d6eb2fb971dfaed5da50b083cf8c39ba24aa24bd5348338f3e202bf187'
NETLIST_SHA = 'd773dca99127093b27e713f195b9ff62207c01a7810130c55d5d99499700d4cc'
COLOR, SOURCE, DEPTH = 0x00800020, 0x00808000, 0x00810000
TARGET = [22 << 24, COLOR, DEPTH, (128 << 16) | 16, (256 << 16) | 256, 0, 0, 0]
CASES = [
    ('COPY16', [29 << 24, SOURCE, (16 << 16) | 1, 32, 0, 0, (16 << 16) | 1, 0]),
    ('CLEAR_COLOR16', [28 << 24, 1, 0x5aa5, 0x7bde, 0, (16 << 16) | 1, 0, 0]),
]
LIVE_GUARD = '''foreach {addr expected} {
  0xe9001000 0x424c5432
  0xe9005080 0x4e435031 0xe9005088 2 0xe900508c 2
  0xe9001004 0 0xe9001008 2 0xe9001034 1 0xe900500c 2
} {
  if {[lindex [read_memory $addr 32 1] 0]!=$expected} {error "R19 COPY anchor changed"}
}
echo R19_COPY_ANCHOR_CONFIRMED
'''


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def local_plan():
    assert sha(ANCHOR) == ANCHOR_SHA
    previous = json.loads(ANCHOR.read_text())
    assert previous['complete'] and previous['stopped_on'] == 'COPY16'
    for name, digest in previous['files'].items():
        assert sha(ANCHOR.parent/name) == digest, name
    assert sha(R19/'impl/pnr/console_neo.fs') == R19_SHA
    regions = {
        'color': (COLOR-32, bytes((i*37+19)&255 for i in range(4160))),
        'source': (SOURCE-32, bytes((i*53+41)&255 for i in range(96))),
        'depth': (DEPTH-32, bytes((i*61+7)&255 for i in range(4160))),
    }
    ordered = sorted(regions.values())
    assert all(a+len(d) < b for (a,d),(b,_) in zip(ordered,ordered[1:]))
    assert all(len(p) == 8 and all(0 <= w < (1 << 32) for w in p)
               for p in [TARGET]+[p for _,p in CASES])
    expected = {}
    for name, _ in CASES:
        data = bytearray(regions['color'][1])
        data[32:64] = (regions['source'][1][32:64] if name == 'COPY16'
                       else struct.pack('<H', 0x5aa5)*16)
        expected[name] = bytes(data)
    return regions, expected


def route_review(path):
    """Bind board actions to the exact reviewed bitstream, never latest/*.fs."""
    review = json.loads(path.read_text())
    assert review['board'] == 'neo' and review['diagnostic_access_ready']
    assert review['controller_sha256'] == sha(Path(__file__))
    assert review['parent_r19_sha256'] == R19_SHA
    contract_path = HERE/'contract.json'
    assert review['contract_sha256'] == sha(contract_path)
    contract = json.loads(contract_path.read_text())
    assert contract['format'] == 'D*'
    assert sha(HERE/'neo_capture_memory.v') == contract['helper_sha256']
    build = Path(review['build']).resolve()
    assert build.is_relative_to(ROOT/'tang/impl')
    assert sha(build/'source/tang/boards/neo/neo_capture_local.v') == contract['helper_sha256']
    net_hash = sha(build/'console_neo.vg')
    # R21 parser-only revisions need an explicit equivalence proof, not a
    # relaxed netlist identity comparison or a hand-selected other build.
    if net_hash != NETLIST_SHA:
        equivalence = Path(review['format_equivalence_proof']).resolve()
        assert equivalence.is_relative_to(ROOT)
        assert sha(equivalence) == review['format_equivalence_sha256']
        e = json.loads(equivalence.read_text())
        assert e['passed'] and e['parent_netlist_sha256'] == NETLIST_SHA
        assert e['netlist_sha256'] == net_hash
    assert review['netlist_sha256'] == net_hash
    bitstream = build/'impl/pnr/console_neo.fs'
    assert sha(bitstream) == review['bitstream_sha256']
    assert review['observer_paths_reviewed']
    for name, digest in review['inputs'].items():
        p = Path(name)
        p = p if p.is_absolute() else ROOT/p
        assert sha(p) == digest, name
    return review, bitstream


def parse_case(text, width=None):
    assert 'CASE_OBSERVED' in text
    row = {'completed': bool(int(re.search(r'^COMMAND_COMPLETE ([01])$',text,re.M)[1]))}
    for key in ('BEFORE','AFTER'):
        row['gpu_'+key.lower()] = [int(w,0) for w in re.search(r'^GPU_'+key+r' (.+)$',text,re.M)[1].split()]
        assert len(row['gpu_'+key.lower()]) == 26
    row['error_deltas'] = {str(i):(row['gpu_after'][i]-row['gpu_before'][i])&0xffffffff
                           for i in (3,7,9,13,19)}
    raw = [int(w,0) for w in re.search(r'^NCP (.+)$',text,re.M)[1].split()]
    assert len(raw) == 6 and raw[0] == 0x4e435031 and (raw[1]&0x4f) == 12
    epoch = int(re.search(r'^ARM_EPOCH ([01])$',text,re.M)[1])
    assert ((raw[1] >> 5)&1) == epoch
    row['capture_raw'] = raw
    try:
        row['capture'] = decoder.decode(raw[4] | (raw[5] << 32), epoch, width)
    except ValueError as exc:
        row['capture'] = None
        row['decode_error'] = str(exc)
    return row


def classify(row):
    errors = any(row['error_deltas'].values())
    unchanged = all(row[k]['unchanged'] for k in ('color','source','depth'))
    exact = all(row[k]['expected_matches'] for k in ('color','source','depth'))
    if row['completed'] and not errors:
        outcome = 'completed_exact' if exact else 'completed_wrong_memory'
    elif row['completed']:
        outcome = 'rejected_unchanged' if unchanged else 'rejected_with_memory_change'
    else:
        outcome = 'timeout_unchanged' if unchanged else 'timeout_with_memory_change'
        if errors:
            outcome += '_and_errors'
    row['outcome'] = outcome
    capture = row.get('capture')
    row['copy_width_capture_complete'] = bool(capture and capture['complete'] and
        capture['valid_samples'] == 3 and not capture['armed']) if row['name']=='COPY16' else None
    return outcome


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan-only',action='store_true')
    p.add_argument('--check-only',action='store_true')
    p.add_argument('--route-review',type=Path)
    a = p.parse_args()
    regions, expected = local_plan()
    if a.plan_only:
        print(json.dumps({'plan_valid':True,'hardware':False,'ready_to_load':False,
            'reason':'Exact post-route bitstream/path review required',
            'anchor_sha256':ANCHOR_SHA,'target':TARGET,'cases':CASES}))
        return
    if not a.route_review:
        p.error('--route-review is required before any board access')
    review, bitstream = route_review(a.route_review)
    if a.check_only:
        print(json.dumps({'ready':True,'hardware':False,'bitstream_sha256':review['bitstream_sha256']}))
        return
    out = HERE/('board_trial_'+time.strftime('%Y%m%d_%H%M%S'))
    result = dict(candidate=True,diagnostic_complete=False,gpu_qualified=False,
                  bitstream_sha256=review['bitstream_sha256'],route_review_sha256=sha(a.route_review),
                  parent_r19_sha256=R19_SHA,anchor_sha256=ANCHOR_SHA,cases=[],
                  targets=[],
                  SD_written=False,flash_written=False,CPU_resumed=False)
    def save():
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    def run(name,code):
        cfg,log = out/(name+'.tcl'),out/(name+'.log')
        cfg.write_text(code+'\nshutdown\n')
        hw.run_child(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
            '-c','adapter speed 1000; gdb_port disabled; tcl_port disabled; telnet_port disabled',
            '-f',str(cfg)],log,40)
        return log.read_text()
    def interrupt(sig,frame):
        raise KeyboardInterrupt('Signal '+str(sig))
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):
        signal.signal(sig,interrupt)
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active = subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh',
            '-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True)
        assert active.returncode == 1 and not active.stdout.strip(),active.stdout
        identity = hw.usb_identity()
        assert identity['neo']['serial'] == '2025041420'
        assert identity['neo']['path'].endswith('/3-4.4.1') and identity['esp']['path'].endswith('/3-4.4.2')
        out.mkdir();shutil.copy2(__file__,out/'controller.py')
        result.update(identity=identity,started_unix=time.time());save()
        touched = False
        try:
            assert 'R19_COPY_ANCHOR_CONFIRMED' in run('live_guard',CSRS+BASE_GUARD+UNCACHED+LIVE_GUARD)
            for name,words in CASES:
                # Both experiments begin with fresh identical FPGA state.
                # This isolates COPY rejection from a subsequent CLEAR stall.
                touched = True
                result['r19_anchor_live_state_consumed'] = True
                save()
                hw.Hardware(out,result).program('program_'+name,bitstream,review['bitstream_sha256'])
                result['left_bitstream_sha256'] = review['bitstream_sha256']
                save()
                prefix = CSRS+BASE_GUARD+UNCACHED
                code = CSRS+BASE_GUARD+CACHE+UNCACHED+'''foreach addr {0xe9001004 0xe9001008 0xe9001034 0xe9005088 0xe900508c} {
  if {[lindex [read_memory $addr 32 1] 0]!=0} {error "Expected fresh idle observer/GPU"}
}
'''
                for region,(address,data) in regions.items():
                    seed = out/(name+'_'+region+'_seed.bin');seed.write_bytes(data)
                    code += f'load_image {{{seed}}} {address:#x} bin\nverify_image {{{seed}}} {address:#x} bin\n'
                assert 'SEEDS_OK' in run(name+'_seeds',code+'echo SEEDS_OK\n')
                packet = lambda v:'packet {'+' '.join(hex(w) for w in v)+'}\n'
                target_code = prefix+PACKET+ARM+packet(TARGET)+CAPTURE
                for region,(address,data) in regions.items():
                    target_code += f'dump_image {{{out/(name+"_target_"+region+".bin")}}} {address:#x} {len(data)}\n'
                text = run(name+'_target',target_code+'echo CASE_OBSERVED\n')
                target = parse_case(text)
                target['memory_unchanged'] = {region:(out/(name+'_target_'+region+'.bin')).read_bytes()==data
                                             for region,(_,data) in regions.items()}
                result['targets'].append(dict(name=name,**target));save()
                assert target['completed'] and not any(target['error_deltas'].values()),target
                assert target['capture'] and target['capture']['memory_event_mask'] == 0,target
                assert all(target['memory_unchanged'].values()),'TARGET changed guarded memory'
                code = prefix+PACKET+SNAPSHOT+ARM+packet(words)+CAPTURE+'gpu_snapshot after\n'
                for region,(address,data) in regions.items():
                    code += f'dump_image {{{out/(name+"_"+region+".bin")}}} {address:#x} {len(data)}\n'
                row = parse_case(run(name,code+DISABLED+'echo CASE_OBSERVED\n'),16 if name=='COPY16' else None)
                row.update(name=name,words=words,target=target)
                for region,(_,seed) in regions.items():
                    got = (out/(name+'_'+region+'.bin')).read_bytes()
                    want = expected[name] if region=='color' else seed
                    assert len(got) == len(seed)
                    row[region] = dict(expected_matches=got==want,unchanged=got==seed,
                        guards_unchanged=(got[:32]==seed[:32] and got[64:]==seed[64:]) if region=='color' else got==seed,
                        payload=got[32:64].hex(),differing_expected_bytes=sum(x!=y for x,y in zip(got,want)))
                classify(row)
                result['cases'].append(row);save();print(json.dumps(row),flush=True)
                assert row['capture'] is not None,'Malformed D* capture retained in result and raw log'
                assert all(row[k]['guards_unchanged'] for k in regions),'Memory outside destination changed'
                if row['completed'] and not any(row['error_deltas'].values()):
                    assert all(row[k]['expected_matches'] for k in regions),'Completed operation produced wrong bytes'
                # A rejected or stalled operation is the observation sought,
                # not success and not an exception that discards the trace.
            assert len(result['cases']) == len(CASES)
            result['diagnostic_complete'] = True  # Steps completed, not a functional PASS.
            result['left_state'] = 'Neo diagnostic candidate; halted CPU, internal bars; last CLEAR state retained'
        except BaseException as exc:
            result['error'] = repr(exc);save()
            if touched:
                for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,signal.SIG_IGN)
                try:
                    hw.Hardware(out,result).program('fallback_r19',R19/'impl/pnr/console_neo.fs',R19_SHA)
                    assert 'FALLBACK_OK' in run('fallback_guard',BASE_GUARD+'echo FALLBACK_OK\n')
                    result['fallback_restored'] = True
                    result['left_bitstream_sha256'] = R19_SHA
                    result['left_state'] = 'Fresh R19, halted CPU and internal bars; previous R19 command counters not restored'
                except BaseException as fallback:
                    result['fallback_error'] = repr(fallback)
            raise
        finally:
            result['finished_unix'] = time.time()
            result['files'] = {q.name:sha(q) for q in out.iterdir() if q.is_file() and q.name!='result.json'}
            save()
            print(json.dumps({'output':str(out),'diagnostic_complete':result['diagnostic_complete'],
                              'error':result.get('error')}),flush=True)


if __name__ == '__main__':
    main()
