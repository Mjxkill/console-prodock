#!/usr/bin/env python3
"""Summarize stable routed evidence, with global FAIL separate from witness coverage."""
import json
from pathlib import Path
import re
from collections import Counter
import audit_timing as a
p=a.p
HERE=Path(__file__).resolve().parent

def main():
 paths=[p.OUT/'route_result.json',HERE/'postroute_structure_01/result.json',HERE/'postroute_timing_01/result.json',
  p.OUT/'impl/pnr/console_neo.vo',p.OUT/'impl/pnr/console_neo.tr',p.OUT/'impl/pnr/console_neo.fs',Path(__file__)]
 hashes={str(x):p.sha(x) for x in paths};route=json.loads(paths[0].read_text());structure=json.loads(paths[1].read_text());timing=json.loads(paths[2].read_text())
 cells,params=a.routed.original.cells(paths[3].read_text());text=paths[4].read_text()
 negative=[];clock_pairs=Counter();pin_minima=[]
 for cmd,body in a.sections(text):
  if a.TARGET.fullmatch(cmd):
   for row in a.paths(body):clock_pairs[(row['launch_clock'],row['latch_clock'])]+=1
  elif re.fullmatch(r'report_timing -(setup|hold|recovery|removal) -max_paths \d+ -max_common_paths \d+',cmd):
   mode=cmd.split()[1][1:]
   negative.extend(dict(analysis=mode,**row) for row in a.paths(body) if row['valid'] and row['slack_ns']<0)
 for group in ('witness','hrdata'):
  for mode in ('setup','hold'):
   for pin in ('D','CE','RESET'):
    selected=[r for r in timing['coverage'] if r['analysis']==mode and r['endpoint'].endswith('/'+pin) and ('utw_observer' in r['endpoint'])==(group=='witness')]
    worst=min(selected,key=lambda r:r['minimum_slack_ns'])
    pin_minima.append(dict(group=group,analysis=mode,pin=pin,endpoints=len(selected),worst_slack_ns=worst['minimum_slack_ns'],worst_endpoint=worst['endpoint']))
 facts={n:dict(type=cells[n][0],pins=cells[n][1],parameters={k:v for k,v in params.items() if k.startswith(n+'.')}) for n in [
  'u_soc/vid_hrstn_r_s0','u_accel/u_v1/u_pixels/u_capture/n77_s2','u_usb_idle_trace/n6_s1',
  'u_usb_idle_trace/hreset_s0','u_usb_idle_trace/utw_observer/utw_cell_105','u_usb_idle_trace/hr_2_s0','u_usb_idle_trace/uh_1_s0',
  'u_accel/u_v1/u_pixels/u_capture/after_event_8_s1','u_accel/u_v1/u_pixels/u_capture/beat_0_s0']}
 report=dict(schema='neo-utw1-r22r1-postroute-summary-v1',candidate=True,hardware_access=False,hardware_qualified=False,
  route_status=route['status'],bitstream_sha256=route['bitstream_sha256'],netlist_sha256=route['netlist_sha256'],
  structure_passed=structure['structure']['passed'],helper_ff=structure['structure']['helper_ff'],
  target_requests_resolved=timing['all_targets_resolved'],target_slacks_nonnegative=timing['target_report_slacks_nonnegative'],
  target_status_counts=timing['status_counts'],target_minima=pin_minima,
  target_clock_pairs=[dict(launch=x,latch=y,paths=n) for (x,y),n in clock_pairs.items()],
  global_timing_qualification='FAIL',global_summary=timing['global_summary'],global_reports=timing['global_reports'],negative_paths=negative,
  global_summary_caveat='Gowin labels 9 endpoints as Setup Violated; detailed reports show one setup and eight recovery destinations. Preserve both outputs without treating the summary label as nine ordinary setup paths.',
  reset_and_clock_netlist_facts=facts,
  reset_relationship='Common upstream AE350 HRESETN is sampled by vid_hrstn_r on vid_hclk. GPU local capture takes inverse vid_hrstn as asynchronous CLEAR under gpu_clk. UTNA uses rst_usb OR !vid_hrstn for reset synchronizers and derives hreset from hr[2]/uh[1]; UTW1/hrdata use hreset synchronously under vid_hclk.',
  clock_warnings={'clk_d':'PR1014 present in both R19 and this build; input-buffer output serves reference PLLs and init/reset logic.',
   'ae350_tck_d':'PR1014 present in both R19 and this build; debugger clock branch. No causality established.'},
  clock_caveat='STA clock names/rates are the constraint model, not measured frequency or physical lock evidence.',
  not_individually_targeted=['PHY-side snapshot and send_index','FIFO write/CDC/synchronizer and flag paths',
   'Original bank storage/validity, receive_index, snapshot_count, busy, read_pending','Asynchronous reset release of UTNA synchronizers',
   'AHB/JTAG upstream and external return route beyond hrdata'],
  diagnostic_recommendation='Suitable to consider for the reviewed bounded diagnostic with CPU parked and no GPU/DDR workload, followed by exact R19 restoration. This is not global timing closure or board qualification.',
  interpretation_bounds=['Version zero remains FAIL even with a coherent capture.',
   'Witness=1/bank=0 places disagreement after sampled boundary only conditional on witness/read-path validity.',
   'Witness=0/bank=0 cannot distinguish upstream zero from witness failure; does not prove a FIFO defect.',
   'Shared reset origin is real; different branches do not imply independent reset correctness.',
   'No listed negative path ends in UTNA/UTW1; this does not prove CDC/metastability correctness or external clock/reset behavior.'],
  inputs=hashes)
 p.require(all(p.sha(Path(x))==v for x,v in hashes.items()),'route inputs changed during summary')
 p.save(HERE/'postroute_summary.json',report)
 print(json.dumps(dict(path=str(HERE/'postroute_summary.json'),sha256=p.sha(HERE/'postroute_summary.json'),negative_paths=len(negative),global_qualification='FAIL',witness_coverage=True)))
if __name__=='__main__':main()
