"""OpenCode orchestration with a host-only provider gateway and isolated MCP.

OpenCode has no native tools. Only taskbox MCP exposes files and execution,
inside the independently checked bubblewrap boundary. The old review runner
is untouched. Every proposed edit remains an isolated candidate.
"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from agent_core import atomic
from agent_provider import ProviderProxy
from agent_evidence import audit


def dependencies():
    """Flat installed pack, with source-tree locations only for candidate tests."""
    here = Path(__file__).resolve().parent
    for directory in (here / 'isolation', here.parent):
        if directory.is_dir() and str(directory) not in sys.path:
            sys.path.append(str(directory))
    import agent_isolation
    from process_io import capture
    return agent_isolation, capture


class Backend:
    def __init__(self, args, spec, out, key):
        self.args, self.spec, self.out = args, spec, Path(out)
        self.isolation, self.capture = dependencies()
        self.key = key
        self.proxy = None
        self.manifest = None
        self.child = None
        self.tests = []
        self.started = time.monotonic()
        self.gateway_records = []
        self.audit_evidence = None

    def preflight(self, spec):
        self.manifest = self.isolation.prepare(spec, self.out / 'isolation')
        self.path = self.manifest['manifest_path']
        for name in self.manifest['paths']:
            if self.key.encode() in (Path(self.manifest['tree']) / name).read_bytes():
                raise ValueError('credential present in copied input')
        proof = self.isolation.preflight(self.path)
        if proof.get('isolation_verified') is not True:
            return proof
        self.controller = self.out / 'controller'
        self.controller.mkdir()
        self.proxy = ProviderProxy(self.key, self.args.model, self.args.max_requests)
        base_url = self.proxy.start()
        self.env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
                    'LANG': 'C.UTF-8', 'HOME': str(self.controller)}
        for name in ('CONFIG', 'DATA', 'CACHE', 'STATE'):
            directory = self.controller / name.lower()
            directory.mkdir()
            self.env['XDG_' + name + '_HOME'] = str(directory)
        prompt = (
            'You are implementing the assigned task on an isolated copy. '
            'You have taskbox MCP tools to read and change owned files and run '
            'real tests. Use those tools: do not merely propose a patch. '
            'Native tools are unavailable. Read the task and relevant files, '
            'run the fixed tests BEFORE editing, inspect their actual failure, '
            'fix the cause, run the fixed tests again, and continue correcting '
            'until they pass or you reach a real blocker. Do not edit tests or '
            'other protected inputs. Never claim an action without tool evidence. '
            'All taskbox_read_file/write_file paths MUST be relative paths, such '
            'as agent_audit.py, NEVER absolute paths. The tool filesystem is /work, '
            'which differs from OpenCode own directory. '
            'Keep modules commented and below 1000 physical lines. '
            'Conclude with the files changed, tests observed, and limitations.')
        config = dict(autoupdate=False, snapshot=False, share='disabled',
                      enabled_providers=['task-provider'],
                      permission={'*': 'deny', 'taskbox_*': 'allow'},
                      mcp=self.isolation.mcp_config(self.path),
                      agent={'implementer': dict(mode='primary', description='Isolated implementation',
                                                 prompt=prompt, steps=self.args.max_steps,
                                                 permission={'*': 'deny', 'taskbox_*': 'allow'})},
                      provider={'task-provider': dict(npm='@ai-sdk/openai-compatible',
                           name='Bounded task gateway', options=dict(baseURL=base_url, apiKey=self.proxy.token),
                           models={self.args.model: dict(name=self.args.model,
                                     limit=dict(context=131072, output=self.args.max_output_tokens))})})
        self.config = self.controller / 'opencode.json'
        atomic(self.config, config)
        self.env.update(OPENCODE_CONFIG=str(self.config), OPENCODE_DISABLE_PROJECT_CONFIG='true',
                        OPENCODE_DISABLE_CLAUDE_CODE='true',
                        OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX=str(self.args.max_output_tokens))
        self.bin = shutil.which(self.args.opencode_bin)
        if self.bin is None:
            raise RuntimeError('OpenCode unavailable')
        version = subprocess.run([self.bin, '--version'], capture_output=True, text=True,
                                 timeout=10, env=self.env)
        if version.returncode:
            raise RuntimeError('OpenCode version unavailable')
        atomic(self.out / 'opencode_version.json', {'version': version.stdout.strip()})
        return proof

    def baseline(self):
        result = self.isolation.run_tests(self.path)
        self.tests.append(result)
        atomic(self.out / 'baseline.json', result)
        return result

    def run_agent(self, prompt, session_id, attempt):
        command = [self.bin, 'run', '--pure', '--format', 'json',
                   '--agent', 'implementer', '--model', 'task-provider/' + self.args.model,
                   '--dir', str(self.controller), '--title', self.spec['task_id']]
        if session_id is not None:
            command += ['--session', session_id]
        # Neither real provider key nor caller environment is inherited.
        before = len(self.proxy.snapshot())
        self.child = subprocess.Popen(command, cwd=self.controller, env=self.env,
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, start_new_session=True)
        atomic(self.out / f'command_{attempt}.json',
               {'argv': command, 'pid': self.child.pid, 'session_requested': session_id})
        remaining = self.args.timeout - (time.monotonic() - self.started)
        if remaining <= 0:
            raise subprocess.TimeoutExpired(command, self.args.timeout)
        try:
            raw, errors = self.capture(self.child, prompt.encode(), remaining)
        except BaseException as error:
            raw = getattr(error, 'captured_stdout', b'')
            errors = getattr(error, 'captured_stderr', b'')
            (self.out / f'partial_events_{attempt}.jsonl').write_text(self.redact(raw.decode(errors='replace')))
            (self.out / f'stderr_{attempt}.txt').write_text(self.redact(errors.decode(errors='replace')))
            raise
        (self.out / f'stderr_{attempt}.txt').write_text(self.redact(errors.decode(errors='replace')))
        after = self.proxy.snapshot()
        atomic(self.out / f'gateway_{attempt}.json', after)
        return dict(returncode=self.child.returncode,
                    events=self.redact(raw.decode(errors='replace')),
                    api_requests_observed=len(after) - before)

    def redact(self, value):
        return value.replace(self.key, '[REDACTED]') if self.key else value

    def validate(self):
        changes = self.isolation.collect_changes(self.path)
        test = self.isolation.run_tests(self.path)
        self.tests.append(test)
        number = len(self.tests) - 1
        atomic(self.out / f'validation_tests_{number}.json', test)
        atomic(self.out / f'changes_{number}.json', changes)
        result = dict(test)
        result.update(changed_files=changes['changed_files'],
                      policy_ok=test.get('policy_ok') is True and changes.get('policy_ok') is True,
                      feedback=test.get('tests_log', ''), changes=changes)
        self.audit_evidence = audit(self.manifest['journal_path'])
        atomic(self.out / f'audit_evidence_{number}.json', self.audit_evidence)
        required = self.spec.get('required_tool_evidence', {})
        result['evidence_ok'] = self.audit_evidence['test_audit_complete']
        if required.get('failed_test_before_edit', False):
            result['evidence_ok'] &= self.audit_evidence['failed_test_before_write']
        if required.get('passed_test_after_edit', False):
            result['evidence_ok'] &= self.audit_evidence['passed_test_after_write']
        return result

    def close(self):
        if self.child is not None and self.child.poll() is None:
            try:
                os.killpg(self.child.pid, signal.SIGTERM)
                self.child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(self.child.pid, signal.SIGKILL)
                self.child.wait(timeout=3)
            except ProcessLookupError:
                pass
        if self.proxy is not None:
            self.proxy.close()
            self.gateway_records = self.proxy.snapshot()
            atomic(self.out / 'gateway_final.json', self.gateway_records)
        self.key = None
        if self.child is not None:
            deadline = time.monotonic() + 2
            while True:
                self.audit_evidence = audit(self.manifest['journal_path'])
                if self.audit_evidence['all_recorded_processes_exited'] or time.monotonic() >= deadline:
                    break
                time.sleep(.05)
            atomic(self.out / 'audit_evidence_final.json', self.audit_evidence)
            if not self.audit_evidence['all_recorded_processes_exited']:
                raise RuntimeError('MCP lifecycle incomplete or process still alive')
