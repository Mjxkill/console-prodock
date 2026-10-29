# Independent executable tests of the ILM reader and partial journals

You own adversarial.py and ANALYSIS.md only. All payload, model, decoder,
hardware journals and protected test_reader.py are read-only. No hardware,
network, keys, vendor builds or edits outside these two files. New files
stay <=1000 lines. Owner/reviewer is /root/game_visual_followup.

The reader binary has already passed8local tests. Your job is additional
concrete executable tests, not another opinion. Use unittest with at least
10individual non-skipped tests; test_reader.py runs the real compiled reader
through the bounded RV32 interpreter and then your tests. The full command
is prevalidated in the actual isolation before launch. Initial failure is
the intentional adversarial.py stub. Do not weaken tests or change protected
files to make a result pass. A discovered production defect must be reported
with failing reproduction; leave task FAIL rather than hiding it.

Read readback_r1/readback.S, readback_model.py, decode.py, HARDWARE_RUN03.md
and original readback README. Reader code is atILMa0005000; journal256B at
a0006400; old journal512B at a0006000. DDR reads only128B12000000..7f.
Result1 means CPU32loads complete, NOT GPU success. GPU may remain busy/done1
with a correct image or seed unchanged. These are observations to separate.

Implement and execute meaningful missing cases, including:
- mstatus.MIE or mie or satp nonzero each causes guard refusal before DDR;
- wrong old journal identity/version/counts causes refusal, never oldjournalwrites;
- an AHB framebuffer guard nonzero via a narrow Reader.access subclass;
- completed journal with one data/header/count/first-error mutation must not
  silently appear consistent; wrong size/magic/version and negative result;
- real run02 and run03 original MD12 journals are incomplete CLEAR (0words)
  even though image iszero: they are not measurements of DDRclear or corruption.
- a CPUload bus hang may hit interpreter instruction/exception bound and
  must not be labeled completed; a trap after some loads leaves partial evidence.
- no commands, GPUwrites, DDRstores or writes oldjournal in any testedcase.

Import Reader from readback_model (test launcher adds its directory tosys.path).
It accepts binary,scenario andcache/milmb kwargs. CPU.csrs is actually cpu.csr;
set registers there before run. It records accesses as(write,address,value),
ddr_reads and commands. Oldjournal memory can be altered withcpu.put before
execution. Snapshot oldjournal for comparison AFTER your deliberately changed
preconditions, not the default constructor's oldsnapshot. The actual binary
must be used, never replace it with a mock function. Use importlib for MD12
decode_journal.py to avoid confusing its512B ABI with new256B reader ABI.

Do not infer FPGA root cause from a pure software test. Report cases, actual
results and remaining limitations (physicalCSR/cache/DDR/arbitration notmodeled).
If a decoder classification issue is found, provide exact case and impact.
