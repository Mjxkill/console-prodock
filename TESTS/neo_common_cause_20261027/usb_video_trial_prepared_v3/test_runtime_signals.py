"""Real imported run_child with harmless children and asynchronously delivered signals."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent


def child(mode, number, directory):
    import probe_usb_video as ctl
    assert os.getpgrp() == os.getpid(), 'Test must own its process group before any group signal'
    request = ctl.StopRequest()
    request.install()
    report = {'candidate_sha256': 'mock', 'left_startup_verified': False}
    events, observations, delivery_errors = [], [], []

    def blocking(name):
        log = directory/(name+'.log')
        delivered = []
        timeout = mode == 'timeout_group'
        program = ('import os,json,time;print("READY "+json.dumps(dict(pid=os.getpid(),'
                   'pgid=os.getpgrp(),sid=os.getsid(0))),flush=True);time.sleep('
                   + ('10' if timeout else '0.45') + ');print("CHILD_COMPLETED",flush=True)')

        def send():
            try:
                deadline = time.monotonic()+3
                while time.monotonic() < deadline:
                    if log.exists() and 'READY ' in log.read_text():
                        if mode == 'experiment_pid':
                            os.kill(os.getpid(), number)
                        else:
                            os.killpg(os.getpgrp(), number)
                        delivered.append(number)
                        return
                    time.sleep(.005)
                raise TimeoutError('Harmless child did not reach READY')
            except BaseException as exc:
                delivery_errors.append(repr(exc))

        thread = threading.Thread(target=send)
        thread.start()
        failure = None
        start = time.monotonic()
        try:
            ctl.base.prior.hw.run_child([sys.executable, '-c', program], log, .5 if timeout else 3)
        except BaseException as exc:
            failure = exc
        finally:
            thread.join(timeout=4)
        assert not thread.is_alive() and not delivery_errors and delivered == [number]
        raw = log.read_text()
        info = json.loads(next(line[6:] for line in raw.splitlines() if line.startswith('READY ')))
        assert info['pid'] == info['pgid'] == info['sid']
        assert info['pgid'] != os.getpgrp() and info['sid'] != os.getsid(0)
        assert signal.getsignal(number) == request.handler  # bound methods: equality, not identity
        if timeout:
            assert isinstance(failure, subprocess.TimeoutExpired)
            assert 'CHILD_COMPLETED' not in raw
        else:
            assert failure is None and 'CHILD_COMPLETED' in raw
        try:
            os.kill(info['pid'], 0)
        except ProcessLookupError:
            pass
        else:
            raise AssertionError('Harmless child still alive or not reaped')
        observations.append(dict(name=name, child=info, delivered=delivered,
                                 elapsed=time.monotonic()-start, completed=failure is None,
                                 failure=repr(failure) if failure else None, reaped=True))
        if failure:
            raise failure

    class IO:
        save = staticmethod(lambda: None)
        def observe(self, name, *args):
            events.append(name)
            if mode == 'restore_primary_group' and name == 'coupled_usb_video':
                raise RuntimeError('primary experimental error')
        def camera(self, name):
            events.append(name)
        def program(self, name, path, digest):
            events.append(name)
            if ((mode in ('experiment_pid', 'experiment_group', 'timeout_group') and name=='program_coupled')
                    or (mode in ('restore_group', 'restore_primary_group') and name=='restore_r19')):
                blocking(name)
            report['last_programmed_sha256'] = digest

    error = None
    try:
        ctl.execute(IO(), report, lambda: None, Path('MOCK.fs'), 'MOCK', request)
    except BaseException as exc:
        error = repr(exc)
    assert events.count('restore_r19') == 1 and report['left_startup_verified']
    assert report['last_programmed_sha256'] == ctl.base.prior.t.R19_SHA
    assert request.received == [number] and report['error'] == error
    if mode == 'restore_primary_group':
        assert error == "RuntimeError('primary experimental error')"
    elif mode == 'timeout_group':
        assert error.startswith('TimeoutExpired(')
    else:
        assert error == f"KeyboardInterrupt('Signal {number}')"
    print(json.dumps(dict(passed=True, hardware_access=False, mode=mode, signal=number,
                         events=events, observations=observations, error=error, report=report,
                         run_child_source=str(Path(ctl.base.prior.hw.__file__).resolve()))))


def main():
    if sys.flags.optimize:
        raise SystemExit('assertions disabled: refusing to run')
    if len(sys.argv) == 5 and sys.argv[1] == '--child':
        child(sys.argv[2], int(sys.argv[3]), Path(sys.argv[4]))
        return
    out = HERE/'runtime_signal_tests'
    out.mkdir(exist_ok=False)
    records = []
    for mode in ('experiment_pid', 'experiment_group', 'restore_group', 'restore_primary_group', 'timeout_group'):
        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            directory = out/f'{mode}_{int(number)}'
            directory.mkdir()
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--child', mode,
                                     str(int(number)), str(directory)], start_new_session=True,
                                    capture_output=True, text=True, timeout=12)
            (directory/'controller.log').write_text(result.stdout+result.stderr)
            assert result.returncode == 0, (mode, number, result.stdout, result.stderr)
            records.append(json.loads(result.stdout))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    source = Path(records[0]['run_child_source'])
    report = dict(passed=True, hardware_access=False, cases=records,
                  controller_sha256=sha(HERE/'probe_usb_video.py'), tool_sha256=sha(Path(__file__)),
                  run_child_source=str(source), run_child_sha256=sha(source),
                  scope='Exact imported run_child; harmless Python children only. Real asynchronously delivered PID/group signals. No serial, JTAG, USB identity query or board backend used.')
    (HERE/'runtime_signal_tests_result.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=True, hardware_access=False, cases=len(records))))


if __name__ == '__main__':
    main()
