#!/usr/bin/env python3
"""Read-only R21r2 reset audit. No routing, no board commands, no qualification by omission."""
from pathlib import Path
import argparse,hashlib,json,re,sys,functools
ROOT=Path('/home/michael/console');HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(HERE.parents[1]));sys.path.insert(0,str(ROOT/'TESTS/neo_720p_20261012/reset_sequence_20261025'))
import build_memory_capture as b
from audit_routed import cells as routed_cells
from audit_postroute import parse_sdf,clock_period
from gowin_toolchain import PRIMITIVES
from check_geometry_timing import inspect
from neo.timing import timing_checks
PARENT=ROOT/'tang/impl/console_neo_n56r21r1_capture_memory'
BUILD=ROOT/'tang/impl/console_neo_n56r21r2_resetqual_coupled'
PREFIX='u_reset_trial/'
GATES={'neo_qualified_pll_lut','u_soc/neo_qualified_clear_lut'}
RESET_FF=['ae350_rst_sync_0_s0','ae350_rst_sync_1_s0','u_soc/init_sync_0_s0','u_soc/init_sync_1_s0']
SYNCS=['u_reset_trial/ready_meta_0_s0','u_reset_trial/ready_meta_1_s0','u_reset_trial/reset_meta_0_s0','u_reset_trial/reset_meta_1_s0']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def pin_directions():
    text=PRIMITIVES.read_text();result={}
    for name,body in re.findall(r'^module\s+(\w+)\b(.*?)^endmodule',text,re.M|re.S):
        ports=set()
        for decl in re.findall(r'^\s*output\s+([^;]+);',body,re.M):
            decl=re.sub(r'\[[^]]*\]','',decl)
            ports|=set(re.findall(r'\b[A-Za-z_]\w*\b',decl))-{'wire','reg','logic','signed','unsigned'}
        result.setdefault(name,set()).update(ports)
    assert {'Q'}<=result['DFFCE'] and {'SUM','COUT'}<=result['ALU']
    return result

OUTPUTS=pin_directions()
def drivers(data):
    found={}
    for name,(kind,pins) in data.items():
        for pin in OUTPUTS.get(kind,set()):
            if pin in pins:
                key=('$constant',kind) if kind in ('GND','VCC') else (name,pin)
                found.setdefault(pins[pin],set()).add(key)
    return found

def flatten_helper(net):
    flat={};prm={}
    def descend(module,prefix,binding):
        body=b.block(net,module);assert not re.findall(r'^assign ',body,re.M)
        c,p=b.cells(body),b.params(body)
        widths={name:(int(hi),int(lo)) for hi,lo,name in re.findall(r'^(?:input|output)\s+\[(\d+):(\d+)\]\s+(\w+);',body,re.M)}
        def resolve(token):
            if token in ('GND','VCC'):return '$'+token
            m=re.fullmatch(r'(\w+)(\[[\d:]+\])?',token);assert m,token
            base,slice_=m[1],m[2] or ''
            if base not in binding:return prefix+token
            target=binding[base]
            if slice_:
                assert ':' not in slice_,token
                if re.search(r'\[\d+\]$',target):
                    assert base in widths and widths[base][0]==widths[base][1]==int(slice_[1:-1]),(base,slice_,target)
                    return target
                target=re.sub(r'\[\d+:\d+\]$','',target)+slice_
            return target
        for name,(kind,pins) in c.items():
            if kind=='neo_reset_trial_rx':
                descend(kind,prefix+name+'/',{p:resolve(v) if ':' not in v else resolve(v.split('[')[0])+v[v.index('['):] for p,v in pins.items()})
            else:flat[prefix+name]=(kind,{p:resolve(v) for p,v in pins.items()})
        for name,value in p.items():prm[prefix+name]=value
    root=b.block(net,'neo_reset_trial')
    ports=re.findall(r'^(?:input|output)\s+(?:\[[^]]+\]\s+)?(\w+);',root,re.M)
    descend('neo_reset_trial',PREFIX,{p:'@'+p for p in ports})
    return flat,prm

