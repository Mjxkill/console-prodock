"""Strict counters for trusted taskbox audit records.

``summarize(records)`` implements CONTRACT.md: it audits how many protected
acceptance-test commands (``run_tests`` tool calls plus their per-command
``test_finish`` outcomes) were actually observed, separately from model-call
bookkeeping.  This is a pure utility: no imports, no files, no network, no
processes, no clocks, and no dependency on the orchestration runtime.  The
input records are never modified, and no unobserved result is ever invented.
"""

# Only these events participate in the audit.  Every other event string
# (for example sandbox_start or launcher_exit) is ignored entirely, although
# each record must still carry a string ``event`` field.
_RELEVANT_EVENTS = ('tool_start', 'tool_finish', 'test_finish')

# Inclusive bounds required by the contract for test_finish fields.
_MAX_TEST_INDEX = 1023
_RETURN_CODE_LOW = -255
_RETURN_CODE_HIGH = 255


def _require(condition, message):
    """Raise ValueError (never TypeError) when a record breaks the contract."""
    if not condition:
        raise ValueError(message)


def _is_plain_int(value):
    """True for genuine integers only; bool subclasses int and is rejected."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_valid_request_id(value):
    """request_id must be a nonempty string or a genuine integer (no bool)."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, str) and value != ''


def summarize(records):
    """Count observed test-command outcomes for an audited session.

    Returns exactly four fields:
      test_runs      -- number of unique observed command outcomes, where the
                        identity of an outcome is (launch_id, request_id, index);
      test_failures  -- how many of those have a nonzero returncode OR timed
                        out OR had their output limited;
      complete       -- True only when every test_finish belongs to a run_tests
                        start AND finish of the same (launch, request), every
                        run_tests start has a finish and vice versa, and every
                        finished run_tests call saw at least one command
                        outcome.  Empty input is a complete zero-test view.
      test_calls     -- number of distinct run_tests request identities seen in
                        tool_start OR tool_finish records.

    Type errors, missing required fields, and conflicting repeats of the same
    identity raise ValueError.  Identical repeated relevant records are
    tolerated (idempotent).  Records may arrive out of order; results are
    order-independent.  The input list and its records are never mutated, and
    outcomes observed against an incomplete lifecycle are still counted (only
    the ``complete`` flag drops to False).
    """
    if not isinstance(records, list):
        raise ValueError('records must be a list of dictionaries')

    tool_seen = {}    # (event, launch_id, request_id) -> first record seen,
                      # used to tolerate identical repeats and reject conflicts
    starts = set()    # (launch_id, request_id) of run_tests tool_start records
    finishes = set()  # (launch_id, request_id) of run_tests tool_finish records
    outcomes = {}     # (launch_id, request_id, index) -> first test_finish

    for record in records:
        if not isinstance(record, dict):
            raise ValueError('each record must be a dictionary')
        if 'event' not in record:
            raise ValueError('record is missing the event field')
        event = record['event']
        if not isinstance(event, str):
            raise ValueError('event must be a string')
        if event not in _RELEVANT_EVENTS:
            continue  # lifecycle noise and unrelated tools never affect counts

        # Common required fields for every relevant event.
        launch_id = record.get('launch_id')
        _require(isinstance(launch_id, str) and launch_id != '',
                 'launch_id must be a nonempty string')
        request_id = record.get('request_id')
        _require(_is_valid_request_id(request_id),
                 'request_id must be a nonempty string or a genuine integer')

        if event == 'test_finish':
            # Per-command outcome fields with strict types and ranges.
            index = record.get('index')
            _require(_is_plain_int(index) and 0 <= index <= _MAX_TEST_INDEX,
                     'index must be an integer in 0..1023, not bool')
            returncode = record.get('returncode')
            _require(_is_plain_int(returncode)
                     and _RETURN_CODE_LOW <= returncode <= _RETURN_CODE_HIGH,
                     'returncode must be an integer in -255..255, not bool')
            timeout = record.get('timeout')
            _require(isinstance(timeout, bool), 'timeout must be boolean')
            output_limited = record.get('output_limited')
            _require(isinstance(output_limited, bool),
                     'output_limited must be boolean')
            identity = (launch_id, request_id, index)
            prior = outcomes.get(identity)
            if prior is None:
                outcomes[identity] = record  # count each identity once
            elif prior != record:
                # Same identity but not an identical repeat: conflicting data.
                raise ValueError('conflicting repeat of outcome identity %r'
                                 % (identity,))
        else:
            # tool_start / tool_finish carry the tool name.
            name = record.get('name')
            _require(isinstance(name, str),
                     'tool records require a string name')
            identity = (event, launch_id, request_id)
            prior = tool_seen.get(identity)
            if prior is None:
                tool_seen[identity] = record
            elif prior != record:
                raise ValueError('conflicting repeat of tool identity %r'
                                 % (identity,))
            if name == 'run_tests':
                # Only run_tests participates in test-call completeness.
                if event == 'tool_start':
                    starts.add((launch_id, request_id))
                else:
                    finishes.add((launch_id, request_id))

    # Unique observed outcomes; failures use contract rules (rc != 0, timeout,
    # or limited output), even when the surrounding lifecycle is incomplete.
    test_runs = len(outcomes)
    test_failures = 0
    for record in outcomes.values():
        if record['returncode'] != 0 or record['timeout'] or record['output_limited']:
            test_failures += 1

    # Complete only when starts, finishes, and calls with observed outcomes
    # describe exactly the same set of (launch, request) identities; empty
    # input therefore reports a complete observation of zero tests.
    observed_calls = {identity[:2] for identity in outcomes}
    complete = starts == finishes == observed_calls

    return {
        'test_runs': test_runs,
        'test_failures': test_failures,
        'complete': complete,
        'test_calls': len(starts | finishes),
    }