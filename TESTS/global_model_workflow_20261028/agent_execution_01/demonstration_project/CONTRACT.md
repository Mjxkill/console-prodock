# Audit counter implementation task

Implement only `agent_audit.py`, function `summarize(records)`. This utility
will account commands of protected tests separately from model calls. It is
a pure function, without files, network, processes, clocks, or imports of
the orchestration runtime. Keep the module below1000 physical lines.

Input is a list of dictionaries. Each must have an `event` string. Ignore
events other than `tool_start`, `tool_finish`, `test_finish` (for example
sandbox_start or launcher_exit). Relevant events have nonempty string
`launch_id`, and `request_id` which is a nonempty string or an integer (not
bool). Launch separates otherwise reused request IDs.

`tool_start` / `tool_finish` have a string `name`. Only `name='run_tests'`
participates in test-call completeness. `test_finish` has an integer
`index` in0..1023, integer `returncode` in−255..255 (not bool), and boolean
`timeout` and `output_limited`. The identity of a command outcome is
(launch_id, request_id, index). Count each identity once. Identical repeated
relevant records are tolerated; conflicting repeats of the same identity
raise ValueError. Relevant records may be presented out of order.

Each test_finish must belong to a run_tests start AND run_tests finish of
the same (launch,request), otherwise the overall result is incomplete (do
not drop the observed command). Likewise, a run_tests start without a
finish, a finish without start, or a finished test call with no command
outcomes makes the result incomplete. Other tools do not affect completion.
Empty input is a complete observation of zero tests, not proof of task success.

Return exactly these fields:

- test_runs: number of unique observed command outcomes;
- test_failures: number whose returncode is nonzero OR timeout OR output_limited;
- complete: boolean using the rules above;
- test_calls: number of distinct run_tests request identities in starts OR finishes.

Type errors, missing required fields and conflicting repeats raise ValueError.
Never change the input records. Never invent an unobserved result. Read this
contract and tests, then run the protected tests BEFORE any edit. Their
initial failure is expected because the module is unfinished. Implement the
function, run tests again, inspect any remaining failures and fix them.
