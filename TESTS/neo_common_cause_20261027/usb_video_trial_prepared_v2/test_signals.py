"""Real POSIX signals with board IO mocked, including finally entry boundaries."""
import ast
import hashlib
import inspect
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def child(case, number):
    import probe_usb_video as ctl
    request = ctl.StopRequest()
    request.install()
    report = {'candidate_sha256': 'mock-candidate', 'left_startup_verified': False}
    events = []
    delivered = []
    fired = False
    save_count = 0
    fail = {'experiment_error': 'coupled_usb_video',
            'double_error': 'coupled_usb_video',
            'log_error': 'coupled_usb_video',
            'restore_error': 'restore_r19'}.get(case)

    def deliver():
        nonlocal fired
        if fired:
            return
        fired = True
        numbers = SIGNALS if case == 'all_cleanup_signals' else (number,)
        for sig in numbers:
            delivered.append(int(sig))
            os.kill(os.getpid(), sig)

    class IO:
        current = ''

        def __init__(self):
            self.save = self.write_report

        def write_report(self):
            nonlocal save_count
            save_count += 1
            if case == 'cleanup_save' and report.get('restore_attempted'):
                deliver()
            if case == 'log_error' and 'error' in report and not report.get('restore_attempted'):
                deliver()
                raise OSError('injected primary journal failure')
            if case == 'cleanup_log_error' and self.current == 'restore_r19':
                deliver()
                raise OSError('injected cleanup journal failure')

        def event(self, name):
            self.current = name
            events.append(name)
            if case == 'event:' + name:
                deliver()
            if case in ('all_cleanup_signals', 'restore_error') and name == 'restore_r19':
                deliver()
            if name == fail or (case == 'double_error' and name == 'restore_r19'):
                raise RuntimeError('injected ' + name)

        def observe(self, name, code, marker):
            self.event(name)

        def camera(self, name):
            self.event(name)
            self.save()

        def program(self, name, path, digest):
            self.event(name)
            self.save()
            report['last_programmed_sha256'] = digest
            report['left_startup_verified'] = False
            self.save()

    lines, start = inspect.getsourcelines(ctl.execute)
    line_map = {name: start + next(i for i, line in enumerate(lines) if line.strip() == token)
                for name, token in {
                    'finally_entry': 'if touched:',
                    'cleanup_definition': 'def cleanup_save():',
                    'cleanup_io_save': "if hasattr(io, 'save'):",
                    'cleanup_attempt_flag': "report['restore_attempted'] = True",
                    'experiment_error': "report['error'] = repr(exc)",
                    'double_error': "report['error'] = repr(exc)",
                }.items()}
    # The first cleanup_save() call is before the restore try block.
    line_map['cleanup_first_save'] = start + next(i for i, line in enumerate(lines)
                                                 if line.strip() == 'cleanup_save()')
    line_map['after_cleanup'] = start + max(i for i, line in enumerate(lines)
                                           if line.strip() == 'stop.checkpoint()')

    def trace(frame, event, arg):
        if (not fired and frame.f_code is ctl.execute.__code__ and event == 'line'
                and frame.f_lineno == line_map.get(case)):
            deliver()
        return trace

    io = IO()
    error = None
    context = None
    sys.settrace(trace)
    try:
        ctl.execute(io, report, io.write_report, Path('MOCK.fs'), 'MOCK', request)
    except BaseException as exc:
        error = repr(exc)
        context = repr(exc.__context__) if exc.__context__ else None
    finally:
        sys.settrace(None)

    early = case in ('event:r19_initial_guard', 'event:r19_before')
    expected_count = 0 if early else 1
    assert fired and report['signals_received'] == delivered, (case, report, delivered)
    assert events.count('restore_r19') == expected_count, (case, events)
    assert error is not None, (case, report)
    if case in ('experiment_error', 'log_error'):
        assert error == "RuntimeError('injected coupled_usb_video')", (case, error)
        assert report['error'] == error
    elif case == 'double_error':
        assert report['error'] == "RuntimeError('injected coupled_usb_video')"
        assert report['restore_error'] == error == "RuntimeError('injected restore_r19')"
        assert context == report['error']
    elif case == 'restore_error':
        assert report['restore_error'] == error == "RuntimeError('injected restore_r19')"
    else:
        assert 'KeyboardInterrupt' in error and 'Signal' in error, (case, error)
    if not early and case not in ('double_error', 'restore_error'):
        assert report['left_startup_verified']
        assert report['last_programmed_sha256'] == ctl.base.prior.t.R19_SHA
    if case == 'log_error':
        assert report['error_log_errors'] == ["OSError('injected primary journal failure')"]
    if case == 'cleanup_log_error':
        assert report['cleanup_log_errors']
    print(json.dumps(dict(case=case, signal=int(number), delivered=delivered,
                         passed=True, hardware_access=False, events=events,
                         error=error, context=context, report=report,
                         target_line=line_map.get(case), saves=save_count)))


def unchanged_guards():
    old = HERE.parent / 'usb_video_trial_prepared' / 'probe_usb_video.py'
    new = HERE / 'probe_usb_video.py'
    assert sha(old) == 'e33bf8840587f730f039bdc5986239a7d40c97cd0b788f2252bfdc5342d83397'
    a, b = ast.parse(old.read_text()), ast.parse(new.read_text())
    for name in ('local_checks', 'restoration_guard'):
        get = lambda tree: next(node for node in tree.body
                                if isinstance(node, ast.FunctionDef) and node.name == name)
        assert ast.dump(get(a), include_attributes=False) == ast.dump(get(b), include_attributes=False), name
    for name in ('usb_video.tcl', 'video_prefix.tcl', 'utna_protocol.tcl', 'test_protocol.py'):
        assert sha(HERE/name) == sha(old.parent/name), name
    return {'original_sha256': sha(old), 'unchanged_functions': ['local_checks', 'restoration_guard'],
            'protocol_unchanged': True}


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--child':
        child(sys.argv[2].rsplit(':signal', 1)[0], int(sys.argv[3]))
        return
    guards = unchanged_guards()
    boundaries = ['finally_entry', 'cleanup_definition', 'cleanup_io_save',
                  'cleanup_attempt_flag', 'cleanup_first_save', 'cleanup_save',
                  'after_cleanup', 'experiment_error', 'double_error',
                  'restore_error', 'log_error', 'cleanup_log_error']
    boundaries += ['event:' + x for x in ('r19_initial_guard', 'r19_before', 'r19_usb_video',
                   'program_coupled', 'coupled_before_dmi', 'coupled_usb_video',
                   'coupled_after_observation', 'restore_r19', 'restored_guard', 'r19_restored')]
    cases = [(case, sig) for case in boundaries for sig in SIGNALS] + [('all_cleanup_signals', signal.SIGINT)]
    records = []
    for case, sig in cases:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--child', case, str(int(sig))],
                                capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, (case, sig, result.stderr, result.stdout)
        records.append(json.loads(result.stdout))
    report = dict(passed=True, hardware_access=False, controller_sha256=sha(HERE/'probe_usb_video.py'),
                  tool_sha256=sha(Path(__file__)), signal_delivery='os.kill to self in isolated subprocesses',
                  guards=guards, cases=records)
    (HERE/'signal_tests_result.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=True, hardware_access=False, cases=len(records))))


if __name__ == '__main__':
    main()
