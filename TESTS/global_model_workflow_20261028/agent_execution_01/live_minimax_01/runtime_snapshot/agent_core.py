"""Bounded implementation lifecycle, independent of the isolation transport.

The backend is trusted orchestration code, not an agent-selected command.
It must enforce an actual isolation boundary and independent final tests.
No original source integration or automatic acceptance occurs here.
"""
import hashlib
import json
import os
from pathlib import Path
import time


def atomic(path, value):
    temporary = path.with_name(path.name + '.new')
    with temporary.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def execute(backend, spec, out, parse):
    """One task, up to three CLI turns, one exact OpenCode session.

    Return REVIEW_PENDING only if independent validation and explicit task
    evidence requirements pass. A request quota is not a quality criterion.
    Stale output directories and orphaned executions are deliberately refused.
    Backend interfaces are documented in README; exceptions remain failures.
    """
    out = Path(out)
    out.mkdir(exist_ok=False)
    max_continuations = spec.get('max_continuations', 0)
    if type(max_continuations) is not int or not 0 <= max_continuations <= 2:
        raise ValueError('max_continuations must be in 0..2')
    started = time.monotonic()
    state = dict(schema=1, task_id=spec['task_id'], run_id=spec['run_id'],
                 status='PREPARING', session_id=None, attempts=[],
                 task_count=1, model_steps_observed=0,
                 tool_invocations_observed=0, api_requests_observed=None,
                 baseline=None, validation=None, elapsed_seconds=None,
                 quality_status='pending_independent_evaluation',
                 automatic_quality_score=None, source_integrated=False)

    def save(status):
        state['status'] = status
        state['elapsed_seconds'] = time.monotonic() - started
        atomic(out / 'state.json', state)

    save('PREPARING')
    try:
        preflight = backend.preflight(spec)
        atomic(out / 'preflight.json', preflight)
        if preflight.get('isolation_verified') is not True:
            raise RuntimeError('real execution isolation not verified')
        baseline = backend.baseline()
        state['baseline'] = baseline
        save('BASELINE_TESTED')
        if spec.get('require_initial_failure', False) and baseline.get('returncode') == 0:
            raise RuntimeError('expected failing baseline is absent')
        if baseline.get('policy_ok') is not True or baseline.get('infrastructure_ok') is not True:
            raise RuntimeError('baseline policy or infrastructure failure')
        prompt = spec['prompt']
        for attempt in range(max_continuations + 1):
            save('RUNNING')
            response = backend.run_agent(prompt, state['session_id'], attempt)
            raw = response['events']
            if not isinstance(raw, str):
                raise TypeError('events must be decoded JSONL text')
            (out / f'events_{attempt}.jsonl').write_text(raw)
            parsed = parse(raw, expected_session=state['session_id'])
            atomic(out / f'parsed_{attempt}.json', parsed)
            record = dict(attempt=attempt, returncode=response['returncode'],
                          events_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                          parsed=parsed, validation=None,
                          api_requests_observed=response.get('api_requests_observed'))
            state['attempts'].append(record)
            if parsed['session_id'] is not None and state['session_id'] is None:
                state['session_id'] = parsed['session_id']
            state['model_steps_observed'] += parsed['model_steps_finished']
            state['tool_invocations_observed'] += parsed['tool_invocations_observed']
            observed = [entry['api_requests_observed'] for entry in state['attempts']]
            if all(type(n) is int and n >= 0 for n in observed):
                state['api_requests_observed'] = sum(observed)
            else:
                state['api_requests_observed'] = None
            save('VALIDATING')
            # Even a provider error must preserve the independent test outcome
            # and any out-of-policy mutation. Neither may be hidden by exit0.
            validation = backend.validate()
            record['validation'] = validation
            state['validation'] = validation
            if validation.get('policy_ok') is not True:
                save('POLICY_FAILED')
                break
            if response['returncode'] != 0 or parsed['errors'] or not parsed['complete']:
                save('MODEL_INCOMPLETE')
                break
            if validation.get('infrastructure_ok') is not True:
                save('TEST_INFRASTRUCTURE_FAILED')
                break
            if validation.get('passed') is True:
                tools = state['tool_invocations_observed']
                steps = state['model_steps_observed']
                changed = validation.get('changed_files')
                required = spec.get('required_tool_evidence', {})
                min_tools = required.get('min_tool_calls', 0)
                min_steps = required.get('min_model_steps', 0)
                for bound in (min_tools, min_steps):
                    if type(bound) is not int or not 0 <= bound <= 96:
                        raise ValueError('invalid explicit evidence requirement')
                if ((spec.get('require_changes', False) and not changed) or
                        tools < min_tools or steps < min_steps):
                    save('INSUFFICIENT_EXECUTION_EVIDENCE')
                else:
                    save('REVIEW_PENDING')
                break
            if attempt == max_continuations:
                save('TESTS_FAILED')
                break
            if not state['session_id']:
                save('MODEL_INCOMPLETE')
                break
            # Exact previous session only; no implicit --continue or new fork.
            prompt = ('Independent tests still fail. Continue this same task and '
                      'session; inspect the failure, edit owned files only, rerun '
                      'the tests, and fix the cause.\n' +
                      str(validation.get('feedback', 'No test output available.'))[:12000])
            save('CONTINUATION_READY')
    except BaseException as error:
        state['error_type'] = type(error).__name__
        save('INTERRUPTED' if isinstance(error, (KeyboardInterrupt, InterruptedError)) else 'FAILED')
    finally:
        try:
            backend.close()
        except BaseException as error:
            state['cleanup_error_type'] = type(error).__name__
            save('CLEANUP_FAILED')
        save(state['status'])
    return state
