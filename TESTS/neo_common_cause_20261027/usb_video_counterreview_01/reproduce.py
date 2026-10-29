"""Offline counterexamples for the frozen observation controller; never accesses hardware."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PREPARED = HERE.parent / 'usb_video_trial_prepared'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def signal_child(line, sig):
    sys.path.insert(0, str(PREPARED))
    import probe_usb_video as ctl
    events = []
    report = {'candidate_sha256': 'mock-candidate', 'left_startup_verified': False}
    class IO:
        save = staticmethod(lambda: None)
        def observe(self, name, *args):
            events.append(name)
        def camera(self, name):
            events.append(name)
        def program(self, name, *args):
            events.append(name)
    fired = False
    def handler(number, frame):
        raise KeyboardInterrupt('Signal ' + str(number))
    for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(number, handler)
    def trace(frame, event, arg):
        nonlocal fired
        if not fired and frame.f_code is ctl.execute.__code__ and event == 'line' and frame.f_lineno == line:
            fired = True
            os.kill(os.getpid(), sig)
        return trace
    error = None
    sys.settrace(trace)
    try:
        ctl.execute(IO(), report, lambda: None, Path('MOCK.fs'), 'MOCK')
    except BaseException as exc:
        error = repr(exc)
    finally:
        sys.settrace(None)
    print(json.dumps({'target_line': line, 'signal': sig, 'signal_delivered': fired,
                     'events': events, 'error': error,
                     'restoration_attempted': 'restore_r19' in events,
                     'hardware_access': False}))


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--signal-child':
        signal_child(int(sys.argv[2]), int(sys.argv[3]))
        return
    assert sha(PREPARED/'probe_usb_video.py') == 'e33bf8840587f730f039bdc5986239a7d40c97cd0b788f2252bfdc5342d83397'
    results = []
    for line in (0, 107, 110, 111):
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            child = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--signal-child', str(line), str(int(sig))],
                                   capture_output=True, text=True, timeout=10)
            assert child.returncode == 0, child.stderr
            result = json.loads(child.stdout)
            result['counterexample_reproduced'] = line != 0 and result['signal_delivered'] and not result['restoration_attempted']
            assert result['restoration_attempted'] if line == 0 else result['counterexample_reproduced']
            results.append(result)
    tree = ast.parse((PREPARED/'test_protocol.py').read_text())
    harness = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'HARNESS' for t in n.targets))
    needle = ' if {$bits!=32} {error "Unexpected width"}'
    assert harness.count(needle) == 1
    harness = harness.replace(needle, needle+'\n if {$fault eq "post_reset" && [llength $writes]==4 && $address==0xe9000000 && $count==30} {set seq 0}')
    harness_path = HERE/'post_reset_harness.tcl'
    harness_path.write_text(harness)
    child = subprocess.run(['/usr/bin/tclsh', str(harness_path), 'post_reset', str(PREPARED/'usb_video.tcl')], capture_output=True, text=True, timeout=5)
    (HERE/'post_reset.log').write_text(child.stdout+child.stderr)
    post_reset = {'returncode':child.returncode, 'controller_done':'USB_VIDEO_DONE' in child.stdout,
                  'post_sequence_zero':'USB_TRACE_STATUS POST_USB 0x55544e41 0 0' in child.stdout}
    assert child.returncode == 0 and post_reset['controller_done'] and post_reset['post_sequence_zero']
    extractor_path = HERE.parent/'usb_video_extract_01/extract.py'
    spec = importlib.util.spec_from_file_location('offline_extract', extractor_path)
    extractor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extractor)
    valid = (HERE.parent/'usb_video_extract_01/tests_02/r19.log').read_text()
    assert extractor.parse_text(valid)['capture_consistent']
    needle = 'USB_TRACE_STATUS POST_USB 0x55544e41 0 4'
    assert valid.count(needle) == 1
    changed = valid.replace(needle, 'USB_TRACE_STATUS POST_USB 0x55544e41 0 0')
    parsed = extractor.parse_text(changed)
    assert not parsed['capture_consistent']
    assert parsed['check_failures'] == ['POST_USB: unexpected live UTNA status']
    post_reset['existing_extractor_rejects'] = True
    post_reset['existing_extractor_errors'] = parsed['check_failures']
    post_reset['extractor_sha256'] = sha(extractor_path)
    result = {'hardware_access':False, 'controller_sha256':sha(PREPARED/'probe_usb_video.py'),
              'tcl_sha256':sha(PREPARED/'usb_video.tcl'), 'signal_cases':results,
              'post_reset':post_reset,
              'qualification':'COUNTEREXAMPLES_FOUND; not a hardware result or readiness approval'}
    (HERE/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'hardware_access':False, 'signal_counterexamples':sum(r['counterexample_reproduced'] for r in results), 'post_reset':post_reset}))


if __name__ == '__main__':
    main()
