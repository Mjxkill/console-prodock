#!/usr/bin/env python3
"""Freeze a coherent text-only reset patch review packet for three reviewers."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CAND = HERE / 'candidate_01'
PARENT = ROOT / 'tang/impl/console_neo_n56r21r1_capture_memory'
OUT = HERE / 'patch_review_packet_01'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    proof = json.loads((HERE / 'root_phase_sweep_01/result.json').read_text())
    assert proof['passed'] and len(proof['phases']) == 4
    for name, digest in proof['inputs'].items():
        assert sha(Path(name)) == digest, name
    OUT.mkdir(exist_ok=False)
    header = '''RESET PATCH REVIEW — R21r1 isolated Neo candidate; no hardware loaded.

Please challenge the RTL patch, not a hypothetical Gowin LW erratum. All three
reviewers receive this same frozen packet. Do not claim tool execution.

Established parent defect: real50MHz/80MHz ideal-clock simulations of the
extracted reset chain reproduced (a) stale delay qualification after a LOCK
loss between clk50 edges, (b) one-cycle POR release while delay_done=0 after a
sampled loss. These were also present in R19. This does NOT establish that a
LOCK loss caused the physical R21 black-screen/DMI failure. No CPU/PLL analog
model is substituted by the tests. R19 is still the physical fallback.

Patch intent: asynchronously invalidate two clk50 readiness synchronizer bits
on availability loss; require a new qualification; clear BOTH existing AHB
POR stages on permission loss. Normal mode50ms nominal. Diagnostic mode0 now
2.08ms nominal (it used to bypass the delay). Valid UART reset commands retain
their framing and reset-hold handshake. PLL and DDR resets are not changed.

Primary-doc basis: UG306-1.0.9E page40/table5-2 note asks to monitor LOCK
continuously for at least2ms; LOCK can glitch during locking. No quantitative
AE350 POR/HW duration was found in MUG1031-1.3.1E. The20ms precedent is a Sipeed
example debounce block fed by DDRready, not a proved vendor minimum. User
selected50ms margin. DS1239 table3-13 gives SR-to-Q delay, NOT a minimum fabric
reset pulse width. Its10ns RSTMIN-PULSE is the PLL specification. Thus an ideal
RTL1ns test does not establish physical1ns pulse capture.

Evidence provenance: the four root phase runs below use the supplied frozen
v2 bench and the exact candidate source hashes, checked against Verilator's
source-size/mtime build record. Phase sweep15 releases each includes valid and
invalid UART, expired parser prefix, mode0/1, AHB stopped with warm-reset
command, reference clock stopped with LOCK loss, DDR loss. All4 passed. The
three ordinary phases and mapped primitive synthesis/test are being completed
separately; they are NOT evidence claimed by this packet.

The older v1 bench timed out after CASE14 because align_reference waited for
$time%100==0 after restarting clk50 at a changed phase. v2 removes only this
unnecessary rendezvous. Old v1 logs are deliberately NOT mixed into this
packet. The broad dual-board suite is11groupsPASS, distinct from this helper
and physical qualification. SDC inherited from parent below; no new exception
has been added. Local reset/CDC timing still requires post-route inspection.

Requested output: concrete counterexample if any, source/line citations,
distinguish proven RTL behavior from analog limits and missing evidence. Say
whether the current patch is coherent enough to synthesize/route as a candidate,
not whether the Neo failure is solved. Avoid generic refactoring or a new clock
architecture unless a counterexample actually requires it.
'''
    entries = []
    chunks = [header]

    def include(path, start=None, end=None):
        lines = path.read_text().splitlines()
        lo = 1 if start is None else start
        hi = len(lines) if end is None else end
        name = str(path.relative_to(ROOT))
        digest = sha(path)
        entries.append(dict(path=name, sha256=digest, first_line=lo, last_line=hi))
        chunks.append(f'\nFILE {name}\nSHA256 {digest}\n')
        chunks.extend(f'{i}: {lines[i-1]}\n' for i in range(lo, hi+1))

    for name in ('candidate.diff', 'neo_reset_trial.v', 'neo_reset_trial_rx.v',
                 'exact_chain.sv', 'invariants_tb.sv', 'candidate_manifest.json'):
        include(CAND / name)
    include(PARENT / 'source/tang/boards/neo/neo_reset_trial.v')
    include(PARENT / 'source/tang/boards/neo/console_neo.v', 140, 179)
    include(PARENT / 'source/tang/rtl/board/ae350_soc.v', 151, 157)
    include(PARENT / 'source/tang/boards/neo/neo.sdc')
    include(HERE / 'root_phase_sweep_01/result.json')
    for phase in proof['phases']:
        folder = HERE / 'root_phase_sweep_01' / ('phase_' + str(phase['phase_ps']))
        assert sha(folder / 'simulation.log') == phase['log_sha256']
        assert sha(folder / 'events.csv') == phase['events_sha256']
        include(folder / 'simulation.log')
        include(folder / 'events.csv')
    text = ''.join(chunks)
    assert len(text.encode()) < 200000
    packet = OUT / 'packet.txt'
    packet.write_text(text)
    manifest = dict(packet_sha256=sha(packet), packet_bytes=len(text.encode()),
                    files=entries, hardware_access=False,
                    builder_sha256=sha(Path(__file__)))
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k:v for k,v in manifest.items() if k != 'files'}))


if __name__ == '__main__':
    main()
