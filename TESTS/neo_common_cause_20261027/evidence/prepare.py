#!/usr/bin/env python3
"""Read only local evidence; emit a neutral, self-contained review packet."""
from pathlib import Path
import json,hashlib,difflib
ROOT=Path('/home/michael/console')
OUT=ROOT/'TESTS/neo_common_cause_20261027/evidence'
BASE=ROOT/'TESTS/neo_720p_20261012'
CAP=BASE/'capture_memory_20261027'; RESET=CAP/'reset_contract_01'
P=ROOT/'tang/impl/gpu_geometry_g22r0'
R19=ROOT/'tang/impl/console_neo_n56r19_capture_ce_local'
R21=ROOT/'tang/impl/console_neo_n56r21r1_capture_memory'
N=ROOT/'tang/impl/console_neo_n56r21r2_resetqual_coupled'
inputs={}; chunks=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def label(p):
 try:return str(p.relative_to(ROOT))
 except ValueError:return str(p)
def track(p):
 p=Path(p);inputs[label(p)]={'sha256':sha(p),'bytes':p.stat().st_size};return p

def section(title,content):chunks.append('\n## '+title+'\n\n'+content.rstrip()+'\n')
def excerpt(p,a=1,b=None,title=None):
 p=track(p);lines=p.read_text(errors='replace').splitlines();b=len(lines) if b is None else min(b,len(lines))
 section(title or label(p)+f':{a}-{b}', 'SOURCE SHA256 '+sha(p)+'\n'+'\n'.join(f'{i}: {lines[i-1]}' for i in range(a,b+1)))
def selected_json(p,keys=None,title=None):
 p=track(p);d=json.loads(p.read_text())
 if keys is not None:d={k:d[k] for k in keys} # never silently fabricate null keys
 section(title or label(p), 'SOURCE SHA256 '+sha(p)+'\n'+json.dumps(d,indent=2,ensure_ascii=False))
def log_matches(p,terms,limit=70):
 p=track(p);rows=[f'{i}: {s}' for i,s in enumerate(p.read_text(errors='replace').splitlines(),1) if any(t in s for t in terms)]
 assert len(rows)<=limit,(p,len(rows))
 section(label(p)+' selected exact log lines','SOURCE SHA256 '+sha(p)+'\n'+'\n'.join(rows))