def boundary_labels(flat):
    d=drivers(flat);output_ports={'release_request','delay_mode','command_epoch','holding','delay_done','ahb_tick','rtc_tick'}
    labels={}
    for net,ds in d.items():
        if net.startswith('@') and net[1:].split('[')[0] in output_ports:
            assert len(ds)==1,(net,ds)
            source=next(iter(ds));assert source[0]!='$constant'
            labels[source]=('$helper_port',net[1:])
    assert len(labels)==10,labels
    return labels

def structural(old,op,new,np,old_net,new_net):
    od,nd=drivers(old),drivers(new)
    old_flat,_=flatten_helper(old_net);flat,hp=flatten_helper(new_net)
    ol,nl=boundary_labels(old_flat),boundary_labels(flat)
    canonical=lambda ds,labels:{labels.get(x,x) for x in ds}
    missing=sorted(n for n in old.keys()-new.keys() if not n.startswith(PREFIX))
    unexpected_added=sorted(n for n in new.keys()-old.keys() if not n.startswith(PREFIX) and n not in GATES)
    changes={};aliases={}
    for name in old.keys()&new.keys():
        if name.startswith(PREFIX):continue
        k,p=old[name];nk,nv=new[name]
        differences={}
        for pin in p.keys()|nv.keys():
            if name in ('u_soc/init_sync_0_s0','u_soc/init_sync_1_s0') and pin=='CLEAR':continue
            a,z=p.get(pin),nv.get(pin)
            sd=canonical(od.get(a,set()),ol);dd=canonical(nd.get(z,set()),nl)
            if a==z and sd==dd:continue
            differences[pin]=dict(before=a,after=z,before_drivers=sorted(sd),after_drivers=sorted(dd),equivalent=bool(sd) and sd==dd and len(sd)==1)
        if k!=nk or differences:
            good=k==nk and all(v['equivalent'] for v in differences.values())
            (aliases if good else changes)[name]=dict(before=old[name],after=new[name],pins=differences)
    param_changes={k:dict(before=v,after=np.get(k)) for k,v in op.items() if not k.startswith(PREFIX) and np.get(k)!=v}
    unexpected_params={k:v for k,v in np.items() if k not in op and not k.startswith(PREFIX) and k not in {g+'.INIT' for g in GATES}}
    # Exact new gate truth tables and driver identities; labels prevent accidental net-name reliance.
    errors=[]
    check=lambda condition,why: errors.append(why) if not condition else None
    for name,init in [('neo_qualified_pll_lut',"4'h2"),('u_soc/neo_qualified_clear_lut',"4'hB")]:
        check(name in new and new[name][0]=='LUT2','missing/type '+name)
        check(np.get(name+'.INIT')==init,'INIT '+name)
    if not errors:
        gp=new['neo_qualified_pll_lut'][1];gc=new['u_soc/neo_qualified_clear_lut'][1]
        check(nd.get(gp['I0'],set())==od.get('pll_ae350_lock',set()) and bool(od.get('pll_ae350_lock')), 'coupled PLL input')
        check(nd.get(gp['I1'],set())=={('ae350_rst_sync_1_s0','Q')},'coupled first-chain input')
        check(nd.get(gc['I0'],set())=={('ae350_rst_sync_1_s0','Q')},'CLEAR first-chain input')
        check(canonical(nd.get(gc['I1'],set()),nl)=={('$helper_port','release_request')},'CLEAR permission input')
        for f in ('u_soc/init_sync_0_s0','u_soc/init_sync_1_s0'):
            check(nd.get(new[f][1]['CLEAR'],set())=={('u_soc/neo_qualified_clear_lut','F')},f+' CLEAR')
    # Match every helper primitive, parameter and data/control origin to the synthesized graph.
    fd=drivers(flat);top=b.cells(b.block(old_net,'console_neo'))['u_reset_trial'][1]
    external={p:od.get(net,set()) for p,net in top.items()}
    external['pll_ready']={('neo_qualified_pll_lut','F')}
    helper_errors=[];external_checks=[]
    for name,(kind,pins) in flat.items():
        if kind in ('GND','VCC'):continue
        if name not in new or new[name][0]!=kind:
            helper_errors.append(dict(cell=name,reason='missing/type'));continue
        for pin,net in pins.items():
            if pin in OUTPUTS.get(kind,set()):continue
            expected=fd.get(net,set())
            if net in ('$GND','$VCC'):expected={('$constant',net[1:])}
            if not expected and net.startswith('@'):
                expected=external.get(net[1:],set());external_checks.append(dict(cell=name,pin=pin,source=net,expected=sorted(expected)))
            actual=nd.get(new[name][1].get(pin),set())
            if len(expected)!=1 or expected!=actual:helper_errors.append(dict(cell=name,pin=pin,net=net,expected=sorted(expected),actual=sorted(actual)))
    for name,value in hp.items():
        if np.get(name)!=value:helper_errors.append(dict(parameter=name,expected=value,actual=np.get(name)))
    extra_helper=sorted(n for n in new if n.startswith(PREFIX) and n not in flat)
    return dict(passed=not(missing or unexpected_added or changes or param_changes or unexpected_params or errors or helper_errors or extra_helper),missing_cells=missing,unexpected_added_cells=unexpected_added,application_changes=changes,alias_only_application_changes=aliases,parameter_changes=param_changes,unexpected_parameters=unexpected_params,reset_gate_errors=errors,helper_errors=helper_errors,helper_extra_cells=extra_helper,helper_external_checks=external_checks,helper_cell_count=len(flat),unknown_primitive_types=sorted({k for k,_ in new.values()}-set(OUTPUTS)))

