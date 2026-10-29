"""Strict counters for trusted taskbox audit records.

``summarize(records)`` implements the counting rules of CONTRACT.md for the
audit event stream emitted by the protected test harness.

Rules implemented here (all of them come from CONTRACT.md):

* Only ``tool_start``, ``tool_finish`` and ``test_finish`` are *relevant*
  events.  Every other event (for example ``sandbox_start`` or
  ``launcher_exit``) is ignored completely, payload included: such records
  carry no ``launch_id``/``request_id`` and must never raise.
* Every relevant record must carry a nonempty string ``launch_id`` and a
  ``request_id`` that is either a nonempty string or an integer (``bool`` is
  not accepted as an integer here).
* ``tool_start``/``tool_finish`` additionally carry a string ``name``; only
  ``name == 'run_tests'`` takes part in the test-call bookkeeping.  Other
  tools never influence the result.
* ``test_finish`` carries an ``index`` in ``0..1023``, a ``returncode`` in
  ``-255..255`` and the booleans ``timeout`` and ``output_limited``.
* The identity of a command outcome is ``(launch_id, request_id, index)``.
  Repeated identical outcomes are tolerated and counted exactly once; a
  repeat of the same identity that disagrees about the payload is a
  conflict and raises ``ValueError``.
* Relevant records may arrive in any order, so the bookkeeping is done with
  sets and never depends on the position of a record.
* The function is pure: the input records are never mutated and no result is
  ever invented for an observation that has not been made.

Type errors, missing required fields and conflicting repeats all raise
``ValueError`` (never ``TypeError``), as required by the contract.
"""

# Events that carry audit information; everything else is ignored.
RELEVANT_EVENTS = frozenset(('tool_start', 'tool_finish', 'test_finish'))

# Tool events.
TOOL_START = 'tool_start'
TOOL_FINISH = 'tool_finish'

# Command outcome events.
TEST_FINISH = 'test_finish'

# The only tool whose calls are counted as test calls.
TEST_TOOL_NAME = 'run_tests'

# Inclusive bounds for the numeric outcome fields.
MIN_INDEX = 0
MAX_INDEX = 1023
MIN_RETURNCODE = -255
MAX_RETURNCODE = 255

# Sentinel for "no value stored yet" in the outcome table.
_MISSING = object()