section('Task and evidence discipline', '''Independent adversarial review requested by the user: find a falsifiable common explanation for the Neo console failures versus a working Pro Dock. Consider one shared integration/constraint/startup problem AND the possibility of multiple unrelated faults. Do not assume a common cause exists. No hardware access, source edits, new synthesis or PnR is requested from reviewers.

Deliver: (1) verified facts versus hypotheses; (2) a small causal graph stating which observations each hypothesis explains and cannot explain; (3) at most three high-value discriminating tests using existing bitstreams/observables or exact-source simulation before suggesting new PnR; (4) identify any precise violated contract/constraint with source lines and actual mapped endpoint. Do not propose an arbitrary timing exception, a blind B/C retarget, or an unexplained LOCAL_CLOCK patch.

LW is a supported routing resource, not itself a diagnosis. An A/B result after rerouting changes the entire physical implementation; report the intervention and result without assigning causality to a named resource absent an established violated requirement. RTL simulation, synthesis/mapping identity, STA coverage, hardware behavior and visual feedback are distinct evidence categories. Missing exported SDF arcs are not proof that the internal Gowin STA library lacks them. Do not infer die revision from the package or tool B/C string alone. Do not treat a stale/zero snapshot as a fresh live measurement.

This packet contains source excerpts, exact archived measurements and separately labelled interpretations. Earlier model opinions are deliberately excluded. Files remain untouched; this preparation performs reads and writes only this evidence folder. The Pro Dock reference remains protected. All new Neo versions remain candidates and global timing FAILs remain FAILs.''')
section('Build and physical comparison', '''| Item | Pro Dock reference | Neo current diagnostic family | What is established / limitation |
|---|---|---|---|
| Exact target | GW5AST-138B / GW5AST-LV138FPG676AC1/I0 | GW5AST-138C / GW5AST-LV138PG484AC1/I0 | Actual build Tcl below. 676 versus484 package pins; B/C not interpreted as die revision here. |
| Proven working software/hardware baseline | G22r0 + original Linux/NEBULA R17 restored/tested Oct21 | Analyzer L31r8 reportedly works on this same Neo; exact frozen Tcl also targets C/PG484 | L31 target independently hash-checked against its original manifest below. No new analyzer hardware experiment in this audit. |
| Video | LCD800x480, pixel35MHz | HDMI1280x720, pixel74.375MHz, serial371.875MHz | 2.4x active pixels; current failing internal pattern uses no framebuffer DDR traffic. |
| CPU and DDR clocks declared | CORE800, AHB/APB80, RTC10, DDR300/UI75MHz | same nominal frequencies | Hard CPU macro/library exports differ between Pro and Neo, confounded by target and generation/library version. |
| DDR controller source | DDR3 5.9 lineage /300MHz | same byte-identical standalone controller and original arbiter/adapter | Physical board and pins differ; reference number equality does not establish physical timing equality. |
| CPU FIFO | inferred dual-clock FIFO RTL | isolated 100/64-bit depth4 storage replaced with explicit FFs, same pointer/reset protocol | Not identical total implementation; real Neo source diff included. Larger USB/trace FIFOs remain inferred. |
| GPU | functional geometry/pixel/compositor under G22r0 | evolved diagnostic sources, queue and observations, masks/selectors/netlist patches | Do not claim the complete GPU RTL/netlist is identical; comparison hashes below. |
| USB device | C28 generated Controller3.3 + SoftPHY3.5/V_120, Gowin1.9.12.03, Oct2026 | active older Sipeed1.9.10.03 generated Nov2024 modules, old template targetB | New targetC USB IP was generated separately but is NOT in R19/R21/R21r2. Exact active provenance linked below. |
| USB topology | 50->48->60/960->120MHz | same real primitive ratios and nominal domains | Old PHY lacking V_120 macro does NOT establish wrong 120MHz SDC. See mapped clock audit. |
| Port inputs | SOFT-USB device and board LCD | SOFT-USB device +2low-speed HIDhosts, BL616 UART/JTAG, HDMI | Hostgamepads are separate from failing HSdevice path. |

Pro Dock Oct21 hardware campaign: FPGA/USB HS480Mbps/CPU800MHz/Linux6.12.112 boot;384000pixel oracle and2430commands; threeNEBULAreference poses;10000frames in226.056s (44.24FPS),213740commands, up to39sprites/8layers, noGPUerrors/underflows/rejects. SDfour sectors reread identically (first detection timeout then retry retained). This validates those exact binaries at that time. Later game/kernel work must not be silently called original R17.
Pro Dock reference is not a fully timing-closed control: setup−0.564ns/9violations; historical occasional USB CDC duplicated characters remain documented. A working game does not prove all CDC/reset/physical contracts.

DDR part note: user identified H5TQ4G63EFR-RDC on Neo. Stored schematic versions include both Micron and Hynix Neo variants; Pro schematic4072 also uses HynixEFR. This is not an independently photographed package identification or board SI measurement.''')
for p in [P/'build.tcl',R19/'build.tcl',N/'build.tcl']:excerpt(p)
L31=Path('/home/michael/logic_analyser_wifi/tang/impl/linux_l31r8_local_20261012')
l31t=track(L31/'workspace/tang/build_la16_usb.tcl');l31m=track(L31/'manifest.json');expected=json.loads(l31m.read_text())['files']['tang/build_la16_usb.tcl'];assert sha(l31t)==expected
section('L31r8 exact known-reference target binding',json.dumps({'build':str(L31),'manifest_sha256':sha(l31m),'frozen_tcl_sha256':sha(l31t),'manifest_expected':expected,'equal':True},indent=2))
excerpt(l31t,1,14)
section('Primary documentation conflict, not a target diagnosis', '''Accessed2026-10-27: https://wiki.sipeed.com/hardware/en/tang/tang-console/mega-console.html (short alias https://wiki.sipeed.com/tangconsole).
Its precautions list the138K FPG676 part but simultaneously recommend PBG484A and versionB; its no-response FAQ instead names the PG484 part. This is internally inconsistent. The illustration URL is https://wiki.sipeed.com/hardware/zh/tang/tang-mega-138k/assets/partno_138K.png ; it was not independently pixel-inspected in this packet. The linked official138K examples are https://github.com/sipeed/TangMega-138K-example.
The working L31r8 frozen Tcl uses C/PG484 and its hash matches its build manifest. Thus the ambiguous wiki text does not establish that current Neo targetC is wrong. Parent is independently checking the newer Sipeed B->C guidance and physical device identification; it should be appended as a separately sourced addendum, not silently inferred here.''')

