#!/usr/bin/env python3
"""Explicit-netlist global audit for this isolated ECO. Read-only build access."""
from pathlib import Path
import argparse,hashlib,json,re,sys
ROOT=Path('/home/michael/console');HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from check_geometry_timing import inspect
from neo.timing import timing_checks
from neo.timing_closure import global_clock_routes,audit as audit_closure
from check_gpu_copy_synthesis import audit as audit_copy
from check_gpu_scanout_synthesis import audit as audit_scanout
from check_neo_fifo_synthesis import audit as audit_fifo
from check_ddr_profile import audit as audit_ddr
from neo.gpu_replication import audit as audit_owner
from neo.gpu_reset import audit_reset_tree
from neo.pixel_mask import audit as audit_mask
from neo.pixel_selector import audit as audit_selector
BUILD=ROOT/'tang/impl/console_neo_n56r21r2_resetqual_coupled'
PARENT=ROOT/'tang/impl/console_neo_n56r21r1_capture_memory'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();assert not args.out.exists()
    rr=json.loads((BUILD/'route_result.json').read_text());assert rr['returncode']==0 and rr['status']=='ROUTED_NOT_QUALIFIED'
    log=(BUILD/'build.log').read_text();assert 'Bitstream generation completed' in log and not re.search(r'^ERROR',log,re.M)
    pnr=BUILD/'impl/pnr';vg=BUILD/'console_neo.vg';vo=pnr/'console_neo.vo'
    files=[Path(__file__),BUILD/'assembly.json',BUILD/'route_result.json',BUILD/'build.log',BUILD/'build.tcl',BUILD/'sources.json',vg,vo,pnr/'console_neo.tr',pnr/'console_neo.sdf',pnr/'console_neo.rpt.txt',pnr/'console_neo.fs',pnr/'cmd.do',BUILD/'source/tang/boards/neo/neo.cst',BUILD/'source/tang/boards/neo/neo.sdc']
    inputs={str(p):sha(p) for p in files}
    assembly=json.loads((BUILD/'assembly.json').read_text())
    for name,digest in assembly['inputs'].items():assert sha(BUILD/name)==digest,name
    tr=(pnr/'console_neo.tr').read_text();rpt=(pnr/'console_neo.rpt.txt').read_text();sdc=(BUILD/'source/tang/boards/neo/neo.sdc').read_text()
    summary=inspect(BUILD,'console_neo');timing=timing_checks(tr)
    manifest=json.loads((BUILD/'sources.json').read_text())
    source_checks={name:sha(BUILD/'source'/name)==digest for name,digest in manifest.items()}
    actual_files={str(p.relative_to(BUILD/'source')) for p in (BUILD/'source').rglob('*') if p.is_file()}
    mirror_checks={}
    for mirror,source in [('font8x16.hex','tang/rtl/video/font8x16.hex'),('rtl/video/font8x16.hex','tang/rtl/video/font8x16.hex'),('rtl/usbhost/usb_hid_host_rom.hex','tang/boards/neo/usbhost/usb_hid_host_rom.hex')]:
        mirror_checks[mirror]=dict(passed=sha(BUILD/mirror)==sha(BUILD/'source'/source),sha256=sha(BUILD/mirror))
    constraints=re.findall(r'^\s*TC_\S+\s+(\S+)\s+(.+?)\s*$',tr,re.M)
    norm=lambda s:' '.join(s.split())
    expected={norm(s) for s in sdc.splitlines() if s.startswith(('create_','set_','report_timing '))}
    constraint_result=dict(passed=bool(constraints) and all(state=='Actived' for state,_ in constraints) and expected=={norm(c) for _,c in constraints},active=len([s for s,c in constraints if s=='Actived']),missing=sorted(expected-{norm(c) for s,c in constraints}),inactive=[c for s,c in constraints if s!='Actived'],same_sdc_as_parent=(BUILD/'source/tang/boards/neo/neo.sdc').read_bytes()==(PARENT/'source/tang/boards/neo/neo.sdc').read_bytes(),same_cst_as_parent=(BUILD/'source/tang/boards/neo/neo.cst').read_bytes()==(PARENT/'source/tang/boards/neo/neo.cst').read_bytes())
    frequencies={'clk50':50,'bus80_clk':80,'core_clk':800,'rtc_clk':10,'ddr3_mem_clk':300,'ddr3_sys_clk':75,'vid_pclk':74.375,'vid_clk5x':371.875,'CLK_48M':48,'PHY_CLKOUT':60,'fclk_960M':960,'sclk':120}
    clock_rows={}
    for name,hz in frequencies.items():
        f=re.findall(r'^\s*\d+\s+'+name+r'\s+(?:Base|Generated)\s+[\d.]+\s+([\d.]+)MHz',tr,re.M)
        clock_rows[name]=dict(expected_mhz=hz,observed_mhz=float(f[0]) if len(f)==1 else None,passed=len(f)==1 and abs(float(f[0])-hz)<.051)
    routes=global_clock_routes(rpt)
    required=json.loads((BUILD/'source/tang/boards/neo/timing_closure.json').read_text())['required_primary_clocks']
    primary={n for n,k,_ in routes if k=='PRIMARY'}
    clock_result=dict(passed=all(r['passed'] for r in clock_rows.values()) and not(set(required)-primary),clocks=clock_rows,required_primary=required,missing_primary=sorted(set(required)-primary),global_routes=routes,no_fmax_path_messages=re.findall(r'^No timing paths to get frequency of (.+)!$',tr,re.M))
    req=(BUILD/'build.tcl').read_text();cmd=(pnr/'cmd.do').read_text();options={}
    for name in ['place_option','route_option','clock_route_order']:
        w=re.findall(r'^set_option -'+name+r' (\d+)$',req,re.M);g=re.findall(r'^-'+name+r' (\d+)$',cmd,re.M)
        options[name]=dict(requested=w,applied=g,passed=len(w)==1 and len(g)==1 and w[0]==g[0])
    want=re.findall(r'^set_option -replicate_resources ([01])$',req,re.M);got=bool(re.search(r'^-replicate$',cmd,re.M))
    options['replicate_resources']=dict(requested=want,applied=int(got),passed=len(want)==1 and int(want[0])==int(got))
    jobs=dict(copy=lambda:audit_copy(vg),scanout=lambda:audit_scanout(vg),gpu_owner_replication=lambda:audit_owner(vo),timing_closure=lambda:audit_closure(BUILD/'source',pnr/'console_neo.tr'),cpu_ddr_fifo_registers=lambda:audit_fifo(vg),gpu_reset_tree=lambda:audit_reset_tree(vg,pnr/'console_neo.rpt.txt',control_local=True),gpu_pixel_mask=lambda:audit_mask(vg),gpu_pixel_mask_routed=lambda:audit_mask(vo,routed=True),gpu_pixel_selector=lambda:audit_selector(vg),gpu_pixel_selector_routed=lambda:audit_selector(vo,routed=True),ddr_profile=lambda:audit_ddr(BUILD/'source','neo-fifo-registers'))
    audits={}
    for name,job in jobs.items():
        try:audits[name]=job()
        except Exception as e:audits[name]=dict(passed=False,error=repr(e))
        print(name+': '+('PASS' if audits[name]['passed'] else 'FAIL'),flush=True)
    for name,digest in inputs.items():assert sha(Path(name))==digest,name
    gates=dict(global_timing=summary['status']=='PASS' and set(timing)=={'setup','hold','recovery','removal'} and all(v>=0 for v in timing.values()),constraints=constraint_result['passed'] and constraint_result['same_sdc_as_parent'] and constraint_result['same_cst_as_parent'],clocks=clock_result['passed'],pnr_options=all(r['passed'] for r in options.values()),frozen_sources=set(manifest)==actual_files and all(source_checks.values()),memory_images=all(r['passed'] for r in mirror_checks.values()),synthesis_audits=all(r['passed'] for r in audits.values()),part='<Part Number>: GW5AST-LV138PG484AC1/I0' in tr)
    r=dict(audit_complete=True,hardware_access=False,loaded=False,load_authorized=False,qualification_status='PASS' if all(gates.values()) else 'FAIL',gates=gates,global_timing=summary,timing_checks_ns=timing,clocks=clock_result,constraints=constraint_result,pnr_options=options,synthesis_audits=audits,changed_sources=[n for n,ok in source_checks.items() if not ok],memory_images=mirror_checks,netlist_sha256=sha(vg),bitstream_sha256=sha(pnr/'console_neo.fs'),inputs=inputs,limits=['Uses explicit ECO netlist console_neo.vg; no synthesized directory or route.json is invented.','Global STA and structural audits do not prove boot, GPU behavior or pulse capture.','The dedicated reset and observation-path audits remain separate.','No-Fmax-path messages are reported verbatim, not treated as absence of all hardCPU analysis.','No FAIL is suppressed or reclassified as PASS.'])
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(result=str(args.out),sha256=sha(args.out),qualification=r['qualification_status'],timing=timing),indent=2))
if __name__=='__main__':main()
