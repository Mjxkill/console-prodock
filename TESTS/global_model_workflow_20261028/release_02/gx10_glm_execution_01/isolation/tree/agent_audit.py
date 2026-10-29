"""Strict counters for trusted taskbox audit records.

Implements summarize(records) according to CONTRACT.md:

- Pure function: no files, network, processes, clocks, or orchestration
  runtime imports; and the input records are never mutated.
- Relevant events are 'tool_start', 'tool_finish', 'test_finish'; every
  other event (e.g. 'sandbox_start', 'launcher_exit') is ignored.
- A command outcome is identified by (launch_id, request_id, index) and is
  counted once; identical repeats are tolerated, conflicting repeats of the
  same identity raise ValueError.
- Completion rules require run_tests starts to pair with run_tests finishes
  and every test_finish to belong to such a paired call, which itself must
  carry at least one observed command outcome.

This module only adds the missing implementation of summarize().
"""


def _record_event(rec):
    """Validate that a record is a dict with a string 'event' key.

    Invalid records raise ValueError. Relevant events are returned verbatim;
    every other event kind is reported as None (to be ignored downstream),
    which matters because lifecycle events may lack required identity fields.
    """
    event = rec.get('event')
    if not isinstance(event, str):
        raise ValueError('record event must be a string, got %r' % (event,))
    if event not in ('tool_start', 'tool_finish', 'test_finish'):
        return None
    return event


def _validate_identity(rec):
    """Validate launch_id/request_id of a relevant record.

    'launch_id' must be a nonempty string; 'request_id' must be a nonempty
    string or an integer and is never a bool. Returns the launch-separated
    request identity tuple used for command calls.
    """
    launch_id = rec.get('launch_id')
    if not isinstance(launch_id, str) or not launch_id:
        raise ValueError('relevant record launch_id must be a nonempty '
                         'string, got %r' % (launch_id,))
    request_id = rec.get('request_id')
    if isinstance(request_id, bool):
        raise ValueError('request_id must not be a bool, got %r'
                         % (request_id,))
    if not (isinstance(request_id, int)
            or (isinstance(request_id, str) and request_id)):
        raise ValueError('request_id must be a nonempty string or an '
                         'integer, got %r' % (request_id,))
    return (launch_id, request_id)


def _validate_tool_name(rec):
    """Validate the required string 'name' of a tool_start/tool_finish."""
    name = rec.get('name')
    if not isinstance(name, str):
        raise ValueError('tool record name must be a string, got %r' % (name,))
    return name


def _validate_outcome(rec):
    """Validate and extract the payload of a test_finish record.

    Requires integer 'index' in 0..1023 (not bool), integer 'returncode'
    in -255..255 (not bool), and true booleans 'timeout' and
    'output_limited'. Returns the outcome payload tuple.
    """
    index = rec.get('index')
    if isinstance(index, bool) or not isinstance(index, int) \
            or index < 0 or index > 1023:
        raise ValueError('test_finish index must be an integer in 0..1023, '
                         'got %r' % (index,))
    returncode = rec.get('returncode')
    if isinstance(returncode, bool) or not isinstance(returncode, int) \
            or returncode < -255 or returncode > 255:
        raise ValueError('test_finish returncode must be an integer in '
                         '-255..255, got %r' % (returncode,))
    timeout = rec.get('timeout')
    if not isinstance(timeout, bool):
        raise ValueError('test_finish timeout must be a boolean, got %r'
                         % (timeout,))
    output_limited = rec.get('output_limited')
    if not isinstance(output_limited, bool):
        raise ValueError('test_finish output_limited must be a boolean, '
                         'got %r' % (output_limited,))
    return (returncode, timeout, output_limited)


def summarize(records):
    """Account protected test-command outcomes and model-only calls.

    Returns a dict with exactly the fields: test_runs (unique observed
    command outcomes), test_failures (nonzero returncode OR timeout OR
    output_limited), complete (pairing rules of CONTRACT.md), and test_calls
    (distinct run_tests request identities in starts OR finishes).

    Raises ValueError for malformed input, missing required fields, type
    errors, or conflicting repeats of the same outcome identity. Identical
    repeats and out-of-order presentation are tolerated. The input list and
    its records are never modified.
    """
    # Container validation: a list of records is required; anything else
    # (None, dict, ...) is a type error for this contract.
    if not isinstance(records, list):
        raise ValueError('records must be a list, got %r' % (type(records),))

    # launch-separated request identities, mapped to the observed tool name.
    starts = {}
    finishes = {}
    # Command outcomes keyed by (launch_id, request_id, index) -> payload.
    outcomes = {}

    for rec in records:
        # Each record must itself be a dictionary with a string event;
        # irrelevant lifecycle events are skipped before identity checks.
        if not isinstance(rec, dict):
            raise ValueError('each record must be a dict, got %r' % (rec,))
        event = _record_event(rec)
        if event is None:
            continue
        call_key = _validate_identity(rec)
        if event == 'tool_start':
            name = _validate_tool_name(rec)
            if call_key in starts and starts[call_key] != name:
                raise ValueError('conflicting repeat of tool_start identity '
                                 '%r with name %r vs %r'
                                 % (call_key, name, starts[call_key]))
            starts[call_key] = name
        elif event == 'tool_finish':
            name = _validate_tool_name(rec)
            if call_key in finishes and finishes[call_key] != name:
                raise ValueError('conflicting repeat of tool_finish identity '
                                 '%r with name %r vs %r'
                                 % (call_key, name, finishes[call_key]))
            finishes[call_key] = name
        else:  # event == 'test_finish'
            payload = _validate_outcome(rec)
            outcome_key = call_key + (rec['index'],)
            if outcome_key in outcomes:
                if outcomes[outcome_key] != payload:
                    raise ValueError('conflicting repeat of command outcome '
                                     'identity %r: %r vs %r'
                                     % (outcome_key, payload,
                                        outcomes[outcome_key]))
                # Identical repeat: tolerable idempotent dedup, count once.
                continue
            outcomes[outcome_key] = payload

    # Runs and failures come only from the deduplicated outcome set.
    test_runs = len(outcomes)
    test_failures = sum(
        1 for (returncode, timeout, output_limited) in outcomes.values()
        if returncode != 0 or timeout or output_limited)

    # Test calls are distinct run_tests request identities seen in a start
    # OR a finish; other tool names must not inflate this counter.
    run_starts = set(k for k, name in starts.items() if name == 'run_tests')
    run_finishes = set(k for k, name in finishes.items()
                       if name == 'run_tests')
    test_calls = len(run_starts | run_finishes)

    # Completion rules (CONTRACT.md), all of which are required:
    complete = (
        # every run_tests start pairs with a finish and vice versa;
        run_starts == run_finishes
        # every test_finish belongs to such a paired run_tests call;
        and all(outcome_key[:2] in run_starts for outcome_key in outcomes)
        # and every observed finished test call has at least one command
        # outcome (a start/finish pair with no outcomes is incomplete).
        and all(any(outcome_key[:2] == call_key for outcome_key in outcomes)
                for call_key in run_starts))

    return dict(test_runs=test_runs, test_failures=test_failures,
                complete=complete, test_calls=test_calls)