def table_paths(tr):
    kind=None;rows=[]
    for lineno,line in enumerate(tr.splitlines(),1):
        m=re.search(r'<Report Command>:report_timing -(setup|hold|recovery|removal)\b',line)
        if m:kind=m[1]
        fields=re.split(r'\s{2,}',line.strip())
        if kind and len(fields)==9 and fields[0].isdigit() and re.fullmatch(r'-?\d+\.\d+',fields[1]) and '/' in fields[2] and '/' in fields[3]:
            rows.append(dict(kind=kind,slack_ns=float(fields[1]),source=fields[2],destination=fields[3],launch_clock=fields[4],latch_clock=fields[5],relation_ns=float(fields[6]),skew_ns=float(fields[7]),data_delay_ns=float(fields[8]),line=lineno))
    return rows

def local_timing(new,sdf,tr,sdc):
    incoming,cq,clocks,setup,counts=parse_sdf(sdf);nd=drivers(new)
    periods={'clk_d':clock_period(sdc,tr,'clk50'),'vid_hclk':clock_period(sdc,tr,'bus80_clk'),'rtc_clk':clock_period(sdc,tr,'rtc_clk')}
    visiting=set();gaps={};terminal=[]
    @functools.lru_cache(None)
    def origins(pin):
        name,port=pin.rsplit('/',1)
        if name in cq and port=='Q':return {name:cq[name]}
        if pin in visiting:raise ValueError('cycle '+pin)
        if name in new:
            kind,pins=new[name]
            if kind in ('GND','VCC'):return {}
            if port not in OUTPUTS.get(kind,set()):
                want={a+'/'+b for a,b in nd.get(pins.get(port),set()) if a!='$constant'}
                got={a for a,_ in incoming.get(pin,[])}
                if want and want!=got:gaps[pin]=dict(expected=sorted(want),actual=sorted(got))
            elif kind.startswith('LUT') or kind=='INV':
                want={name+'/'+p for p in pins if p.startswith('I')};got={a for a,_ in incoming.get(pin,[])}
                if want!=got:gaps[pin]=dict(expected=sorted(want),actual=sorted(got))
        if not incoming.get(pin):
            if name in new:
                ds=nd.get(new[name][1].get(port),set())
                if ds and all(a=='$constant' for a,b in ds):return {}
            terminal.append(pin);return {'TERMINAL:'+pin:(0.,0.,0.)}
        visiting.add(pin);found={}
        for source,delay in incoming[pin]:
            for origin,before in origins(source).items():
                v=tuple(a+b for a,b in zip(before,delay))
                found[origin]=tuple(max(a,b) for a,b in zip(found[origin],v)) if origin in found else v
        visiting.remove(pin);return found
    targets=RESET_FF+SYNCS;coverage={n:n in new for n in targets}
    bounds=[];missing=[];foreign=[]
    for name in targets:
        if name not in new:continue
        target=name+'/D';net=new[name][1]['D']
        if nd.get(net,set()) and all(a=='$constant' for a,b in nd[net]):continue
        found=origins(target)
        for origin,delay in found.items():
            if origin.startswith('TERMINAL:'):
                foreign.append(dict(source=origin,destination=target));continue
            if origin not in clocks or name not in clocks or target not in setup:
                missing.append(dict(source=origin,destination=target));continue
            sc,sd=clocks[origin];dc,dd=clocks[name]
            sn=new[origin][1]['CLK'];dn=new[name][1]['CLK']
            if sc==dc and sn==dn and sn in periods:
                value=periods[sn]+min(dd)-max(sd)-max(delay)-setup[target]
                bounds.append(dict(source=origin,destination=target,clock=sn,period_ns=periods[sn],conservative_setup_ns=value,data_by_corner_ns=delay,source_clock_ns=sd,destination_clock_ns=dd,setup_ns=setup[target]))
            else:foreign.append(dict(source=origin,destination=target,source_clock=sc,destination_clock=dc,data_by_corner_ns=delay,classification='cross-domain; report/max_delay required, no synchronous-bound assumption'))
    rows=table_paths(tr)
    relevant=[r for r in rows if r['destination'].split('/')[0]=='u_reset_trial' or any(r['destination'].startswith(n+'/') for n in targets)]
    async_requirements={};sdf_cells={}
    for part in sdf.split('\n  (CELL\n')[1:]:
        m=re.search(r'\(INSTANCE ([^\s)]+)\)',part)
        if m:sdf_cells[m[1].replace('\\','')]=part
    for name in targets:
        if name not in new:continue
        pins=new[name][1]
        for pin in ('CLEAR','PRESET','RESET','SET'):
            if pin not in pins:continue
            ds=nd.get(pins[pin],set())
            if ds and all(a=='$constant' for a,b in ds):continue
            key=name+'/'+pin;part=sdf_cells.get(name,'')
            rec=re.findall(r'\(RECOVERY \(negedge '+pin+r'\) \(posedge CLK\) \(([^)]+)\)\)',part)
            rem=re.findall(r'\(REMOVAL \(negedge '+pin+r'\) \(posedge CLK\) \(([^)]+)\)\)',part)
            hits=[r for r in rows if r['destination']==key and r['kind'] in ('recovery','removal')]
            async_requirements[key]=dict(drivers=sorted(ds),recovery_requirement_triplets=rec,removal_requirement_triplets=rem,reported_paths=hits,reported_kinds=sorted({r['kind'] for r in hits}),declared_existing_exception=name.startswith('ae350_rst_sync_'),pulse_width_qualification=False)
    interstage_targets={'ae350_rst_sync_1_s0/D','u_soc/init_sync_1_s0/D','u_reset_trial/ready_meta_1_s0/D','u_reset_trial/reset_meta_1_s0/D'}
    selected=[r for r in bounds if r['destination'] in interstage_targets]
    return dict(periods_ns=periods,coverage=coverage,sdf_counts=counts,conservative_setup_bounds=bounds,interstage_setup_passed=all(coverage.values()) and {r['destination'] for r in selected}==interstage_targets and all(r['conservative_setup_ns']>0 for r in selected) and not gaps,missing_clock_or_setup=missing,foreign_or_async_origins=foreign,cone_gaps=gaps,terminal_origins=sorted(set(terminal)),reset_requirements=async_requirements,reported_helper_paths=relevant,reported_helper_negative_paths=[r for r in relevant if r['slack_ns']<0],limits=['Conservative intra-domain SDF setup bounds only; no inferred hold or CDC phase relation.','Recovery/removal printed paths are evidence, missing paths remain missing.','Existing PRESET false path is enumerated, never treated as a timing proof.','No minimum asynchronous pulse-width guarantee or hardCPU reset contract inferred.'])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--self-test',action='store_true');args=ap.parse_args()
    assert not args.out.exists();old,op=routed_cells(PARENT/'impl/pnr/console_neo.vo')
    old_net=(PARENT/'console_neo.vg').read_text();new_net=(BUILD/'console_neo.vg').read_text()
    if args.self_test:
        d=drivers(old);flat,_=flatten_helper(new_net);labels=boundary_labels(flat)
        assert len(labels)==10 and any(k=='ALU' for k,p in flat.values())
        assert ('u_soc/init_sync_1_s0','Q') in d[old['u_soc/init_sync_1_s0'][1]['Q']]
        controls={n:old[n] for n in RESET_FF}
        result=dict(passed=True,mode='parser and boundary self-test only; no candidate routed result',routed_cells=len(old),helper_flat_cells=len(flat),helper_output_labels={str(k):v for k,v in labels.items()},control_cells=controls,primitive_library_sha256=sha(PRIMITIVES))
    else:
        route=json.loads((BUILD/'route_result.json').read_text())
        assert route['returncode']==0 and route['status']=='ROUTED_NOT_QUALIFIED'
        assembly=json.loads((BUILD/'assembly.json').read_text())
        for name,digest in assembly['inputs'].items():assert sha(BUILD/name)==digest,name
        assert b.manifest(BUILD/'source')==json.loads((BUILD/'sources.json').read_text())
        for name in ['neo.cst','neo.sdc']:
            assert (BUILD/'source/tang/boards/neo'/name).read_bytes()==(PARENT/'source/tang/boards/neo'/name).read_bytes()
        pnr=BUILD/'impl/pnr'
        frozen_paths=[PARENT/'impl/pnr/console_neo.vo',BUILD/'console_neo.vg',BUILD/'assembly.json',BUILD/'sources.json',BUILD/'route_result.json',BUILD/'source/tang/boards/neo/neo.sdc',pnr/'console_neo.vo',pnr/'console_neo.sdf',pnr/'console_neo.tr',pnr/'console_neo.fs',PRIMITIVES]
        frozen={str(p):sha(p) for p in frozen_paths}
        new,np=routed_cells(pnr/'console_neo.vo')
        structure=structural(old,op,new,np,old_net,new_net)
        tr=(pnr/'console_neo.tr').read_text();sdf=(pnr/'console_neo.sdf').read_text();sdc=(BUILD/'source/tang/boards/neo/neo.sdc').read_text()
        lt=local_timing(new,sdf,tr,sdc);global_sta=inspect(BUILD,'console_neo')
        result=dict(audit_complete=True,hardware_access=False,load_authorized=False,structure=structure,reset_timing=lt,global_timing=global_sta,timing_checks=timing_checks(tr),qualification_status='REVIEW_REQUIRED',limits=['This targeted audit cannot replace complete timing/CDC/DDR/observer checks.','No board state or bitstream programming is performed.'])
        for name,digest in frozen.items():assert sha(Path(name))==digest,name
        result['inputs']=frozen
    result['script_sha256']=sha(Path(__file__));args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(result=str(args.out),sha256=sha(args.out)),indent=2))
if __name__=='__main__':main()