section('Chronology: measured behavior and confounding', '''1. N55/N56: CPU/ILM/DDR pretests and legacy32byte fill pass; V1TARGET rejected and headers observed zero. N56r1 changes three control-placement constraints and reroutes same logic; A/B/A/B reload comparison reproduces N56failure and N56r1success. R1passes13configuration expectations,80configuration sequence and5pixel oracles, but mesh later rejects material restoration. This is physical implementation dependence, not proof LW hardware is defective. N56r1 still setupFAIL−0.440ns.
2. Minimal HDMI with no CPU/DDR: DCEautoPG0 visible -> same netlist constrainedSG0 no signal -> sameautoPG0 visible. ExplicitPG0 and laterSG4 visible. FullR8SG4 retains visible internal pattern while framebufferfetch remains blocked. Therefore HDMI signal and DDRfetch are separable failures; no general SG-resource erratum established.
3. FullR1Linux boot confirmed via kernel logs and after cold power viaUART, GPU720p/SD/twoHIDs initialized. Serial input corruption/XOFF occurred. A CPU-parked RGB565framebuffer test with1.84MB contents verified still had roughly720underflows/frame, zero completedfetches. No Linux/game is required to reproduce that reader problem.
4. R19: CPUparked, internalHDMIpattern/checksum correct. TARGET/legacy/emptyclear accepted. CLEAR16color or depth can stall. During depth-only stall,3uncachedCPUwrites32B plus guards reread exactly; noGPUbuffer change. This does not establish GPUrequestneverasserted or DDRuniversallygood. COPY16 is rejected with done advancing, descriptor header opcode29 correct, source/destination/Z unchanged; its identical packet passes RTL/mapped simulation.
5. R19->R21r1: only observer helper/content changes + observation fanout, with all original application primitive connectivity/INIT conserved by audit. Same CST/SDC/PnR options, new physical implementation. R21r1globalSTAFAIL−2.602ns. Two loads give properJTAGTAPID but DMI timeout and blackcamera; same100kHzTCK R19before/after responds and showspattern. Thus not a demonstration that a timing-clean equivalent design failed.
6. Exact-source reset simulation (R19/R21 chain, real50ms wait,50/80MHz): loss ofLOCK between50MHz edges is captured by AHBasyncreset while qualifier remains stale, leading to PORrelease49.5ns afterLOCKreturns; another pulse phase yields12.5nsPORpulse whiledelay_done0. Both logical defects are reproduced, but physical occurrence on card is not established.1nsstimuli demonstrate logic, not guaranteed silicon pulse capture.
7. R21r2coupled: isolated resetqualifier repair (async invalidation,2FFrelease,50ms wait; couple PLLready with observed AHBreset; clear both finalCPUresetpipeline stages). Exact-source, mapped-primitives and binary postroute helper-equivalence tests pass; globalSTAFAIL remains−4.813ns setup and−2.680ns recovery. SameDDR/USB/video application logic asR21r1; two new gates and twoCLEARconnections outsidehelper, plus new PnR.
8. R21r2hardware now consistently responds overDMI: CPUexamined/parked0x80000004, ROM/GPU/geometry IDs exact. Fresh4reads over1.633s showframes0/checksum0 withmode0 andallframebuffer/layers/sprites disabled. R19pairedcontrol shows377588->377686frames and1ff8f800checksum. R21r2 restoredR19aftereachdiagnostic; finalmire andguardPASS. Current experiment does not distinguish pixelclock/reset fromcounterCDC. The latestcandidatephoto is obstructed/blurred and is NOT evidence ofa new blackscreen.
9. Both versions' AHBUSBtraceID55544e41/status0/sequence0 have been read. No fresh USB-domain snapshot was requested duringthatreadonlytrial; zeros do not prove USBclockstopped. NoHSenumeration currently seen onNeo. R1earlierarmedtrace showed~12.87Mticks/200ms and~2.57M RXERRORcycles, noSOF/reset/token; that is anotherbuild and must not be promoted to currentmeasurement.

Timing and positive source/mapped tests do not override these distinct physical outcomes. New PnR is a confound in all larger candidate changes. Source-level resets differ between Pro/L31/R19/R21r2; the common-underlying-architecture claim needs testing rather than assuming portability of integration.''')
# Measurements: avoid identity/host/private metadata; no nonexistent schema keys projected to null.
selected_json(RESET/'video_readonly_20261027_155600/result.json', ['qualification_status','candidate_sha256','last_programmed_sha256','left_startup_verified','observations_completed','UART_commands','DDR_written','GPU_commands','SD_written','flash_written','Linux_loaded','CPU_resume_command','CPU_ROM_restart_possible','dynamic_observer_used','baseline_verified','program_coupled_status','restore_attempted','restore_r19_status','left_state'])
vd=track(RESET/'video_observation_01.json');v=json.loads(vd.read_text())
rows={}
for name,d in v['observations'].items():
 rows[name]={'elapsed_ms':d['elapsed_start_to_start_ms'],'frame_delta':d['frame_delta'],'samples':[{'sample':s['sample'],'time_ms':s['time_ms'],'scan_mode':s['VIDEO_SCAN'][1],'frames':s['VIDEO_SCAN'][6],'display_checksum':hex(s['VIDEO_SCAN'][24]),'usb_trace':s['USB_TRACE_STATUS'],'gpu_debug_status':s['VIDEO_GPU_DEBUG'][1],'gpu_debug_meta':s['VIDEO_GPU_DEBUG'][16],'scan_debug_status':s['VIDEO_SCAN_DEBUG'][1],'scan_debug_meta':s['VIDEO_SCAN_DEBUG'][16]} for s in d['samples']]}
