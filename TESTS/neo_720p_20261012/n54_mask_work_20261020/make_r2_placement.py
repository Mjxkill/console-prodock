#!/usr/bin/env python3
"""Placement-only N54r2 proposal from measured N54r1 paths; never a timing waiver."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'optimizer'))
from reports import fixed_constraints

work = Path(__file__).parent
reference = ROOT/'tang/impl/console_neo_n54r1'
analysis = json.loads((work/'timing_analysis_r1.json').read_text())
base_path = reference/'source/tang/boards/neo/neo.cst'
base = base_path.read_text()
changes = {
    # Restore the source toward its original right-side consumers; keep the
    # two GPU receivers closer instead of pulling this shared source left.
    'u_soc/vid_hrstn_r_s0': 'R[50:65]C[120:135]',
    'u_accel/engine_resetn_1_s0': 'R[30:50]C[90:110]',
    'u_accel/engine_resetn_3_s0': 'R[60:80]C[90:110]',
    # First diagnostic CDC stages can sit near their left-side sources.
    'diag_board_meta_1_s0': 'R[85:105]C[15:35]',
    'diag_board_meta_2_s0': 'R[85:105]C[15:35]',
    # Avoid the measured round trip C42 -> C133 -> C44 in the blitter flags.
    'u_accel/gpu_debug_state_102_s0': 'R[45:65]C[45:65]',
    'u_accel/n563_s0': 'R[45:65]C[60:85]',
    'u_accel/busy_sync_0_s0': 'R[45:65]C[60:85]',
    'u_gpu_debug/held_55_s0': 'R[20:40]C[70:90]',
    # Shorten the measured scan-queue -> issue -> stage detour.
    'u_scan_queue/push_s2': 'R[78:86]C[136:150]',
    'u_gpu/u_reader/u_tiles/issue_s0': 'R[78:86]C[136:150]',
    'u_gpu/u_reader/u_tiles/stage_s0': 'R[78:86]C[136:150]',
}
ddr = 'u_soc/g_ddr.u_ddr/u_ip/gw3_top/u_ddr_phy_top/'
changes[ddr+'ddr_rsti_reg_2_s0'] = 'R[99:104]C[4:8]'
changes[ddr+'u_ddr_phy_wds/u_ddr_phy_reset_gen/if_wrreset_Z_s'] = 'R[97:103]C[5:10]'
paths = [p for p in analysis['paths'] if p['analysis']=='recovery' and p['slack_ns']<0
         and p['source']==ddr+'ddr_rsti_reg_2_s0']
sinks = sorted({p['destination'] for p in paths})
if len(sinks)!=80 or any(not re.fullmatch(re.escape(ddr)+
        r'u_ddr_phy_wds/fifo_ctrl_gen\[[0-3]\]\.fifo_ctrl/\w+',name) for name in sinks):
    raise ValueError('Unexpected DDR reset sink set')
changes.update({name:'R[95:104]C[5:18]' for name in sinks})

# Every new name is observed in the actual completed route, with no automatic
# replicas. The vendor DDR leaves are expanded by P&R, not exposed in the VG.
vo = (reference/'impl/pnr/console_neo.vo').read_text()
cells = {}
for m in re.finditer(r'^\s*(\w+)\s+(\\\S+|\w+)\s*\(([^;]+)\);',vo,re.M):
    cells[m[2].removeprefix('\\')] = dict(kind=m[1],ports=m[3])
if any(name not in cells or not cells[name]['kind'].startswith(('DFF','LUT'))
       for name in changes):
    raise ValueError('Expected only observed LUT/register cells')
candidate = base
replaced = []
for name,region in changes.items():
    pattern = r'^INS_LOC "'+re.escape(name)+r'" [^;]+;\s*$'
    count = len(re.findall(pattern,candidate,re.M))
    line = f'INS_LOC "{name}" {region};'
    if count>1:
        raise ValueError('Duplicate anchor: '+name)
    if count:
        candidate = re.sub(pattern,lambda m:line,candidate,flags=re.M)
        replaced.append(name)
    else:
        candidate += line+'\n'
if sorted(replaced)!=sorted([
        'u_soc/vid_hrstn_r_s0','u_accel/engine_resetn_1_s0','u_accel/engine_resetn_3_s0']):
    raise ValueError('Unexpected existing anchor replacement')
if fixed_constraints(candidate)!=fixed_constraints(base):
    raise ValueError('Non-placement constraints changed')
out = work/'n54r2.cst'
with out.open('x') as stream:
    stream.write(candidate)
sha = lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record = dict(reference=str(reference),base_cst_sha256=sha(base_path),
              candidate_cst_sha256=sha(out),reference_netlist_sha256=sha(reference/'console_neo.vg'),
              timing_sha256=sha(reference/'impl/pnr/console_neo.tr'),
              replaced=replaced,anchors={k:dict(region=v,kind=cells[k]['kind']) for k,v in changes.items()},
              ddr_logic_changed=False,ddr_clocks_changed=False,
              limits='Measured placement hypothesis; the complete unchanged netlist and SDC must be rerouted and qualified.')
out.with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n')
print(f'{out}: {len(changes)} anchors, including {len(sinks)} DDR PHY FIFO reset receivers')
