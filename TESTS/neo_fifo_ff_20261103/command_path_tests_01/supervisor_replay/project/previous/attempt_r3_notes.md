# Unvalidated notes of interrupted compaction-heavy attempt
No bench was produced. These are analysis notes, not a proof.

## Goal
- Build and actually execute a Verilator integration bench covering u_commands → cmem → ext_command → real gpu_geometry/v1/child capture, with real R19 source and shadow comparison of the two SDPB-backed banked helpers; produce REPORT/RESULTS/TEST_RECORD/COVERAGE.

## Constraints & Preferences
- Work root `/work`; own only declared `owned/*`; temp compilations only in `/tmp`.
- Inputs immutable/read-only; no edits to snapshot, bindings, banked, evidence, previous, rules.
- No hardware, network, SSH, API, Gowin, routing; no production patch.
- ≤1000 physical lines per new code file; no functions in .h; document contracts/limits/visible failures.
- No fix for an error whose cause is not established (diagnose first); "Pas de correctif pour une erreur dont la cause n'est pas établie."
- Verilator invocation: `--binary --timing -Wno-fatal -j 2 -MAKEFLAGS VM_PARALLEL_BUILDS=0`; run binary from unique `/tmp` dir; bounded watchdog; real script returns nonzero on failed checks.
  - NOTE: must be `-j 2` (space); `-j2` errors `%Error: Invalid option: -j2`.
- Tooling: `awk` NOT installed; use `python3`/`sed` for source extraction. `taskbox_read_file` cannot read `/work/banked/` — use `taskbox_exec` + bash.
- Do NOT insert a synchronous helper after async cmem reads or after head (adds a cycle, changes design).
- Use real R19 archived RTL; banked helper = exact qualified source (assembly 9026b77d...), not abandoned mux helper.
- cmem CEB=1, RESET=0; input FIFO output head absorbed into SDPB (account M_F0..7 absorption).
- Test TARGET/SCISSOR and COPY16x2 with w2/w6=`0x00100002`, independent valid src/dst, nonoverlapping depth.
- Verify all eight words in ext_command, then parent packet, then child packet; especially dimensions and sentinel w7=1.
- Positive baseline + sentinel rejection; clock ratios 80/75 and close unequal 125/124.9 or 125/125.2; finite pauses each clock separately; bursts long enough for real backpressure; reset between independent cases; no force on application state.
- ≥2 independently failing mutants (e.g. swapped word2/word6 dimensions, zeroed dimensions, dropped/duplicated word, removed reserved w7); mutants are tests only, must fail specific packet scoreboard/rejection assertions, not compile errors.
- Must state shadow trace equivalence is NOT full substituted mapped pipeline proof; document untested mapping/STA/card/CDC limits.
- Write REPORT.md checkpoint (gap and plan) first after inspection, then bench/runner; finish reports before expanding cases.
- Delivery structure alone is never quality validation; no cause claim about hardware mask6014 or firstFIFO from simulation.

