#!/usr/bin/env python3
"""Read-only CPU/JTAG/PLL/reset comparison R19 vs R21r1; no hardware."""
import json,re
from pathlib import Path
import audit_postroute as a
H='u_soc/u_ae350/u_RiscV_AE350_SOC/u_AE350_SOC'
P='u_pll_ae350/u_pll/PLL_inst'
SELECT={H+'/'+p for p in ['DBG_TCK','TMS_IN','TDI_IN','CORE_CLK','AHB_CLK','APB_CLK','RTC_CLK','DDR_CLK','POR_N','HW_RSTN']}
SELECT|={P+'/'+p for p in ['CLKIN','RESET','RESET_I','RESET_O','ENCLK0','ENCLK1','ENCLK4']}
SELECT|={'ae350_tdo_obuf/I','u_soc/init_sync_0_s0/D','u_soc/init_sync_1_s0/D','u_soc/init_sync_0_s0/CLK','u_soc/init_sync_1_s0/CLK',
 'u_soc/init_sync_0_s0/CLEAR','u_soc/init_sync_1_s0/CLEAR','ae350_rst_sync_0_s0/CLK','ae350_rst_sync_1_s0/CLK'}

def run(build):
 vo=build/'impl/pnr/console_neo.vo';sdf=build/'impl/pnr/console_neo.sdf';rpt=build/'impl/pnr/console_neo.rpt.txt';tr=build/'impl/pnr/console_neo.tr'
 c,p=a.cells(vo);incoming,cq,clocks,setup,counts=a.parse_sdf(sdf.read_text())
 arcs={n:[dict(source=s,delay_by_corner_ns=d) for s,d in incoming.get(n,[])] for n in sorted(SELECT)}
 part=tr.read_text();neg=[]
 for line in part.splitlines():
  if re.match(r'^\s*\d+\s+-\d+\.\d+\s+',line) and any(k in line for k in ['u_pll_ae350','u_soc/init_sync','ae350_rst_sync','u_reset_trial','u_ae350/u_RiscV']):neg.append(line.strip())
 return dict(input_sha256={str(x):a.b.sha(x) for x in [vo,sdf,rpt,tr]},cells={n:v for n,v in c.items() if n in [H,P] or n.startswith(('u_pll_ae350/','ae350_rst_sync','u_soc/init_sync','u_reset_trial/','ae350_t'))},
  parameters={n:v for n,v in p.items() if n.startswith((H+'.',P+'.','u_pll_ae350/','ae350_rst_sync','u_soc/init_sync','u_reset_trial/','ae350_t'))},
  global_clock_routes=a.global_clock_routes(rpt.read_text()),sdf_arcs=arcs,negative_sta_rows=neg,
  missing_sdf_endpoints=[n for n,v in arcs.items() if not v],gao_cell_count=sum(n.startswith(('u_la0','u_icon','u_gw_jtag')) for n in c))

def main():
 out=a.b.HERE/'cpu_route_compare_01';assert not out.exists()
 before,after=run(a.b.PARENT),run(a.fmt.OUT)
 assert before['cells']==after['cells']
 assert before['parameters']==after['parameters']
 changes=[]
 for endpoint in sorted(SELECT):
  x,y=before['sdf_arcs'][endpoint],after['sdf_arcs'][endpoint]
  changes.append(dict(endpoint=endpoint,before=x,after=y))
 r=dict(hardware_access=False,logic_equal=True,parameters_equal=True,build_before=str(a.b.PARENT),build_after=str(a.fmt.OUT),before=before,after=after,
   comparison=changes,limits=['Missing SDF path is unavailable, not zero delay.','No on-board clock frequency/reset state measurement.','Configured FPGA DONE does not establish hart or DMI readiness.'])
 out.mkdir();a.b.save(out/'result.json',r)
 print(json.dumps(dict(logic_equal=True,parameters_equal=True,arcs=changes,old_negative=before['negative_sta_rows'],new_negative=after['negative_sta_rows']),indent=2))
if __name__=='__main__':main()
