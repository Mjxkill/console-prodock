# Console project dashboard

A read-only HTTP dashboard for Pro Dock Linux/SD boot, the Neo port, games,
feature tests, evidence and delegated workers. It uses Python's standard library
and a browser EventSource connection (SSE).

From the repository root:

```sh
python3 -B -u tools/project_dashboard/server.py --bind 127.0.0.1 --port 8088
```

Open `http://127.0.0.1:8088/`. To share within your tailnet, replace the bind
address with this host's own Tailscale IPv4 address (inspect `tailscale ip -4`).
Do not copy the development workstation's private address. The server has no
separate public authentication system; use localhost or access-controlled
private networking, not an unauthenticated public internet listener.

## Data and interpretation

- `data.json` is the maintained project registry: features, stages, versions,
  evidence, labels and next actions. A person updates decisions/results; the
  collector does not invent a plan or completion percentage from logs.
- `collector.py` checks the registry and explicitly referenced result files.
  Missing, malformed or mismatched evidence becomes unknown. Historical results
  do not qualify changed inputs.
- `workers.py` checks PID/start-time identity and OpenCode descendants. A stale
  file saying `running` is insufficient. Unknown counters remain unknown;
  intermediate failed tests do not necessarily mean a task ultimately failed.
- Current new Ollama assignments use DeepSeek v4.1 Flash and GLM 5.3 Flash.
  Historical other-model results retain their real identity.
- Remote observations are dated imported evidence. The service does not connect
  over SSH, poll a board, read USB/JTAG, start agents or modify FPGA/SD state.

The browser receives changes through `/api/events`, with a heartbeat between
changes and automatic reconnect after interruption. Collection runs roughly
once per second, subject to machine/network load. Reconnection does not turn
old evidence into a new hardware observation. Registry edits need no restart;
Python module edits require a server restart.

A fresh clone will lack many local lab reports referenced in `data.json`. Adapt
the registry and accept unknown/missing entries; do not label them PASS simply
to populate the dashboard.

## Views and access boundaries

The interface exposes workstream summaries, feature/test filters, worker state,
history and build information. Software, simulation, timing, hardware and visual
results stay distinct, including unfavorable results.

Only explicitly allowed evidence is served through `/api/evidence`; there is no
directory browser. Large content is explicitly truncated and not misrepresented
as the complete file. Worker details show selected identities/measurement sources,
not command lines, prompts or provider secrets.

## Validation

```sh
python3 -B -m unittest discover -s tools/project_dashboard -p 'test_*.py'
node --check tools/project_dashboard/app.js
```

Historical browser/Tailscale validation lives under
`TESTS/project_dashboard_20261030/`; it is separate from the FPGA regression.
No physical board is needed for these local service tests.
