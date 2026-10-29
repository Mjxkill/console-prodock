#!/usr/bin/env python3
"""Append semantic proof for exact INV lowering/ADD pin swaps; never rewrite audit."""
from pathlib import Path
import copy,hashlib,json,runpy,subprocess
HERE=Path(__file__).resolve().parent
A=runpy.run_path(str(HERE/'audit_routed.py'))
B=A['BUILD'];OUT=HERE/'postroute_helper_equivalence_02'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def normalize(flat,params,actual,ap):
    f=copy.deepcopy(flat);p=dict(params);records=[]
    for n,(k,pins) in list(f.items()):
        if k in ('GND','VCC'):continue
        ak,actual_pins=actual[n]
        if k=='INV' and ak=='LUT1':
            assert set(pins)=={'I','O'} and set(actual_pins)=={'I0','F'}
            assert ap[n+'.INIT']=="2'h1"
            f[n]=('LUT1',dict(I0=pins['I'],F=pins['O']));p[n+'.INIT']="2'h1"
            records.append(dict(cell=n,conversion='INV to LUT1 INIT1'))
        elif k=='ALU' and ak=='ALU' and pins.get('I1')=='$GND' and actual_pins.get('I0')=='GND':
            assert p[n+'.ALU_MODE']==ap[n+'.ALU_MODE']=='0'
            pins['I0'],pins['I1']=pins['I1'],pins['I0']
            records.append(dict(cell=n,conversion='ADD I0/I1 permutation'))
    return f,p,records

def check(flat,fp,actual,ap,net):
    fd=A['drivers'](flat);ad=A['drivers'](actual)
    top=A['b'].cells(A['b'].block(net,'console_neo'))['u_reset_trial'][1]
    external={p:ad.get(n,set()) for p,n in top.items()}
    errors=[]
    for n,(k,pins) in flat.items():
        if k in ('VCC','GND'):continue
        if n not in actual or actual[n][0]!=k:errors.append((n,'type'));continue
        for pin,signal in pins.items():
            if pin in A['OUTPUTS'][k]:continue
            want=fd.get(signal,set())
            if signal in ('$GND','$VCC'):want={('$constant',signal[1:])}
            if not want and signal.startswith('@'):want=external.get(signal[1:],set())
            got=ad.get(actual[n][1].get(pin),set())
            if len(want)!=1 or want!=got:errors.append((n,pin,sorted(want),sorted(got)))
    hp={k:v for k,v in ap.items() if k.startswith(A['PREFIX'])}
    if fp!=hp:errors.append(('params',sorted(fp.items()^hp.items())))
    extra=[n for n in actual if n.startswith(A['PREFIX']) and n not in flat]
    errors += [('extra',n) for n in extra]
    return errors

