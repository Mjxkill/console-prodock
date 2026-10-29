#!/usr/bin/env python3
"""Read existing routed USB clocks and FIFO routes; no build or device access."""
from pathlib import Path
import hashlib,json,re,sys
ROOT=Path('/home/michael/console')
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from check_usb_phy_cdc_timing import expected_paths
PHY='u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
norm=lambda x:re.sub(r'\s+','',x).replace('\\','')

def inspect(name,stage,basename,sdc):
    vo=stage/'impl/pnr'/(basename+'.vo');sdf=vo.with_suffix('.sdf');tr=vo.with_suffix('.tr')
    text=vo.read_text()
    needed={'u_pll_f/PLL_inst','u_pll_b/PLL_inst',PHY+'/dhcen_inst',PHY+'/clkdiv_inst'}
    cells={norm(m[2]):dict(kind=m[1],ports={p:norm(v) for p,v in re.findall(r'\.(\w+)\(([^()]*)\)',m[3])},line=text[:m.start()].count('\n')+1)
           for m in re.finditer(r'^(\w+)\s+(\\[^\s]+|\w+)\s*\(([^;]*?)\);',text,re.M|re.S) if norm(m[2]) in needed}
    params={norm(n):norm(v) for n,v in re.findall(r'^defparam\s+(.+?)\s*=\s*([^;]+);',text,re.M)}
    picked={n:dict(cells[n],parameters={p[len(n)+1:]:v for p,v in params.items() if p.startswith(n+'.')})
            for n in ['u_pll_f/PLL_inst','u_pll_b/PLL_inst',PHY+'/dhcen_inst',PHY+'/clkdiv_inst']}
    a,b,g,d=(picked[n] for n in ['u_pll_f/PLL_inst','u_pll_b/PLL_inst',PHY+'/dhcen_inst',PHY+'/clkdiv_inst'])
    assert a['ports']['CLKOUT0']=='clk48' and b['ports']['CLKIN']=='clk48'
    assert b['ports']['CLKOUT0']=='fclk_960m' and b['ports']['CLKOUT1']=='phy_clk'
    assert g['kind']=='DHCE' and g['ports']['CLKIN']=='fclk_960m'
    assert d['kind']=='CLKDIV' and d['ports']['HCLKIN']==g['ports']['CLKOUT']
    assert d['ports']['CLKOUT']==PHY+'/sclk' and d['parameters']['DIV_MODE']=='"8"'
    freq=lambda c,o:float(c['parameters']['FCLKIN'].strip('"'))*(int(c['parameters']['MDIV_SEL'])+int(c['parameters']['MDIV_FRAC_SEL'])/8)/int(c['parameters']['IDIV_SEL'])/int(c['parameters']['ODIV'+str(o)+'_SEL'])
    frequencies={'CLK_48M':freq(a,0),'PHY_CLKOUT':freq(b,1),'fclk_960M':freq(b,0),'sclk':freq(b,0)/8}
    assert frequencies=={'CLK_48M':48.,'PHY_CLKOUT':60.,'fclk_960M':960.,'sclk':120.},frequencies
    report=tr.read_text();clock_summary=report.split('\n2.2 Clock Summary\n',1)[1].split('\n2.3 Max Frequency Summary\n',1)[0]
    for clock in frequencies:assert re.search(r'\b'+re.escape(clock)+r'\b',clock_summary),clock
    wanted=expected_paths(vo,instance_prefix='');found={};timescale=None
    for line in sdf.open():
        match=re.search(r'\(TIMESCALE\s+([^)]*)\)',line)
        if match:timescale=match[1].strip()
        if 'INTERCONNECT' not in line or 'u_usb_softphy_top' not in line:continue
        match=re.search(r'INTERCONNECT (\S+) (\S+) \(([^)]+)\)',line.replace('\\/','/').replace('\\.','.'))
        if match and (match[1],match[2]) in wanted:
            key=(match[1],match[2]);assert key not in found
            found[key]=dict(wanted[key],source=key[0],target=key[1],route_ns=[float(x) for x in match[3].split(':')])
    assert timescale=='1 ns' and len(found)==44 and set(found)==set(wanted)
    return dict(board=name,files={str(p):sha(p) for p in [vo,sdf,tr,sdc]},clock_cells=picked,
                nominal_frequencies_mhz=frequencies,sta_clock_summary=clock_summary,
                usb_sdc_lines=[dict(line=i,text=line) for i,line in enumerate(sdc.read_text().splitlines(),1)
                               if any(c in line for c in frequencies)],
                gray_routes=list(found.values()),gray_route_max_ns=max(max(p['route_ns']) for p in found.values()),
                gray_routes_below_source_period=all(0<=v<1000/120 for p in found.values() for v in p['route_ns']))

if __name__=='__main__':
    n=ROOT/'tang/impl/console_neo_n56r21r2_resetqual_coupled';p=ROOT/'tang/impl/gpu_geometry_g22r0'
    data=[inspect('Neo',n,'console_neo',n/'source/tang/boards/neo/neo.sdc'),
          inspect('Pro Dock',p,'console_gpu_geometry_g22r0',p/'source/diagnostics/timing_reports.sdc')]
    result=dict(status='CLOCK_TOPOLOGY_AND_DECLARATIONS_CONSISTENT',hardware_access=False,
                tool_sha256=sha(Path(__file__)),fifo_endpoint_extractor_sha256=sha(ROOT/'tools/check_usb_phy_cdc_timing.py'),boards=data,
                limits=['No USB enumeration or analog measurement.',
                        '120 MHz nominal follows the actual divider, independent of the V_120 macro name.',
                        'Clock groups cut internal 60/120/960 crossings as in the original vendor SDC; no universal CDC proof follows.',
                        '44 SDF interconnect checks are wire-delay coverage, not setup/hold/MTBF/reset qualification.',
                        'Global R21r2 timing remains FAIL. No timing constraints were changed.'])
    out=HERE/'clock_audit.json';assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'sha256':sha(out),'boards':[{k:b[k] for k in ['board','nominal_frequencies_mhz','gray_route_max_ns','gray_routes_below_source_period']} for b in data]}))