section('Fresh paired video/USB MMIO projection (actual schema)', 'SOURCE '+label(vd)+' SHA256 '+sha(vd)+'\n'+json.dumps(rows,indent=2))
for logfile in ['r19_video_readonly.log','video_readonly.log','restored_guard.log']:
 p=RESET/'video_readonly_20261027_155600'/logfile
 if p.exists():log_matches(p,['PARKED','ROM','IDCODE','examined','CHECKSUM','STARTUP','NEO_REVIEW','GUARD','HART'],35)
for p in [BASE/'local_capture_20261026/r19_depth_cpu_20261026_234857/result.json', BASE/'local_capture_20261026/r19_copy_20261027_000303/result.json',CAP/'startup_100k_20261027_090320/result.json',ROOT/'TESTS/prodock_restore_20261021/README.md']:
 track(p)
section('Measurement provenance references', '\n'.join(f'{label(p)} SHA256 {sha(p)}' for p in [BASE/'local_capture_20261026/r19_depth_cpu_20261026_234857/result.json',BASE/'local_capture_20261026/r19_copy_20261027_000303/result.json',CAP/'startup_100k_20261027_090320/result.json',ROOT/'TESTS/prodock_restore_20261021/README.md']))

rels=['tang/rtl/board/ddr3_standalone_32b/ddr3_standalone.v','tang/rtl/board/ddr_gpu_arb.v','tang/rtl/board/ddr_arb.v','tang/rtl/board/ahb_ddr_cdc.v','tang/rtl/board/ddr_ui_adapt.v','tang/rtl/board/ddr_dcfifo.v','tang/rtl/board/gowin_pll_ddr3/gowin_pll_ddr3.v','tang/rtl/board/ae350_soc.v','tang/rtl/video/gpu_accel.v','tang/rtl/video/gpu_geometry.v','tang/rtl/video/gpu_scanout.v']
# Resolve unique basenames if some board paths differ; record exact resolved paths, never guess equality.
comparisons=[]
for rel in rels:
 pair=[]
 for build in [P,N]:
  f=build/'source'/rel
  if not f.exists():
   found=list((build/'source').rglob(Path(rel).name));assert len(found)==1,(rel,found);f=found[0]
  track(f);pair.append(f)
 comparisons.append({'name':Path(rel).name,'prodock':label(pair[0]),'prodock_sha256':sha(pair[0]),'neo':label(pair[1]),'neo_sha256':sha(pair[1]),'byte_identical':pair[0].read_bytes()==pair[1].read_bytes()})