def main():
    OUT.mkdir(exist_ok=False)
    net=(B/'console_neo.vg').read_text();flat,fp=A['flatten_helper'](net)
    actual,ap=A['routed_cells'](B/'impl/pnr/console_neo.vo')
    normalized,np,records=normalize(flat,fp,actual,ap)
    errors=check(normalized,np,actual,ap,net);assert not errors,errors
    original=json.loads((HERE/'postroute_01/reset.json').read_text())['structure']
    outside=['missing_cells','unexpected_added_cells','application_changes','parameter_changes','unexpected_parameters','reset_gate_errors','helper_extra_cells']
    assert not any(original[k] for k in outside)
    # Reject a non-commutative input substitution and a mode change, independently.
    add=next(n for n,(k,p) in normalized.items() if k=='ALU' and p.get('I0')=='$GND' and p.get('I3')=='$VCC')
    bad=copy.deepcopy(actual);bad[add][1]['I1'],bad[add][1]['I3']=bad[add][1]['I3'],bad[add][1]['I1']
    assert check(normalized,np,bad,ap,net)
    badp=dict(ap);badp[add+'.ALU_MODE']='1';assert check(normalized,np,actual,badp,net)
    inv=next(r['cell'] for r in records if r['conversion'].startswith('INV'))
    badp=dict(ap);badp[inv+'.INIT']="2'h2";assert check(normalized,np,actual,badp,net)
    # Use official models, not handwritten ADD equations. Test all binary inputs,
    # then record four-state X/Z differences without claiming four-state identity.
    tb=r'''`timescale 1ns/1ps
module tb;
reg a,b,c,d;wire s0,k0,s1,k1,ni,nl,wrong_s,wrong_k;
integer i,j,n,binary=0,four_differences=0,negative=0;
reg [1:0] vals[0:3];
ALU #(.ALU_MODE(0)) first(.I0(a),.I1(b),.I3(d),.CIN(c),.SUM(s0),.COUT(k0));
ALU #(.ALU_MODE(0)) swapped(.I0(b),.I1(a),.I3(d),.CIN(c),.SUM(s1),.COUT(k1));
ALU #(.ALU_MODE(1)) wrong_mode(.I0(a),.I1(b),.I3(d),.CIN(c),.SUM(wrong_s),.COUT(wrong_k));
INV inv(.I(a),.O(ni));LUT1 #(.INIT(2'h1)) lut(.I0(a),.F(nl));
function state;input integer v;begin case(v)0:state=0;1:state=1;2:state=1'bx;3:state=1'bz;endcase end endfunction
initial begin
 for(i=0;i<16;i=i+1)begin {a,b,c,d}=i;#1;
  if({s0,k0} !== {s1,k1})$fatal(1,"BINARY_ADD_MISMATCH %d",i);
  if(ni!==nl)$fatal(1,"INVERTER_MISMATCH");
  if({s0,k0} !== {wrong_s,wrong_k})negative=negative+1;
  binary=binary+1;
 end
 for(i=0;i<4;i=i+1)begin a=state(i);#1;if(ni!==nl)$fatal(1,"FOUR_STATE_INV");end
 for(i=0;i<4;i=i+1)for(j=0;j<4;j=j+1)begin
  a=state(i);b=0;c=state(j);d=1;#1;
  if({s0,k0} !== {s1,k1})begin four_differences=four_differences+1;$display("XPROP_DIFFERENCE data=%b carry=%b original=%b routed=%b",a,c,{s0,k0},{s1,k1});end
 end
 if(negative==0)$fatal(1,"NEGATIVE_CONTROL_INEFFECTIVE");
 $display("PASS BINARY_CASES=%0d INV_4STATE=4 NEGATIVE=%0d XPROP_DIFFERENCES=%0d",binary,negative,four_differences);$finish;
end
endmodule
'''
    (OUT/'tb.sv').write_text(tb)
    compiler=Path('/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog')
    with (OUT/'compile.log').open('w') as log:
        subprocess.run([str(compiler),'-B',str(compiler.parent.parent/'lib/x86_64-linux-gnu/ivl'),'-g2012','-s','tb','-o',str(OUT/'sim.vvp'),str(OUT/'tb.sv'),str(A['PRIMITIVES'])],stdout=log,stderr=log,check=True,timeout=60)
    with (OUT/'simulation.log').open('w') as log:
        subprocess.run([str(compiler.parent/'vvp'),str(OUT/'sim.vvp')],stdout=log,stderr=log,check=True,timeout=30)
    log=(OUT/'simulation.log').read_text();assert 'PASS BINARY_CASES=16 INV_4STATE=4' in log
    paths=[Path(__file__),HERE/'audit_routed.py',HERE/'postroute_01/reset.json',B/'console_neo.vg',B/'impl/pnr/console_neo.vo',A['PRIMITIVES'],OUT/'tb.sv',OUT/'compile.log',OUT/'simulation.log']
    result=dict(passed=True,hardware_access=False,timing_qualified=False,scope='Binary combinational equivalence of exact Gowin lowering operations plus graph/pin/parameter identity of every other helper primitive',original_audit_fail_retained=True,conversions=records,helper_cells=len(flat),remaining_errors=errors,negative_controls=['ALU I1/I3 substitution rejected','ALU_MODE change rejected','LUT1 wrong INIT rejected','official ADD/SUB test distinguishes non-equivalence'],limits=['ALU mode0 is binary equivalent when I0/I1 are swapped; official four-state model may propagate X/Z differently. Differences are logged, not suppressed.','No analog behavior, timing or pulse capture guarantee inferred.','No build or original audit modified.'],inputs={str(p):sha(p) for p in paths})
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(result=str(OUT/'result.json'),sha256=sha(OUT/'result.json'),conversions=len(records)),indent=2))
if __name__=='__main__':main()
