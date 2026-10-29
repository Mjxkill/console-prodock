"""Sequential, isolated Gowin experiments on frozen Neo netlists."""
import fcntl
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from reports import fixed_constraints, inspect_build
from runtime import REPO, save, sha


def make_plan(parent, output, experiments):
    parent = Path(parent).resolve(strict=True)
    record = inspect_build(parent)
    if record['status'] not in ('TIMING_PASS', 'TIMING_FAIL'):
        raise ValueError('Parent must be a complete build with verified sources and timing')
    net = parent / 'impl/gwsynthesis/console_neo.vg'
    if not net.is_file():
        raise ValueError('This adapter requires a synthesized Neo build; use its original synthesis parent')
    frozen = parent / 'source/tang/boards/neo'
    snapshots = {str(p):sha(p) for p in [net, frozen/'neo.cst', frozen/'neo.sdc',
                                       parent/'sources.json', parent/'build.tcl',
                                       REPO/'tools/route_console_neo.py', REPO/'tools/check_neo_timing.py']}
    names = set()
    for experiment in experiments:
        if set(experiment) - {'name', 'place', 'route', 'replicate', 'cst'}:
            raise ValueError('Unknown experiment option')
        name = experiment['name']
        if not re.fullmatch(r'[A-Za-z0-9_]+', name) or name in names:
            raise ValueError('Invalid/duplicate build name')
        if (REPO / 'tang/impl' / name).exists():
            raise ValueError('Build already exists: ' + name)
        names.add(name)
        if experiment['place'] not in range(5) or experiment['route'] not in range(3) or experiment['replicate'] not in (0, 1):
            raise ValueError('Unsupported Gowin strategy')
        if experiment.get('cst'):
            cst = Path(experiment['cst']).resolve(strict=True)
            if fixed_constraints(cst.read_text()) != fixed_constraints((frozen/'neo.cst').read_text()):
                raise ValueError('Experiment changes pins/banks/non-placement constraints')
            experiment['cst'] = str(cst)
            snapshots[str(cst)] = sha(cst)
    if not experiments:
        raise ValueError('Empty experiment list')
    plan = dict(schema=1, backend='gowin-neo', parent=str(parent), snapshots=snapshots,
                experiments=experiments, max_parallel=1, policy='Never program hardware; never alter clocks or frozen inputs')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        stream.write(json.dumps(plan, indent=2) + '\n')
    return plan


def execute_plan(plan_path):
    plan_path = Path(plan_path).resolve(strict=True)
    plan = json.loads(plan_path.read_text())
    if plan.get('backend') != 'gowin-neo' or plan.get('schema') != 1:
        raise ValueError('Unsupported plan schema/backend')
    state_path = plan_path.with_suffix('.state.json')
    with plan_path.with_suffix('.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = json.loads(state_path.read_text()) if state_path.exists() else dict(plan_sha256=sha(plan_path), jobs=[])
        if state['plan_sha256'] != sha(plan_path):
            raise ValueError('Plan changed after execution began')
        if any(j['status'] == 'RUNNING' for j in state['jobs']):
            raise ValueError('Prior interrupted/running job requires inspection; refusing duplicate execution')
        completed = {j['name'] for j in state['jobs']}
        for experiment in plan['experiments']:
            if experiment['name'] in completed:
                continue
            for path, digest in plan['snapshots'].items():
                if sha(path) != digest:
                    raise ValueError('Frozen plan input changed: ' + path)
            name = experiment['name']
            # Validate on execution as well: a hand-edited plan is input.
            if not re.fullmatch(r'[A-Za-z0-9_]+', name):
                raise ValueError('Invalid build name')
            if (REPO/'tang/impl'/name).exists():
                raise ValueError('Output already exists: ' + name)
            command = ['nice', '-n', '10', sys.executable, str(REPO/'tools/route_console_neo.py'),
                       '--from-build', plan['parent'], '--name', name,
                       '--place', str(experiment['place']), '--route', str(experiment['route']),
                       '--replicate', str(experiment['replicate'])]
            if experiment.get('cst'):
                command += ['--placement-cst', experiment['cst']]
            job = dict(name=name, status='RUNNING', started_unix=time.time(), argv=command)
            state['jobs'].append(job)
            save(state_path, state)
            print('Starting ' + name, flush=True)
            with (plan_path.parent / (name + '.driver.log')).open('x') as output:
                process = subprocess.Popen(command, cwd=REPO, stdout=output, stderr=subprocess.STDOUT)
                job['pid'] = process.pid
                save(state_path, state)
                job['returncode'] = process.wait()
            build = REPO / 'tang/impl' / name
            job.update(status='BUILD_FAILED', elapsed_s=round(time.time()-job['started_unix'], 1))
            if job['returncode'] == 0:
                with (plan_path.parent / (name + '.qualification.log')).open('x') as output:
                    gate = subprocess.run([sys.executable, str(REPO/'tools/check_neo_timing.py'), str(build)],
                                          cwd=REPO, stdout=output, stderr=subprocess.STDOUT)
                job['qualification_returncode'] = gate.returncode
                job['status'] = 'QUALIFIED' if gate.returncode == 0 else 'REJECTED'
            job['analysis'] = inspect_build(build) if build.exists() else None
            save(state_path, state)
            print(name + ': ' + job['status'], flush=True)
    return state
