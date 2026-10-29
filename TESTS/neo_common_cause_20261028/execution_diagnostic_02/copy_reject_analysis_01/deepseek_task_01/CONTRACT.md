# R19 COPY rejection: bounded independent descriptor bench

Owner Codex game_visual_followup. No hardware, synthesis, routing, network,
credentials, project edits, package installs or RTL edits. Author bench.sv and
ANALYSIS.md only, each <=1000 physical lines. Exact gpu_copy565.v is read-only.

Hardware: exact COPY test submitted TARGET then COPY, done2/status0/rejected1.
The firmware phase8/result-5 ALSO covers rejection, not necessarily timeout.
Its final memory image was not read. Prior exact-RTL full chain accepted the
same packets and one32B read/write. The current goal is characterize rejection
gates and missing adversarial coverage, not claim the hardware cause.

Implement a standalone actual gpu_copy565 instance and external native memory
terminal. Input cases.hex has14cases,15words percase:8commandwords,dst_base,
dst_stride,dst_height,clip_l,clip_t,clip_r,clip_b. +case=N selects one. Read
cases.json for external oracle. All commands have destination16x1 source x/y0.

Reset for several edges, pulse start with command stable; deadline1000cycles.
Memory ready is high. Accepted READ produces a 256-bit response after several
cycles: each32-bit word=(source byte address+4*index)^a5396c17. The valid board
case must read native word04800000 and write04800008,32B mask0,payload exact.
Count requests only on valid&&ready; preserve a read response until its one
cycle rd_valid. Bad descriptors and zero extent must emit no native traffic.
Check done once, bad, count and payload via actual output ports. Wait20cycles
after done to catch late transactions. Any unexpected address/command/data is
a failure, not just an informational print. No force/deposit into DUT.

Print one RESULT line matching the protected validate.py schema. It must
report actual measurements; never hardcode expected output or bypass the DUT.
You may also display observed descriptor_bad/state at CHECK/VALIDATE for the
analysis (simulation-only observability). Interpret dimensions high16=width,
low16=height; source_end=src+stride*height, strict interval-overlap test. A
source_end equal to destination_base is disjoint and should be accepted.

Run taskbox_run_tests before implementation (scaffold intentionally lacks
bench) and after all code/report edits. Toolchain/harness compilation has been
prevalidated by supervisor. Write precise predicates for all rejection paths,
check exact board values numerically, and list what the RTL bench cannot
distinguish on hardware: target_valid, captured packet/fields, synthesized
arithmetic/enables, transient reset/state. Do not attribute any FIFO/timing/
DDR fault without a concrete reproduction. Do not repeat the full system bench.
