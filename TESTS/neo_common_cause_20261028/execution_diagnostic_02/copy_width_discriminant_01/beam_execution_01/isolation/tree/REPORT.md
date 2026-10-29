# REPORT (copy_width_discriminant_01)

Official `validate.py`: all 12 modeled cases pass; this is
simulation of unmodified R19 RTL, not hardware proof
(`hardware=false` in validator output).

Observed model outcomes:
- width=16: injections 0 and (healthy seed1/seed8) clear;
  injections 1-4 reject.
- width=1: injections 0 and 2 clear; injections 1, 3, 4 reject.
- All rejections have the same CSR/FIFO tuple:
  done=2, busy=0, reject=1, errors=0, lost=0,
  geom_errors=0, geom_cycles=4, native_requests=0.
- Passes: done=2, busy=0, reject=0, errors=0, lost=0,
  geom_errors=0, geom_cycles=4, native_requests=0.
- Healthy timing seed8 gives the same result for width16
  injection0 and width1 injection2.

Nonidentifiability of identical CSR counts:
- Every injected fault consumes the same CSR counters and has
  native_requests=0 because the requested extent is empty, so there
  is no DMA footprint to distinguish cases.
- The same reject count for faults 1-4 means target validity,
  COPY-local source-width bit, child copy status, and bad header
  cannot be separated by current CSR.
- geom_cycles=4 increments outside IDLE/PASS and therefore exposes
  no timestamp for pixel validation depth.
- descriptor_bad and target_valid are not exposed by any CSR.

Conditional value of width=1:
- Width=1 removes only fault2's trigger in this bounded model; other
  faults remain reject-identical, so it narrows a possible
  data-dependent source-width/clipping path but does not prove the
  synthetic injection2 bit-84 localization. Width also changes packet
  geometry, so it could mask rather than isolate a gate.
- If width=1 still rejects injection2, current CSR cannot identify
  the gate; then the defect is not width-discriminant in this model.

Clock evidence:
- Exact R19 SDC: bus 80 MHz, DDR UI 75 MHz, reference 50 MHz.
- Bench uses ideal 80/75 MHz clocks with two phase models and no
  jitter; reset/phase issues are modeled, not measured.
- DDR bridge HCLK uses clk50, distinct from u_accel clocks, but was
  not physically measured here.

Recommended next test (only):
- Replay injection2 at width=1 under the alternate phase model already
  passing; escalate only if that remains clear, with instrumented
  native-write observation rather than another fault list.