(OUT/'source_comparison.json').write_text(json.dumps(comparisons,indent=2)+'\n')
section('Actual snapshot source comparison (not universal netlist equivalence)',json.dumps(comparisons,indent=2))
for rel,title in [('tang/rtl/board/ddr_dcfifo.v','Isolated Neo CPU FIFO storage delta'),('tang/rtl/board/ae350_soc.v','SoC wrapper delta from ProDock to currentNeo')]:
 a=P/'source'/rel;b=N/'source'/rel
 section(title, ''.join(difflib.unified_diff(a.read_text().splitlines(True),b.read_text().splitlines(True),fromfile=label(a),tofile=label(b),n=3)))
# Top+reset snippets, only exact sources used by active snapshots.
excerpt(P/'source/tang/rtl/console_top.v',491,542)
excerpt(R19/'source/tang/boards/neo/console_neo.v',122,192)
excerpt(N/'source/tang/boards/neo/console_neo.v',1,34)
excerpt(N/'source/tang/boards/neo/console_neo.v',71,118)
excerpt(N/'source/tang/boards/neo/console_neo.v',122,192)
excerpt(R19/'source/tang/boards/neo/neo_reset_trial.v',60,130)
excerpt(N/'source/tang/boards/neo/neo_reset_trial.v',60,125)
excerpt(N/'source/tang/rtl/board/ae350_soc.v',130,196)
excerpt(N/'source/tang/rtl/board/ae350_soc.v',365,383)
excerpt(N/'source/tang/rtl/video/gpu_scanout.v',23,43)
excerpt(N/'source/tang/rtl/video/gpu_scanout.v',120,148)
excerpt(N/'source/tang/rtl/video/gpu_scanout.v',238,277)
excerpt(N/'source/tang/rtl/video/gpu_scanout.v',514,550)
# Exact active constraints. Pro diagnostic SDC really used by build Tcl.
excerpt(N/'source/tang/boards/neo/neo.sdc')
excerpt(P/'source/diagnostics/timing_reports.sdc')
selected_json(RESET/'candidate_02/postroute_01/global.json',['qualification_status','global_timing','timing_checks_ns','clocks','constraints','synthesis_audits'])
section('Postroute/constraints conclusions and limits', '''CurrentNeo has all12 expected nominalSTA clocks and8requiredPRIMARYroutes recognized, sourceCST/SDC unchanged fromR21r1. Those are mapping/coverage checks, not proof every path meets timing or siliconclocks run. core_clk has noFmaxpath summary but hardCPU SDF contains730SETUPHOLD; claiming noCPU timinganalysis fromtheFmaxmessage is incorrect.
SDC defines CORE/AHB/RTC at PLLpins with base create_clock rather than generated relationships; core/RTC are grouped asynchronous. MUG1031 says CORE/DDR/AHB asynchronous and AHB/APB synchronous1:1. NoTCK create_clock/input-output timing is present; exact JTAGTMS/TDI arcs exist inhardCPU SDF. UART/gamepad first-stage exceptions were checked againstactualroutedFFs: suffix_s1 isnot synchronizerstage; regex targets first stages, not second.
Betweenbus80,clk50,ddrUI,pixel domains, bidirectional max_delay8ns exists with holdfalsepaths; USB60/120/960 are groupedasync as in oldvendorSDC. Clockgroups outrank falsepath, which outranks maxdelay perSUG940. Newmaxdelay wouldnot automaticallyoverridegroups. Gray wire bounds alone do not prove resetcoherence, fullmaxskew, metastability orcorrecthandshake.
AE350 exportedSDF forR19/R21 has730SETUPHOLD butnoPOR/HWresetwidth/recovery/removal arcs. Thisis missing exported evidence, not proofrequirementsabsentfrominternalGowinlibrary. G22AE350export differs in1270timingarcs fromNeo, confounded targetandtool/library; R19/R21macroblocks identical.
CurrentNeo−2.680nsrecovery goes from clk50 PLL_INIT/state1Q throughlogicmaskingPLLLOCK (notthroughPLLprimitive), qualifiedavailability/release andSoCCLEAR to BOTH init_sync stages. ParentR21r1CLEAR cameonlyfrombus80ae350_rst_sync andrecovery+8.851ns. Realnewasyncresetboundaryisdocumented. Legalstartup delay_done0 keepsreleaseofffor50ms; exhaustive512binarycombosprove sensitizationmask, withoutdeletingSTAviolations. delay_done->CLEAR bound+1.735underinherited8nsconstraintisnotproofasynchronousphase. FirstchainPRESETexcluded;analogLOCKpulsecaptureandhardCPUresetrequirementsnotestablished.
R21r2dynamicobserver setupbound−1.938ns: doNOTuseD/Q/CE/stickymemorycapturesasproofonthisroute. StableMMIO/heldACKbanks needindividualprotocolandcoveragechecks, not blankettrust.
Mostsetupviolations countedunderddr3_sys_clk areGPUlogic endpoints, notproofDDRcalibrationfailed. DDRprofileauditFAIL is inheritedae350_socdifference versusG22; detailedR21r1->R21r2audit proves20DDRfiles/13268DDRcells/13358paramsidentical. Still notphysicalDDRqualification.''')
for p in [RESET/'candidate_02/POSTROUTE_REVIEW.md',RESET/'candidate_02/postroute_ddr_identity_01/result.json',RESET/'candidate_02/postroute_release_paths_02/result.json',CAP/'root_constraints_01/ae350_sdf_audit.json',CAP/'root_constraints_01/sync_cells.json']:
 track(p)
