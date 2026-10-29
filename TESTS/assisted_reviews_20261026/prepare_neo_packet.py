#!/usr/bin/env python3
"""Create a bounded, sourced diagnostic packet. No hardware or external calls."""
from pathlib import Path
import hashlib
import json
import re

ROOT=Path('/home/michael/console')
HERE=Path(__file__).resolve().parent
B=Path('tang/impl/console_neo_n56r19_capture_ce_local')
T=Path('TESTS/neo_720p_20261012/local_capture_20261026')
sources=[];sections=[]
def digest(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def source(p,label):
    p=Path(p);sid='S%02d'%(len(sources)+1)
    sources.append(dict(id=sid,path=str(p),sha256=digest(p),label=label))
    return sid
def clean(s):return s.replace('/home/michael/console/','<REPO>/').replace('/home/michael/','<LOCAL>/')
def add(label,sid,s):sections.append('\n=== '+label+' ['+sid+'] ===\n'+clean(s)+'\n')
def excerpt(p,label,ranges):
    sid=source(p,label);lines=(ROOT/p).read_text().splitlines();parts=[]
    for a,b in ranges:
        parts.append('\n'.join('%5d %s'%(i,lines[i-1]) for i in range(a,min(b,len(lines))+1)))
    add(label,sid,'\n[... omitted lines ...]\n'.join(parts));return sid
def projection(p,label,keys=None,transform=None):
    sid=source(p,label);d=json.loads((ROOT/p).read_text());d=transform(d) if transform else {k:d[k] for k in keys} if keys else d
    add(label+' (JSON projection)',sid,json.dumps(d,indent=2,ensure_ascii=False));return sid

header='''NEO / R19 — INDEPENDENT ADVERSARIAL FPGA REVIEW PACKET — 2026-10-26

Purpose: diagnose a reproducible native GPU CLEAR stall. Review the evidence and
the actual request protocol, and propose the smallest discriminating next test.
Answer in French. Cite source IDs and line numbers where supplied. Separate facts,
logical deductions, physical hypotheses, and unmeasured signals. Do not announce
a root cause unless the evidence distinguishes it from the competing explanations.
You have no board access in this review. Do not suggest blind new PnR iterations.

Platform and preservation constraints:
- Neo GW5AST-138C, PG484; AE350 core 800 MHz, AHB 80 MHz, DDR3 memory
  clock 300 MHz and GPU/UI 75 MHz. DDR IP 5.9 and Hynix H5TQ4G63EFR parts.
- Working Pro Dock reference uses GW5AST-138B/PG676. Preserve its G22r0
  FPGA and software archives. Shared sources must not receive speculative Neo
  changes. A working Pro Dock is evidence of a working configuration, not proof
  that all Neo RTL snapshots or physical implementations are identical.
- Current exact R19 SRAM bitstream:
  1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c
- Authoritative mapped netlist SHA:
  dfac41d80eecaa0b6a3c152d36d8fcdb902060cecbd450647ede445d1c8004b6
  R19 is R18r1 with one CST LOCAL_CLOCK constraint on the measured pixel
  command-capture enable. The routed cell/pin/INIT comparison has no delta;
  physical locations and interconnect can nevertheless change globally.
- Global timing is FAIL: setup -2.888 ns, hold +0.124 ns, recovery -0.239 ns,
  removal +0.274 ns. This is a deliberate diagnostic image, not a release.
  Do not infer that the global worst path is the CLEAR request path.
- IMPORTANT LIVE-STATE DISTINCTION: the user power-cycled the board AFTER the
  stalled tests. The parent reloaded exact R19 and checked internal HDMI bars,
  halted CPU PC=0x80000004, GPU idle done=0, errors=0. The stall below is
  reproducible historical evidence, not the currently preserved live state.

Key hardware facts, with detailed sources below:
1. R18r1 local capture observed start=1, idle=1 but command-register CE=0,
   followed by opcode Q=0/rejection. After R19 rerouting, nine commands show
   CE=1 and the expected opcode Q on the following edge, without V1 rejection.
   The trace samples opcode bits31:24 only; it is not a complete packet test.
   This does not establish a general LW erratum.
2. CPU DDR preparation/readback succeeds. A legacy FILL writes 32 bytes of
   0xa6 at 0x00800020 correctly, preserving neighbors. TARGET points native
   color at EXACTLY this byte address and Z at 0x00810000.
3. Native CLEAR with flags=0 finishes; an empty rectangle also finishes.
   CLEAR color-only, 16x1 RGB565, 0x5aa5, stays busy with done=4. The same
   32 bytes remain all 0xa6. Error/lost/rejected counters do not increase.
   Four native command captures show the expected opcode. Thus a large
   surface, texture reads, high address range and scanout contention are not
   necessary conditions for this observed stall.
4. Earlier high-address CLEAR stalled similarly. Stable coherent snapshots
   showed queue empty, blitter wp=rp=88, ext_active=1, CLEAR opcode=0x1c,
   blitter waiting in M_SETUP, engine resets released. CPU could still read
   the guarded color/Z/source regions unchanged. That does not prove that
   the GPU issued no write elsewhere, or that native VALID/READY worked.
5. Existing R19 probes DO NOT expose the pixel FSM or native VALID/pending/
   arbiter READY/registered acceptance. Stable asynchronous header reads
   corroborate the stopped command but are not an atomic snapshot.
6. R20/R20r1 attempted observation-only rewiring of 128 existing snapshot
   DATA inputs (no new application logic). Functional mapped tests pass.
   R20r1 PnR failed after 100 minutes with 120 unrouted nets; NO BITSTREAM,
   NO HARDWARE OBSERVATION. Do not treat its planned trace as measured data.
7. Four mapped handshake functions were exhaustively compared to RTL without
   a one-hot assumption: native_issue (2^22 combinations), native_valid next
   (2^11), pending next (2^9), accepted next (2^2). They match assuming reset
   inactive and documented flip-flop D/CE semantics. This excludes those four
   Boolean-expression mismatches, not distribution/timing or payload capture.
8. Prior routed R1 scanout+queue+arbiter first-line functional test passed
   80 ordered DDR reads with backpressure, official primitives, no SDF and
   inactive CPU/drawing. This is NOT a test of R19 native CLEAR or real DDR.
9. HDMI routing was separately isolated: a minimal DCE route at SG0 gave no
   signal while PG0/SG4 worked. R19 internal bars currently work. Neither
   bars nor this separate route experiment qualifies framebuffer reads.

Actual native write chain (single 75 MHz domain after command FIFO crossing):
  pixel RECT_COLOR -> native_issue/native_valid + address/data/mask
  -> geometry shader mux (fetch_valid normally false for passthrough CLEAR)
  -> gpu_accel extended_request -> registered one-entry v1_pending slot
  -> legacy/V1 output mux -> ddr_gpu_arb take_blitter/b_grant
  -> DDR cmd/write enables; accepted -> v1_accepted register -> pixel ready.
The AHB command FIFO has two clocks (80/75 MHz); the native request/acceptance
slot and DDR arbiter do not form an asynchronous FIFO. Do not assume a CDC
fault on a path without identifying its actual clock endpoints.

Questions requested of this independent review:
A. Give a cycle-by-cycle account of one 16-pixel CLEAR write from RECT_COLOR
   through slot capture, arbitration and return acceptance. Find any protocol,
   reset, payload/ownership, enable-polarity or synthesis corner case still
   consistent with the provided evidence. Challenge the testbench assumptions.
B. Rank at most 4 plausible remaining explanations; for each state what would
   falsify it. Distinguish why legacy success does or does not constrain it.
C. Propose the smallest discriminating observation feasible with the existing
   image or a tightly scoped, reviewable instrumented variant. Specify signals,
   triggering, clock domain, known-active witness, expected traces for each
   branch, and how measurement itself could change routing. Prefer data over
   blanket LOCAL_CLOCK changes, random seeds or reducing DDR frequency.
D. Can a targeted post-PnR test include the exact pixel/geometry/slot/arbiter
   cones, real reset semantics and backpressure with official primitives? State
   which boundary assumptions could still conceal this hardware failure.
E. Identify missing evidence; do not fabricate values of unobserved registers.
   A proposed patch must preserve the proven legacy path and Pro Dock reference.

Only project code, selected hardware measurements and technical identifiers are
included. No credentials, external hostnames, user serial numbers or private keys.
'''

projection(T/'handoff.json','Current handoff / historical-state distinction',keys=['status','hardware_state','timing','bitstream_sha256','qualification','pending','previous_runtime_state_before_user_powercycle'])
def cases(d):
    result={k:d[k] for k in ['bitstream_sha256','qualification','scope','common_byte_address','byte_count','measurements_complete','stopped_on']}
    result['cases']=[]
    for c in d['cases']:
        x=dict(name=c['name'],words_hex=['%08x'%w for w in c['words']],completed=c['completed'],gpu_before=c['gpu_before'],gpu_after=c['gpu_after'],error_deltas=c['error_deltas'],color=c['color'],depth=c['depth'])
        if 'capture' in c:x['capture']=c['capture']
        if 'snapshot' in c:x['snapshot']=c['snapshot']
        result['cases'].append(x)
    return result
projection(T/'r19_same_address_01/result.json','Hardware comparison at identical byte address',transform=cases)
projection(T/'r19_clear_observe_01/result.json','Earlier stable stalled-state snapshots',keys=['bitstream_sha256','scope','gpu_reset','gpu_command_sent','ddr_written','cpu_resumed','gpu_snapshots','scanout_snapshots','ddr_regions','gpu_final'])
def audit(d):return {k:d[k] for k in ['bitstream_sha256','qualification_status','timing','missing_parent_cells','changed_parent_cells','changed_parent_parameters','added_cells','observer_ff_count','sample_ff_count','shadow_ff_count','held_shadow_max_ns','held_shadow_bound_passed','required_primary','missing_primary','global_routes','limits']} | {'worst_reported_families':d['timing_summary']['worst_families']}
projection(T/'r19_postroute_01/result.json','Physical comparison R18r1 to R19 and timing',transform=audit)
projection(T/'r19_capture_paths_01.json','Independent capture-path bounds',keys=['passed','qualification','only_existing_output_change','all_other_application_cells_and_parameters_preserved','held_shadow_max_ns','sample_setup_lower_bound_ns','limits'])
projection(T/'handshake_truth_proof.json','Exhaustive mapped handshake equivalence')
excerpt(T/'check_handshake_truth.py','Proof method and compared equations',[(1,120)])
projection(T/'r20r1_memory_sim_01/result.json','Mapped CLEAR simulation scope',keys=['passed','netlist_sha256','scope','observation_rewired_inputs','application_primitives_added','logs'])
source(T/'r20r1_memory_sim_01/simulation.log','Full mapped CLEAR simulation log (not copied)')
excerpt(B/'source/tang/rtl/video/gpu_accel.v','Command FIFO/reset and actual extended request slot',[(1,83),(179,264)])
excerpt(B/'source/tang/rtl/video/gpu_geometry.v','Geometry passthrough and pixel ready gating',[(40,61),(240,270),(324,333)])
excerpt(B/'source/tang/rtl/video/gpu_v1.v','Pixel states, native valid contract, CLEAR validation and execution',[(21,43),(82,143),(244,291),(343,368),(422,433),(576,626)])
excerpt(B/'source/tang/rtl/board/ddr_gpu_arb.v','Actual complete DDR arbitration RTL',[(1,160)])
excerpt(B/'source/tang/rtl/board/ddr_subsys.v','Arbiter connection to vendor DDR IP',[(110,143)])
excerpt(B/'impl/pnr/console_neo.rpt.txt','R19 global routing report',[(114,140)])
excerpt(B/'source/tang/boards/neo/neo.sdc','Clock/CDC timing constraints',[(1,230)])

# Include exact post-PnR primitive pins and their LUT fan-in, bounded at FF Q.
vo=B/'impl/pnr/console_neo.vo';sid=source(vo,'Actual R19 post-PnR netlist (selected sequential primitives / LUT cones below)')
text=(ROOT/vo).read_text();cells={};driver={};params={}
for m in re.finditer(r'^(\w+)\s+(\\\S+|\w+)\s*\(([^;]*?)\);',text,re.M|re.S):
    kind,name,body=m.groups();name=name.removeprefix('\\')
    if kind=='module':continue
    pins=dict(re.findall(r'\.(\w+)\s*\(([^()]*)\)',body))
    norm=lambda s:s.replace('\\','').strip()
    pins={p:norm(v) for p,v in pins.items()};cells[name]=(kind,pins,m[0])
    q=pins.get('Q',pins.get('F'))
    if q:driver[q]=name
for m in re.finditer(r'^defparam\s+(\\\S+|\w+)\s*\.\w+\s*=\s*[^;]+;',text,re.M):params.setdefault(m[1].removeprefix('\\'),[]).append(m[0])
targets=['u_accel/u_v1/u_pixels/native_valid_s1','u_accel/v1_pending_s2','u_accel/v1_accepted_s0','u_accel/v1_tx_write_s0','u_soc/g_ddr.u_ddr/u_gpu_arb/take_blitter_s0']
selected=set(targets);frontier=[]
for n in targets:
    assert n in cells,n
    frontier += [cells[n][1][p] for p in ('D','CE','RESET') if p in cells[n][1]]
while frontier:
    net=frontier.pop();name=driver.get(net)
    if name in selected or name is None:continue
    kind,pins,_=cells[name]
    if not re.fullmatch(r'LUT[1-4]|INV',kind):continue
    selected.add(name);frontier += [v for p,v in pins.items() if p.startswith('I')]
assert len(selected)<100,len(selected)
add('Exact routed DFF/LUT primitives; upstream FF outputs are leaves',sid,'\n'.join(cells[n][2]+'\n'+'\n'.join(params.get(n,[])) for n in sorted(selected)))
source(B/'console_neo.vg','Authoritative R19 mapped netlist used by Boolean proof')
source(B/'sources.json','Frozen source inventory')
source(B/'experiment.json','R19 route experiment provenance')
source(B/'impl/pnr/console_neo.fs','Exact current/previously-tested R19 SRAM bitstream')
source(B/'impl/pnr/console_neo.tr','Full timing report (FAIL, not copied)')
source(B/'impl/pnr/console_neo.sdf','Full routed delays (not copied)')

index='\nSOURCE INDEX — SHA256 OF THE FULL ORIGINAL FILE\n'+''.join('[{id}] {path}\n  SHA256 {sha256}\n  {label}\n'.format(**s) for s in sources)
packet=header+index+''.join(sections)
# Parent reviewed the 105 KB scope and authorized this expanded packet;
# its external-review wrapper has a 200 KB bound.
assert len(packet.encode())<=200*1024,len(packet.encode())
for forbidden in ('BEGIN PRIVATE KEY','Bearer ','sk-ant-','sk-proj-','[sudo]','michael@'):
    assert forbidden not in packet,forbidden
out=HERE/'neo_packet.txt'
assert not out.exists()
out.write_text(packet)
manifest=dict(packet=str(out.relative_to(ROOT)),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),source_count=len(sources),sources=sources,extraction_script_sha256=digest(Path(__file__).relative_to(ROOT)),hardware_access=False,external_calls=False,scope='Independent diagnostic review packet, not a new test or qualification')
(HERE/'neo_packet_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:v for k,v in manifest.items() if k!='sources'},indent=2))
