import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, 'tools')
from check_usb_idle_board import jlink, decode
from check_gpu_reloads import console_snapshot

root = Path('TESTS/usb_idle_r3_cdc_boots5_7_20261003')
root.mkdir(exist_ok=False)
(root/'runner.py').write_bytes(Path(__file__).read_bytes())
results = []
for boot in range(5, 8):
    out = root/f'boot{boot}'
    out.mkdir()
    result = {'boot': boot}
    results.append(result)
    try:
        command = ['python3', 'tools/check_gpu_reloads.py', '--stage',
            'tang/impl/gpu_l12_usb_hs33_idle_r3', '--rounds', '1',
            '--load-only', '--out', str(out/'reload')]
        with (out/'reload.log').open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                           timeout=160, check=True)
        print(f'BOOT {boot}: loaded HS480', flush=True)
        with (out/'idle.log').open('w') as log:
            subprocess.run(['python3', 'tools/check_usb_idle_board.py',
                '--endpoints', '2', '3', '--seconds', '1', '--out', str(out/'idle')],
                stdout=log, stderr=subprocess.STDOUT, timeout=100, check=True)
        idle = json.loads((out/'idle/result.json').read_text())
        trace = idle['trace']
        if (idle['cleanup_errors'] or idle['poll']['completions'] or
            any(trace[k] for k in ['missing2', 'missing3', 'bad_response',
                                   'rx_error_cycles', 'bad_in_tokens', 'bus_resets'])):
            raise RuntimeError('Empty endpoint test failed; preserve this boot')
        address = idle['wire_address']
        result.update(wire_address=address, device=console_snapshot())
        probe = jlink(out, 'probe')
        arm = jlink(out, 'arm', (address<<8)|1)
        result['arm'] = arm
        if arm['sequence'] != probe['sequence']+1 or arm['words'][2] != (address<<8)|1:
            raise RuntimeError('Arm snapshot not coherent')
        try:
            with (out/'stress.log').open('w') as log:
                process = subprocess.run(['python3', 'tools/check_usb_stress.py',
                    '--rounds', '20', '--out', str(out/'stress')], stdout=log,
                    stderr=subprocess.STDOUT, timeout=180)
            result['stress_returncode'] = process.returncode
        finally:
            snapshot = jlink(out, 'snapshot', 6)
            result['snapshot'] = snapshot
            result['trace'] = decode(snapshot)
        if snapshot['sequence'] != arm['sequence']+1 or snapshot['words'][2] != 6:
            raise RuntimeError('Final snapshot not coherent')
        if result['stress_returncode']:
            raise RuntimeError('CDC mismatch; preserve this boot')
        trace = result['trace']
        if (not trace['in2'] or not trace['in3'] or trace['address'] != address or
            any(trace[k] for k in ['missing2', 'missing3', 'bad_response',
                                   'rx_error_cycles', 'bad_in_tokens', 'bus_resets'])):
            raise RuntimeError('Unexpected USB trace; preserve this boot')
        result['status'] = 'pass'
        print(f'BOOT {boot}: 20 rounds, 108820 exact bytes, no trace fault', flush=True)
    except BaseException as error:
        result.update(status='fail', error=repr(error))
        print(f'BOOT {boot}: {error!r}', flush=True)
        break
    finally:
        result['device_after'] = console_snapshot()
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        (root/'result.json').write_text(json.dumps(results, indent=2)+'\n')
sys.exit(0 if len(results)==3 and all(r['status']=='pass' for r in results) else 1)