# Vendor documents summarized, avoiding extensive copyrighted excerpts.
for p in [RESET/'UG306_109E.txt',CAP/'vendor_docs/MUG1031-1.3.1E.txt']:
 track(p)
section('Documented reset/clock contract versus examples', '''UG306-1.0.9E (2026-08-12), pp39–40/table5-2; archived UG306_109E.txt:2040–2062: sourceinstabilityrequires appropriate PLLreset; LOCKmayglitchduringlocking and shouldbe observedcontinuously foratleast2ms. That isdifferentfrom a measured minimumasynchronousCLEARpulsewidth. Noanalogguarantee for1nsLOCKloss hasbeen established.
MUG1031-1.3.1E (2026-01-23), table4-1p11, archivedtxt:713–735: core<=800MHz, AHB/APB/DDR<=200MHz, RTC32.768kHz, CORE/DDR/AHBasync, AHB/APBsync1:1. §8.4.1p46 (txt:1831–1833) requires dedicated PLL_R0 CLKOUT1 corepath. ExistingthreeprojectsuseRTC10MHz likeSipeedAE350example; nointernalprescalerproofhere. Thedocument/example divergence alone doesnotexplainNeo-onlyfailure.
Thehistorical20mswait comesfromSipeedexample DDRreadydebounce at50MHz/1000000counts, NOT a foundnormativehardCPUresetminimum. POR/HW aretiedtogether there. Neo50ms marginwasanexplicituserchoice. FirstgenerationLOCKqualification andfinalCPUresetpipeline areseparatecontracts.
DS1239table3-13 tSR_CFU isSR->Qdelay, not minimumCLEARpulsewidth. Table3-18 RSTMIN-PULSE10ns concernsPLLreset, notarbitraryfabricFFreset. NoerratumforLW or asynchronousFIFOonthischiphasbeenestablishedbythesedocuments.''')
ref=Path('/home/michael/gowin/ref/TangMega-138KPro-example/ae350_customized_demo/src/ae350_customized_demo.v')
excerpt(ref,60,73);excerpt(ref,100,118);excerpt(ref,207,220)
selected_json(RESET/'l31_provenance.json')
# Active USB provenance compact and actual mapped clocks evidence.
u=track(RESET/'candidate_02/usb_actual_comparison_01/active_provenance.json');ud=json.loads(u.read_text())
section('USB actual active provenance, compact projection', 'SOURCE '+label(u)+' SHA256 '+sha(u)+'\n'+json.dumps({'status':ud['status'],'source_files_compared':len(ud['sources']),'byte_identical_to_prodock':sum(s['same_prodock'] for s in ud['sources']),'different_sources':[s for s in ud['sources'] if not s['same_prodock']],'synthesis_origin':ud['actual_synthesis']['path'],'origin_tcl_sha256':ud['actual_synthesis']['build_tcl_sha256'],'origin_vg_sha256':ud['actual_synthesis']['netlist_sha256'],'current_vg_sha256':ud['actual_synthesis']['current_netlist_sha256'],'all27_usb_modules_same':all(x['same_actual_synthesis'] for x in ud['actual_synthesis']['usb_modules'].values()),'source_ip_versions_neo':ud['source_ip_versions_neo'],'prodock_c28_binding':ud['prodock_c28_binding'],'usb_reset_segment_byte_identical':ud['usb_reset_segment_byte_identical'],'limits':ud['limits']},indent=2))
track(RESET/'candidate_02/usb_clock_constraints_01/clock_audit.json')
section('USB clock and test facts', '''Exactroutedprimitives onboth: PLL_F50x24/25=48MHz; PLL_B48x20 produces960MHz CLKOUT0 and60MHz CLKOUT1; DHCE/CLKDIV DIV_MODE8 produces120MHzsclk. ActualoldvendorSDCalreadydeclares8.333ns sclk andgroups60/120/960async. No clockratio/namedendpointcontradictionfound. 44GrayQ->Dinterconnects exportedallpresent; maximumwireNeo0.839ns,Pro1.043ns, notfullC2Q/setup/skew/MTBFproof. OldRXFIFO8bit/newC28fifo_rx_pkt16bitisreallogicdifference.
NeoactiveSOFT-USBpads J19/H19TX,H17/H18RXDP,H20/G20RXDN,M17pullup,J16/AB16terminationmatch32001Cschematic audit; Proelectricalattributesmatch. Thisislogicalmapping, notSI/levelmeasurement. USBPLL/resetsegment isbyte-identical toProDock, unlikeactualcontroller/PHYversion.
CtargetUSB3.3/PHY3.5V_120 alreadygeneratedisolatedunder n56r3_validation_20261021/usb_ip_candidate butNEVERenteredR19/R21/R21r2. Correctfuturealignmentwould regenerateofficialsourceswithProC28macrosandexplicitNeoC/PG484target; donotcopyBbinary orblindlyresynthesizepatchednetlists (post-synthesisdiagnostic/resetpatcheswouldbelost).
ExistingUTNA commandprotocol (notexecutedinlatestreadonlytrial): command1 clear/arm;waitfreshseq+1,busy0/reject0;after200ms command6snapshot/disarm;readstable32wordbanktwice;after100ms command2 expectsarmed0 andticks=previous+1 dueNBA;another2 after100ms expectsunchangedticks.3actualsourceIcarusclockphase testsPASS andwrongticks negativecontrolfails. NoUSBdatapathresetorMSC/SD/GPUcontrol. Howeverthiswouldbe a NEW observercommandexperiment, notreadonlyMMIO.
Bank word3ticks,word13RXERRORcycles,word15busresetcount,word16SOF,word17TXstall,word31armedbit10. NoPLLLOCK/diag_board inthisCPUbank; thoseareonlyinEP0diagnostictransfer, unavailablewhenUSBdoesnotenumerate. Tickspositiveestablishsome60MHzdomainactivity/handshake, notallPLLs orphysicalHSvalidity. A stalezero bankprovesnothingaboutdomainactivity.''')
# Include exact usb reset source and pixel/CDC relevant primitives.
soft=N/'source/tang/boards/neo/soft_usb.vh'
if soft.exists():excerpt(soft,1,60)
cdc=list((N/'source').rglob('cdc_word.v'))
if len(cdc)==1:excerpt(cdc[0])
# attach reset simulation provenance and limited narrative, no historic mixed logs.
for p in [RESET/'simulation_01/README.md',RESET/'candidate_02/mapped_01/result.json',ROOT/'TESTS/dual_board/20261027_r21r2_reset_qualification/result.json']:
 if p.exists():track(p)