## Progress
### Done
- Verified environment: `/work/preflight.py` → Verilator 5.020 2024-01-01 (Debian 5.020-1).
- `taskbox_run_tests` currently FAILS: `MISSING_OR_EMPTY REPORT.md` (owned files still 0 bytes; re-confirmed via `ls -la owned` + `wc -c owned/*` all 0).
- Confirmed `/work` layout: CONTRACT.md, INPUTS.json, preflight.py, validate.py read-only; dirs banked/bindings/evidence/owned/previous/primitives/rules/snapshot.
- Listed INPUTS.json files/roles/hashes (snapshot reference x17, banked x4, bindings x3, rules x5, previous x3, evidence x4, primitives vendor_extract).
- Re-read `validate.py`: owned REPORT.md≥800B, TEST_RECORD.md≥400B, bench.sv≥500B, run.py≥100B; `.py/.sv/.v/.c/.h`>1000 lines → `LINE_LIMIT`; RESULTS.json dict with non-empty `cases` list AND non-empty `limits` list; prints `STRUCTURE_ONLY_PASS; supervisor must examine real simulations and mutants`.
- Snapshot line counts: font_ram 21, cdc_word 35, gpu_geom_div 47, gpu_texture_cache 86, gpu_perspective 104, ddr_dcfifo 137, gpu_copy565 156, gpu_blit_dma 173, gpu_triangle 203, gpu_accel 285, gpu_raster 444, gpu_v1 629, gpu_geometry 645, blitter 675 (3640 total).
- Re-read `bindings/CONTRACT.md`/MAPPING.json: two Neo command storages; `u_accel.u_commands` SDPB (CLKA=vid_hclk/CLKB=gpu_clk, CEA=mem_10/CEB=pop, RESET=n249_5) and `u_accel.u_blitter` cmem SDPB (gpu_clk/gpu_clk, CEA=cmem_5/CEB=VCC, RESET=GND); SDPB 32/32, READ_MODE=0, SYNC, BLK_SEL 000, OCE=0; ADA/ADB[13:12]=0,[11:5]=7 addr bits, ADA[4:0]=01111, ADB[4:0]=00000; physical 512×32 only 128×32 addressable; source VG `console_neo.vg` sha256 `76d56bd4...`.
- Re-read `banked/banked_words32.v` (module `neo_command_ff128`): 128 words, write_enabled=CEA&&BLKSELA==0, CE=write_enabled&&ADA[11:5]==slot&&ADA[bit/8], DFFRE FFs, row LUT4 on ADB[5:8], bank LUT3 on ADB[9:11], 8×16 one-hot, output mux.
- Re-read gpu_accel.v: mrst 2-stage, engine_resetn[11:0] (reset copy per engine), bus_addr decode, queue_full registered; ports incl FONT_FILE, mem_clk DDR side, observe_packet_words[63:0].
- Re-read ddr_dcfifo.v: Neo-only isolation — 100-bit cmd + 64-bit resp four-slot use explicit FFs; params WIDTH/DEPTH_LOG2 (512 words=9); wr_lost, wr_full registered, wr_count pessimistic; head latency unchanged.
- Re-read blitter.v internals: `cmem[0:127]`, `cmd_full=(fill>120)`, `cmd_avail=(fill>=8)`, `cmem[wp[6:0]]<=cmd_data`, opcode localparams M_IDLE..M_FILL_WAIT; **ext_command assembly line 294** `{txt,{xs,ys},{x1,y1},{x0,y0},{op,dpage,spage,c0,c1}}`; row_addr fn = base + y*(WIDTH/2) + x[10:1]; page base PAGE_BASE_WORDS + dpage×0x80000 halfwords; opcode decode line 146: rect={1,2,3,4,8,9,11,13}, line=5, circle={6,7}, triangle=10, affine=12, extended={22..34}; ext_start/ext_active/ext_done; COPY states M_COPY_RD/M_COPY_SEG/M_COPY_WAIT.
- Re-read gpu_geometry.v DECODE (~255-345): captures `captured_command<=command`; `mesh_vertex_end={1'b0,command[63:32]}+{12'b0,command[127:112],5'b0}`, `mesh_face_end={1'b0,command[95:64]}+{12'b0,command[111:96],5'b0}`; `w0[31:24]<31` → shader pass; `w0[31:24]==22` → `target_w<=w3[31:16]; target_h<=w3[15:0]`; `==25` → material captured.
- Re-read gpu_v1.v decode (lines 250-445): `bad_header<=w0[23:0]!=0 && !(w0[31:24]==26 && w0[23:3]==0 && w0[2:0]<7)`; registered checks scissor_bad/target_bad/material_bad/plane_bad/triangle_bad/clear_bad/invalidate_bad; TARGET op22 sets color_base=w1[29:0], z_base=w2[29:0], width=w3[31:16], height=w3[15:0], color_stride=w4[31:16], z_stride=w4[15:0]; target_bad checks base[4:0], dims, stride<width*2, color_end/z_end>0x400000000, alias; color_end={3'b0,color_base}+color_stride*height; opcodes 22 target,23 scissor,24 texture,25 material,26 plane; state flow IDLE→DECODE_WAIT→DECODE_PIPE→DECODE→(TARGET_WAIT→TARGET_CHECK→TARGET_PIPE→TARGET_VALIDATE | TEX_…); COPY_START→COPY_WAIT (copy_done→copy_bad?BAD:FINISH); copy_sel[3:0] output mux.
- Re-read gpu_copy565.v: 19 states IDLE=0..CAPTURE_WAIT=18; `packet` syn_preserve; `src_end={1'b0,w1}+{17'd0,w3[15:0]}*{17'd0,w2[15:0]}`; `dst_end={3'b0,dst_base}+{17'd0,dst_stride}*{17'd0,dst_height}`; descriptor_bad; COPY_WAIT0=5'd7; u_copy instance in gpu_v1 line 98.
- Read previous/geometry_tb.sv: dual-profile (`ifdef NEO`), no force, internals observed; P_TARGET/P_SCISSOR/P_COPY constants (color 0x12000020, depth 0x12000040, 16x1, stride 32); READ_ADDR=WRITE_ADDR=29'h04800008; PASS_STATE_BIT=1, COPY_WAIT0=7, FIRST_VALID_BOUND=40, COMPLETION_BOUND=400, NEGATIVE_WAIT=96.
- Read evidence/banked_assembly.json: passed=true, netlist_sha256 `9026b77d...`, base_sha256 `76d56bd4...`, helper_sha256 `e5c576bd...`, helper_instance_count=2, SDPB_removed=2, removed_defparams=12, application_inverse_exact=true, connection_changes=0, other_RAM_replacements=0; constraints neo.cst `6330c9dd...`, neo.sdc `c8da535e...`, inherited_INS_LOC_count=190.
- Read evidence/sentinel.json + reject.json + fifo_tail.json: hardware identity (Neo USB 3-4.4.1 serial 2025041420 FTDI 0403:6010; ESP 3-4.4.2; programmer_busdev 3:102), pre_program_gpu counters (errors=0, queue_lost=0, raster_rejected=0, v1_rejected=1, geometry_rejected=0, done=3, status=0, host_words=24); reject.json diagnostic_only, sta_qualified=false, fpga_load_attempts=1, files_programmed_to_flash=0.
- Verilator capability test in `/tmp/hier` (prior): `--binary --timing -Wno-fatal -j 2 -MAKEFLAGS VM_PARALLEL_BUILDS=0` works; hierarchical refs + forcing a reg in initial block OK.

### In Progress
- Finalizing bench interface/plan from re-read RTL (blitter ext_command source, geometry DECODE, v1 decode/target checks, copy565 states) before writing owned files.

### Blocked
- (none)

## Key Decisions
- Boundary approach: prefer full `gpu_accel.v` (all deps provided); fallback = monitor real workload memory pins + instantiate both banked helpers in shadow with exact SDPB pin contract, asserting registered DO equals expected/consumed words (accounting M_F0..7 head absorption).
- Two physical SDPB bindings: `u_accel.u_commands` and `u_accel.u_blitter` cmem; cap physical 512×32 but only 128×32 addressable.
- Verify word order at three stages (ext_command → parent packet → child packet) rather than only transaction registers.
- Observation method: read internals via Verilator hierarchical references (confirmed working); do not add ports/modify immutable sources.

## Next Steps
1. Write `owned/REPORT.md` checkpoint (gap, boundary choice, plan, hash citations).
2. Implement `owned/bench.sv`, `owned/helpers.sv` (if needed), `owned/build.py`, `owned/run.py`, `owned/mutations.py`.
3. Compile in `/tmp` with Verilator (`-j 2`); run from unique `/tmp` dir.
4. Run test script; correct own bench errors; retain failures.
5. Fill `owned/RESULTS.json` (non-empty `cases` + `limits`), `owned/TEST_RECORD.md`, `owned/COVERAGE.json`; finish reports before expanding cases.

## Critical Context
- Command format (8 words of 32b): w0={op[31:24],pdst[23:20],psrc[19:16],c0[15:8],c1[7:0]}; w1={x0[31:16],y0[15:0]}; w2={x1/width/radius[31:16],y1/height[15:0]}; w3={xs,ys}; w4-7 reserved except TEXT; sentinel w7=1.
- blitter ext_command word order (line 294): {txt[127:0], xs,ys, x1,y1, x0,y0, op,dpage,spage,c0,c1} — 8 words, LSB word packs op/colors.
- gpu_geometry TARGET(op22) dims from w3: target_w=w3[31:16], target_h=w3[15:0]; material op25; shader pass for w0[31:24]<31 except 22/25 captures.
- gpu_v1 header reject: `w0[23:0]!=0` invalid unless plane op26 with `w0[23:3]==0 && w0[2:0]<7`; scissor_bad[0] w1[31:16]>w2[31:16]||w2>width, [2] target_valid must hold & w3..w7==0; target_bad[0] base[4:0]==0, [2] stride≥width*2, [3] color_end/z_end≤0x400000000, [4] no color/z overlap.
- gpu_copy565 COPY_WAIT0=7; dst_end uses dst_base+dst_stride*dst_height; overlap=w1<dst_end && dst_base<src_end; u_copy wired in gpu_v1 at line 98 with ready/rd_valid gated by state[COPY_WAIT].
- Existing gaps: geometry bench injects assembled packets; ACCEL_QUEUE compares only transaction-register blocks — neither covers u_commands→cmem→ext_command→real child.
- SDPB params: BIT_WIDTH_0/1=32, READ_MODE=0, RESET_MODE="SYNC", BLK_SEL_0/1=000, OCE=0; ADA[4:0]=01111, ADB[4:0]=00000, ADA/ADB[13:12]=0, [11:5]=7 addr bits.
- helper hashes: banked_words32.v source `4e8df3bd...`, qualified `neo_command_ff128.vg` `e5c576bd...`; assembly netlist `9026b77d...`; 4096 FF storage + 32 FF output/instance (8192+64 total); SDPB_removed=2, connection_changes=0.
- Toolchain quirks: `-j2` rejected (use `-j 2`); `awk` not installed; `taskbox_read_file` cannot read `/work/banked/` — use `taskbox_exec` + bash.
- cdc_word.v: req/ack toggle handshake, 2-flop synchronizers (wptr/rptr/now/seq).
- font_ram.v: 256 glyphs ×16 rows BSRAM, byte addr=c*16+r, sync read 1-cycle `q`; FONT_FILE param.
- blitter page layout: 800×480×8bpp, 16 page slots 1 MiB at DDR base 0x00800000; PAGE_BASE_WORDS + page×0x80000 halfwords; halfword addressing active-high byte enables; blitter WIDTH/HEIGHT/color params in header.
- validate.py enforces exact minimum sizes and RESULTS.json schema — design owned outputs to satisfy these.

## Relevant Files
- `/work/CONTRACT.md`: task scope, gap, execution rules, required outputs.
- `/work/rules/AGENTS.md`, `AGENT_EXECUTION.md`, `WORKFLOW.md`, `ownership.json`: diagnostic-before-fix, isolation, multi-model workflow rules.
- `/work/INPUTS.json`: sha256 hashes + source paths (preflight checks).
- `/work/preflight.py`: input integrity + Verilator check (OK).
- `/work/validate.py`: structural checks, min sizes, line limit, RESULTS.json schema.
- `/work/snapshot/gpu_accel.v`: preferred full top (all deps provided).
- `/work/snapshot/blitter.v`: cmem FIFO + ext_command producer (ext_command line 294; cmd_full/cmd_avail; opcode decode line 146).
- `/work/snapshot/gpu_blit_dma.v`: halfword/byte-enable → aligned DDR BL8 packer.
- `/work/snapshot/gpu_geometry.v`, `gpu_v1.v`, `gpu_copy565.v`: real child consumers (DECODE/opcode/dim logic examined).
- `/work/snapshot/ddr_dcfifo.v`: upstream CDC queue (Neo FF-isolated head).
- `/work/snapshot/cdc_word.v`, `font_ram.v`: CDC word transfer + programmable font BSRAM.
- `/work/bindings/MAPPING.json`, `bindings/CONTRACT.md`, `bindings/SDPB_REFERENCE.v`: exact SDPB bindings, params, primitive.
- `/work/banked/banked_words32.v` (`neo_command_ff128`), `QUALIFICATION.json`, `COMPARISON.json`, `TEST_RECORD.md`: qualified helper + evidence (read via bash; not `taskbox_read_file`).
- `/work/evidence/`: banked_assembly.json, fifo_tail.json, reject.json, sentinel.json (hardware evidence).
- `/work/previous/geometry_report.md`, `geometry_tb.sv`, `ACCEL_QUEUE_RESULT.json`: prior partial coverage (packet constants, gate behavior).
- `/work/owned/`: writable output dir (bench.sv, helpers.sv, build.py, run.py, mutations.py, REPORT.md, RESULTS.json, TEST_RECORD.md, COVERAGE.json — all empty).
