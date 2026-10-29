# Task neo_copy_same_base_boundaries_01

Parent neo_target_clear_copy_01; owner root/game_visual_followup. Domainfpga,
test_design, difficulty low. Only cases.py and REPORT.md writable; no hardware.
Use official taskbox_run_tests before edits and after the final edit.
Implement cases() as a readable function constructing10explicit mutations
from the ABI, independent expected bad values. Protected expected.json lists
the required exact records and order. Keep all requested extents zero. Run
actual RTL through protected validate.py; no fake pass summaries.

Facts measured by root: R19 bitstream1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c.
MD13 TARGET→CLEAR0→COPY0: CLEARdone2/rej0, COPYdone3/rej1, CPUphase10/result−5;
32/32/0images means no final memory read; restoredR19true. Prior ordinary
COPY0 also rejected done2/rej1. Native requests NOT exposed on hardware.
New hardware-candidate firmware is EXACT priorMD12 COPY0, only sourcew1
12000000→12000020 (dst base), size16x1/stride32 and requestedextent0×0 unchanged.
This changes src_end as well as the base comparison: no unique physical cause
can be inferred from a future success. No board test is claimed here.

Question: does identical base/stride neutralize the overlap rejection term
while keeping other descriptor checks? Implement tests for baseline, same
base, taller overlapping source with wrong base, taller same-layout source,
same-base stride64, height0, misalignment2, reservedw7, forcedsrc_end12000060
for original and same-base (simulated fault only). Assertions must prove
completion exactlyonce, bad expected, valid never asserted even ready0,
and20cycles postdone. Those controls are protected in bench+validate.

REPORT.md maximum80lines: relevant exact condition, observations10cases,
why forced src_end counterexample is useful but not physical diagnosis,
and limitations. No further experiments or new architecture needed.
Runtime/readiness/packet outputs are real simulation only; do not claim
same-layout valid for every descriptor or global DDR operation.