section('Discriminating experiments, separated by hypothesis family', '''These are proposals, not performed observations or authorization to use hardware.
A. Commonreferenceclock/startup/resetchain: existingR19vsR21r2, freshUTNA snapshotprotocol whileCPUparked, pairedwithfreshvideoMMIO. IfUSBticks/ACKrespondandpixelcounters0, a totalsharedreferenceclockfailureisnotnecessary; remainingpixelreset/clock/CDCandUSBanalogstillambiguous. IfbothfreshdomainsfailbutAHBworks, testtheirsharedreset/destinationclocks. No directPLL_LOCKavailablehere; do notinventone. Exact-source clockstop/resetphase testscanproducepredictions beforehardware.
B. Pixelreset versus countertransport: source frames/displaychecksum travel viaindependent cdc_word modules; frame0andchecksum0 do not distinguish prstlow, pixelclockdead orreadbackCDC. ExistingHDMIpatterncamera independentofMMIO andstablebank/protocolfeedbackcan narrowthis. Read onlynominalclockSTA cannotverifyclocktoggles. A newinstrument shouldonlyfollowifnoneexistingobservablesdiscriminate, andmustitselfmeetconstraints.
C. DDRbandwidth/arbitration: internalpatternmode0 needsnoDDRtraffic, so R21r2frames0 cannotrequirebandwidthsaturation. ForR19GPU-specificfault, smallvalidemptyconfig/targetthenCOPY16 versusCLEAR16 andguardeduncachedCPUreads distinguishconfigurationrejectfromfirstnativehandshake; STOPfirstfailure. CPUpassdoesnotproveGPUrequest/ACKpath. Reuseexistingoracles; dynamicNCPonR21r2isnotqualified.
D. Target/library/integration: firstbindactualL31r8Ctarget andAE350generationproject/runtimeports andPLL/corepath toknownreference. CompareofficialGowindeviceDB/documentedB/Csupport andexactIPgenerationtarget; preservecontradictorySipeeddocumentasuncertain. BlindchangingCtoBwouldchangetoolmodelandlayoutandlosetheminimaltest. ProvsNeoSDFdifference alonecannotidentifydiecause.
E. IPversion/USB-specific: currentmappedclockratiosconsistent; obtainfreshtraceactivityfirst. LaterisolatedofficialCIPalignment couldtestoldIPcompatibility butrequiresa newcandidate andfullaudit; cannotbyitselfexplainGPUconfigurationorCPUbootfailureswithouta sharedresource/resetcouplingpath. HSSOF/RXERROR statisticsalonecannotlocalizePHY/clock/cable.
F. Constraints/logicalCDC: list actualfailedarcsandmaskedpaths forcommonresetdomains, then exact-source4stateassertionswithlegalclockpauses/phaseoffsets/LOCKloss. A violationmustbe quantitativeandassociatedwith anexecutedpath. KeepallSTAFAILs. Do notuseLOCAL_CLOCKasexplanationorfalsepathsasrepair. Numeric8nswirebounddoesnotprovecoherentmulti-bittransaction.
G. Physical/configuration/I/O: sameNeo analyzer andminimalHDMIdesignswork; R19A/B/Abehaviorwithsameprogrammer/100kTCKcontrolsloadandcablepartially. Actualreferenceclock/rails/PLLLOCKmeasurementwoulddiscriminatebutnotpresent; officialdocumentedconfigurationstatus/CRC onlyifknownsafe. No guessedboundaryscanopcodeor unsupportedreadback. SameDDRpartdoesnotprovesameboardrouting.

Question for each reviewer: Does any precisely supported shared mechanism explain GPUcapture/rejection, readerstall, intermittenthardCPUstartup AND pixelcounters0 while respectingworkinganalyzer/R19controls? Ifnot, sayso andprovide the smallest observation thatwouldchange yourranking. Citefactsagainstyourpreferredhypothesis. Do notpromote speculative analog/reset/tool explanations to conclusions.''')
packet='NEO / PRO DOCK COMMON-CAUSE REVIEW — FACT PACKET\nCreated 2026-10-27; independent first-round material; no prior model answers.\n'+''.join(chunks)
assert len(packet.encode())<=200000,len(packet.encode())
(OUT/'packet.txt').write_text(packet)
manifest={'schema':1,'purpose':'neutral common-cause review packet','hardware_access':False,'source_mutation':False,'new_compilation':False,'source_files':inputs,'outputs':{n:{'sha256':sha(OUT/n),'bytes':(OUT/n).stat().st_size} for n in ['packet.txt','source_comparison.json']},'generator_sha256':sha(Path(__file__)),'limits':['External webpage inconsistency summarized, screenshot not yet independently inspected.','Original evidence files kept unchanged; excerpts line-numbered and JSON projections require actual keys.','No hardware cause has been established by packet assembly.']}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'packet_bytes':len(packet.encode()),'packet_sha256':sha(OUT/'packet.txt'),'manifest_sha256':sha(OUT/'manifest.json'),'sources':len(inputs)},indent=2))