def _is_int(value):
    """Return True for real integers; ``bool`` is explicitly not an int here."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_bool(value):
    """Return True only for genuine booleans (``0``/``1`` are rejected)."""
    return isinstance(value, bool)


def _require_event(record):
    """Return the event name of ``record`` or raise ValueError."""
    if not isinstance(record, dict):
        raise ValueError('audit record must be a dictionary, got %r' % (type(record).__name__,))
    if 'event' not in record:
        raise ValueError('audit record is missing the required field "event"')
    event = record['event']
    if not isinstance(event, str):
        raise ValueError('audit record field "event" must be a string, got %r' % (event,))
    return event


def _require_launch_id(record):
    """Return a validated nonempty string launch id."""
    if 'launch_id' not in record:
        raise ValueError('audit record is missing the required field "launch_id"')
    launch_id = record['launch_id']
    if not isinstance(launch_id, str) or not launch_id:
        raise ValueError('audit record field "launch_id" must be a nonempty string, got %r' % (launch_id,))
    return launch_id


def _require_request_id(record):
    """Return a validated request id (nonempty string or integer, not bool)."""
    if 'request_id' not in record:
        raise ValueError('audit record is missing the required field "request_id"')
    request_id = record['request_id']
    if _is_bool(request_id):
        raise ValueError('audit record field "request_id" must not be a bool, got %r' % (request_id,))
    if isinstance(request_id, str):
        if not request_id:
            raise ValueError('audit record field "request_id" must be a nonempty string, got %r' % (request_id,))
    elif not isinstance(request_id, int):
        raise ValueError('audit record field "request_id" must be a string or an integer, got %r' % (request_id,))
    return request_id


def _require_name(record):
    """Return a validated tool name."""
    if 'name' not in record:
        raise ValueError('audit record is missing the required field "name"')
    name = record['name']
    if not isinstance(name, str):
        raise ValueError('audit record field "name" must be a string, got %r' % (name,))
    return name


def _require_index(record):
    """Return a validated command index in ``0..1023``."""
    if 'index' not in record:
        raise ValueError('audit record is missing the required field "index"')
    index = record['index']
    if not _is_int(index):
        raise ValueError('audit record field "index" must be an integer, got %r' % (index,))
    if index < MIN_INDEX or index > MAX_INDEX:
        raise ValueError('audit record field "index" must be within %d..%d, got %r'
                         % (MIN_INDEX, MAX_INDEX, index))
    return index


def _require_returncode(record):
    """Return a validated return code in ``-255..255``."""
    if 'returncode' not in record:
        raise ValueError('audit record is missing the required field "returncode"')
    returncode = record['returncode']
    if not _is_int(returncode):
        raise ValueError('audit record field "returncode" must be an integer, got %r' % (returncode,))
    if returncode < MIN_RETURNCODE or returncode > MAX_RETURNCODE:
        raise ValueError('audit record field "returncode" must be within %d..%d, got %r'
                         % (MIN_RETURNCODE, MAX_RETURNCODE, returncode))
    return returncode


def _require_flag(record, field):
    """Return a validated boolean flag (``timeout``/``output_limited``)."""
    if field not in record:
        raise ValueError('audit record is missing the required field %r' % (field,))
    value = record[field]
    if not _is_bool(value):
        raise ValueError('audit record field %r must be a boolean, got %r' % (field, value))
    return value


def _collect(records):
    """Fold the relevant records into the three observation tables.

    Returns a tuple ``(starts, finishes, outcomes)`` where ``starts`` and
    ``finishes`` are sets of ``(launch_id, request_id)`` request identities
    of ``run_tests`` calls and ``outcomes`` maps a command identity
    ``(launch_id, request_id, index)`` to its payload
    ``(returncode, timeout, output_limited)``.
    """
    starts = set()
    finishes = set()
    outcomes = {}

    for record in records:
        event = _require_event(record)
        if event not in RELEVANT_EVENTS:
            # Lifecycle noise carries no audit payload; ignore it entirely.
            continue

        launch_id = _require_launch_id(record)
        request_id = _require_request_id(record)

        if event in (TOOL_START, TOOL_FINISH):
            name = _require_name(record)
            if name != TEST_TOOL_NAME:
                # Other tools neither count nor affect completeness.
                continue
            if event == TOOL_START:
                starts.add((launch_id, request_id))
            else:
                finishes.add((launch_id, request_id))
            continue

        # event == TEST_FINISH: a command outcome.
        index = _require_index(record)
        payload = (_require_returncode(record),
                   _require_flag(record, 'timeout'),
                   _require_flag(record, 'output_limited'))
        identity = (launch_id, request_id, index)
        previous = outcomes.get(identity, _MISSING)
        if previous is _MISSING:
            outcomes[identity] = payload
        elif previous != payload:
            raise ValueError('conflicting repeats of command outcome %r' % (identity,))

    return starts, finishes, outcomes


def summarize(records):
    """Summarise audited test-command activity.

    Parameters
    ----------
    records:
        A list of audit record dictionaries.  Every record needs a string
        ``event``; only ``tool_start``, ``tool_finish`` and ``test_finish``
        are relevant and are fully validated.

    Returns
    -------
    dict
        Exactly the keys ``test_runs`` (unique observed command outcomes),
        ``test_failures`` (outcomes with a nonzero return code, a timeout or
        truncated output), ``complete`` (whether every observed run_tests
        call is fully bracketed and carries outcomes) and ``test_calls``
        (distinct run_tests request identities seen in a start or a finish).

    Raises
    ------
    ValueError
        On type errors, missing required fields or conflicting repeats.
    """
    if not isinstance(records, (list, tuple)):
        raise ValueError('records must be a list of audit dictionaries, got %r'
                         % (type(records).__name__,))

    starts, finishes, outcomes = _collect(records)

    # Distinct run_tests request identities seen in a start or a finish.
    calls = starts | finishes

    # Unique observed command outcomes and their failures.
    test_runs = len(outcomes)
    test_failures = 0
    for returncode, timeout, output_limited in outcomes.values():
        if returncode != 0 or timeout or output_limited:
            test_failures += 1

    # Completeness: every observed outcome must belong to a run_tests call
    # that has both a start and a finish, and every finished run_tests call
    # must have observed at least one command outcome.
    complete = True
    for launch_id, request_id in calls:
        if (launch_id, request_id) not in starts or (launch_id, request_id) not in finishes:
            # A start without a finish or a finish without a start.
            complete = False
            continue
        if not any(key[0] == launch_id and key[1] == request_id for key in outcomes):
            # A finished test call with no command outcomes.
            complete = False

    for launch_id, request_id, _index in outcomes:
        if (launch_id, request_id) not in starts or (launch_id, request_id) not in finishes:
            # An outcome without a bracketing run_tests start and finish.
            complete = False
            break

    return dict(test_runs=test_runs,
                test_failures=test_failures,
                complete=complete,
                test_calls=len(calls))
