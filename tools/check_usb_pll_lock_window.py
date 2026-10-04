#!/usr/bin/env python3
"""Exercise real USB PLL LOCK hold values from current and prior console tops.

No Gowin invocation or hardware access. The old top must fail the 2 ms guard;
the current top must pass qualification, a late glitch and stopped-clock reset.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
IVBASE=Path('/tmp/console-usb-sim-tools/extracted/usr')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configuration(top, module, sdc):
    source=top.read_text()
    source=re.sub(r'//[^\n]*', '', source)
    default=int(re.search(r'parameter\s+HOLD_CYCLES\s*=\s*(\d+)',module.read_text())[1])
    # Derive the 48/60 MHz domains from the actual SDC clock ratios.
    clocks={}
    for line in sdc.read_text().splitlines():
        m=re.match(r'create_clock -name (\w+) -period ([\d.]+)',line)
        if m:clocks[m[1]]=1000.0/float(m[2])
        m=re.match(r'create_generated_clock -name (\w+).* -master_clock (\w+) -divide_by (\d+) -multiply_by (\d+)',line)
        if m:clocks[m[1]]=clocks[m[2]]*int(m[4])/int(m[3])
    cases=[]
    domains={'clk':'clk50','clk48':'CLK_48M','phy_clk':'PHY_CLKOUT'}
    for instance in ['u_usb_ref_start','u_usb_phy_start','u_usb_controller_start']:
        pat=r'usb_reset_release\s*(?:#\s*\(\s*\.HOLD_CYCLES\s*\(\s*(\d+)\s*\)\s*\))?\s+'+instance+r'\s*\((.*?)\);'
        matches=list(re.finditer(pat,source,re.S))
        if len(matches)!=1:raise ValueError('Cannot uniquely extract '+instance)
        m=matches[0]
        cm=re.search(r'\.clk\s*\(\s*(\w+)\s*\)',m[2])
        if cm is None or cm[1] not in domains:raise ValueError('Unexpected clock for '+instance)
        clock=cm[1]
        mhz=clocks[domains[clock]]
        if mhz!=int(mhz):raise ValueError('Noninteger clock MHz is unsupported by this bench')
        cases.append(dict(instance=instance,clock=clock,clock_mhz=int(mhz),
                          hold_cycles=int(m[1]) if m[1] else default,
                          explicit_parameter=m[1] is not None,
                          instance_text=m[0]))
    phy=re.search(r'USB2_0_SoftPHY_Top\s+u_usb_softphy_top\s*\((.*?)\);',source,re.S)
    if phy is None:raise ValueError('Cannot find the HS PHY instance')
    phy_inputs={}
    for pin in ['pll_locked_i','rst_i']:
        m=re.search(r'\.'+pin+r'\s*\(([^)]+)\)',phy[1])
        if m is None:raise ValueError('Cannot extract HS PHY '+pin)
        phy_inputs[pin]=m[1].strip()
    return cases,phy_inputs


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--previous-root',type=Path,default=ROOT/'tang/impl/gpu_usb_hs33_ep0_r1/source')
    p.add_argument('--current-root',type=Path,default=ROOT)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    bench=ROOT/'TESTS/rtl/usb_pll_lock_window_tb.sv'
    report=dict(scope='Digital qualification/reset behavior using hold values extracted from the real console tops',
                limits=['No analog PLL, LOCK-glitch probability or metastability model',
                        'Exact reset-release chain instances, with digitally driven LOCK and PLL output clocks; no actual PLL acquisition',
                        'No new timing, bitstream or board proof'],cases=[])
    watched=[bench,Path(__file__)]
    for revision,root in [('previous',a.previous_root),('current',a.current_root)]:
        top=root/'tang/rtl/console_top.v'
        module=root/'tang/rtl/usb/usb_reset_release.v'
        sdc=root/'tang/constr/gpu.sdc'
        watched += [top,module,sdc]
        config,phy_inputs=configuration(top,module,sdc)
        if revision=='current' and [c['clock'] for c in config]!=['clk','clk','phy_clk']:
            raise ValueError('Current topology must qualify both LOCKs on board clk, then release controller on phy_clk')
        if config[2]['hold_cycles']!=64:raise ValueError('Unexpected controller reset hold')
        for guard in ([0,1] if revision=='previous' else [2]):
            report['cases'].append(dict(revision=revision,top=str(top),module=str(module),
                                       sdc=str(sdc),configuration=config,phy_inputs=phy_inputs,guard_stage=guard))
    hashes={str(x):sha(x) for x in watched}
    report['sha256']=hashes
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='usb-pll-lock-window-') as td:
        for case in report['cases']:
            label=case['revision']+'_guard'+str(case['guard_stage'])
            exe=Path(td)/(label+'.vvp')
            model=Path(td)/(label+'.v')
            config=case['configuration']
            model.write_text('module usb_top_lock_chain_model(input clk,clk48,phy_clk,pll_f_lock,pll_b_lock,PHY_RESET,\n'
                             ' output pll_b_reset,phy_lock_reset,rst_usb,qualified_phy_lock,combined_phy_reset);\n'+
                             '\n'.join(c['instance_text'] for c in config)+'\n'+
                             'assign qualified_phy_lock='+case['phy_inputs']['pll_locked_i']+';\n'+
                             'assign combined_phy_reset='+case['phy_inputs']['rst_i']+';\nendmodule\n')
            case['generated_model_sha256']=sha(model)
            cmd=[str(IVBASE/'bin/iverilog'),'-B',str(IVBASE/'lib/x86_64-linux-gnu/ivl'),
                 '-g2012','-s','usb_pll_lock_window_tb','-o',str(exe),
                 '-Pusb_pll_lock_window_tb.GUARD_STAGE='+str(case['guard_stage']),
                 '-Pusb_pll_lock_window_tb.REF_HOLD='+str(config[0]['hold_cycles']),
                 '-Pusb_pll_lock_window_tb.PHY_HOLD='+str(config[1]['hold_cycles']),
                 '-Pusb_pll_lock_window_tb.CONTROLLER_HOLD='+str(config[2]['hold_cycles']),
                 '-Pusb_pll_lock_window_tb.REF_QUAL_MHZ='+str(config[0]['clock_mhz']),
                 '-Pusb_pll_lock_window_tb.PHY_QUAL_MHZ='+str(config[1]['clock_mhz']),
                 str(bench),str(model),case['module']]
            c=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
            case['compile']=dict(command=cmd,returncode=c.returncode,stderr=c.stderr)
            case['expectation_met']=False
            if c.returncode==0:
                r=subprocess.run([str(IVBASE/'bin/vvp'),str(exe)],capture_output=True,text=True,timeout=30)
                case['run']=dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
                case['pass']=r.returncode==0 and 'PASS PLL LOCK chain' in r.stdout
                case['expectation_met']=(r.returncode!=0 and 'LOCK released before 2 ms' in r.stdout) if case['revision']=='previous' else case['pass']
                print(label,case['expectation_met'],r.stdout.strip(),flush=True)
                a.output.with_name(a.output.stem+'_'+label+'.log').write_text(r.stdout+r.stderr)
    report['sources_unchanged']=all(sha(Path(x))==h for x,h in hashes.items())
    report['pass']=all(c['expectation_met'] for c in report['cases']) and report['sources_unchanged']
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(('PASS' if report['pass'] else 'FAIL')+'; '+str(a.output))
    return 0 if report['pass'] else 1


if __name__=='__main__':
    raise SystemExit(main())
