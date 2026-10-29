#!/usr/bin/env python3
"""Isolated geometry FPGA build from the qualified C37 snapshot; no shared IP regeneration."""
import argparse,hashlib,json,os,re,shutil,subprocess
from pathlib import Path
from build_gpu import resolve_constraints
from gowin_toolchain import IDE, environment
from board_contract import before_build, record_build
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'tang/impl/gpu_sdusb_c37'
TEMPLATE=ROOT/'tang/impl/gpu_sdusb_c28'
def nonplacement_constraints(text):
 # INS_LOC is consumed by P&R, not synthesis. All pin/bank/clock records
 # must remain byte-for-byte identical after whitespace/comment stripping.
 clean='\n'.join(s.split('//',1)[0] for s in text.splitlines())
 statements=[' '.join(part.split()) for part in clean.split(';')]
 return [s for s in statements if s and not s.startswith('INS_LOC ')]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--name',required=True)
 p.add_argument('--reuse-synthesis',type=Path,help='Route an identical, verified geometry netlist without resynthesis')
 p.add_argument('--placement-reference',type=Path,help='Gowin incremental placement hint; never changes the netlist or SDC')
 p.add_argument('--timing-paths',type=int,default=2000,help='Number of reported paths; clocks and exceptions stay unchanged')
 p.add_argument('--place-option',type=int,choices=range(5),default=3)
 p.add_argument('--route-option',type=int,choices=range(3),default=2)
 p.add_argument('--replicate-resources',type=int,choices=(0,1),default=0,help='Allow physical replication of high-fanout logic')
 p.add_argument('--candidate',action='store_true',help='Explicit Pro Dock candidate; dual-board local checks required, hardware validation pending')
 a=p.parse_args()
 if not re.fullmatch('[a-zA-Z0-9_]+',a.name):p.error('Invalid build name')
 if not 200<=a.timing_paths<=5000:p.error('timing-paths must be 200..5000')
 contract=before_build('prodock',candidate=a.candidate)
 stage=ROOT/'tang/impl'/a.name;stage.mkdir(exist_ok=False)
 record_build(stage,contract)
 shutil.copytree(BASE/'source',stage/'source');shutil.copytree(BASE/'rtl',stage/'rtl')
 extra=['tang/rtl/video/gpu_geometry.v','tang/rtl/video/gpu_geom_div.v','tang/rtl/video/video_bus_stage.v']
 changed=['tang/rtl/console_top.v','tang/rtl/board/ddr_gpu_arb.v','tang/rtl/usb/usb_msc_port.v','tang/rtl/video/gpu_line_reader.v','tang/rtl/video/gpu_accel.v','tang/rtl/video/blitter.v','tang/rtl/video/gpu_blit_dma.v',*extra,'tang/rtl/video/gpu_perspective.v','tang/rtl/video/gpu_v1.v','tang/rtl/video/gpu_texture_cache.v']
 # Shared RTL must follow the working tree on both boards. Keeping these
 # files frozen at C37 silently omitted later scanout, bus and raster fixes.
 changed += ['tang/rtl/board/ae350_soc.v','tang/rtl/board/ahb_exts_bridge.v',
             'tang/rtl/video/gpu_scanout.v','tang/rtl/video/gpu_rgb_reader.v',
             'tang/rtl/video/gpu_raster.v','tang/rtl/video/gpu_copy565.v']
 for rel in changed:shutil.copy2(ROOT/rel,stage/'source'/rel)
 # The registered peripheral stage replaces the two combinational HREADY
 # LUTs pinned by C37. Their synthesized names/functions no longer exist.
 # Remove only these obsolete placement anchors; preserve all pins and SDC.
 constraint_source=stage/'source/tang/constr/gpu.cst'
 constraint_text=constraint_source.read_text()
 removed_placements=[]
 for cell in ('vid_hready_s0','vid_hready_s2','u_accel/u_raster/texture_row_24_s4','u_accel/u_raster/u_triangle/state_6_s0','u_usb_fifo/ep1_reset_s2'):
  pattern=r'^INS_LOC "'+cell+r'" [^\n]+;\s*$'
  matches=re.findall(pattern,constraint_text,re.M)
  if len(matches)!=1:raise RuntimeError('Expected one baseline placement: '+cell)
  removed_placements+=matches
  constraint_text=re.sub(pattern,'// G3D1: release obsolete HREADY / relocated raster placement.',constraint_text,flags=re.M)
 # The one-hot EXTS bridge merges HREADY with IDLE. Replace only its old
 # binary-machine anchors, keeping the accepted hard-macro neighborhood.
 for cell in ('m_hready_s0','st_0_s0','st_1_s5','n47_s2'):
  pattern=r'^INS_LOC "u_soc/u_bridge/'+cell+r'" [^\n]+;\s*$'
  matches=re.findall(pattern,constraint_text,re.M)
  if len(matches)!=1:raise RuntimeError('Expected one old bridge placement: '+cell)
  removed_placements+=matches
  constraint_text=re.sub(pattern,'// Dual board: replaced binary EXTS bridge anchor.',constraint_text,flags=re.M)
 constraint_text=constraint_text.replace('// @driver module=ahb_exts_bridge instance=m_hready_s0 pin=D','// Dual board: HREADY is the one-hot IDLE register.')
 constraint_text+='''
// One-hot EXTS control adjacent to the AE350 hard macro.
INS_LOC "u_soc/u_bridge/st_0_s1" R4C150[0][A];
INS_LOC "u_soc/u_bridge/st_1_s0" R4C150[1][A];
// @driver module=ahb_exts_bridge instance=st_0_s1 pin=CE
INS_LOC "u_soc/u_bridge/st_0_s3" R4C150[0][B];
// @driver module=ahb_exts_bridge instance=st_1_s0 pin=D
INS_LOC "u_soc/u_bridge/n50_s0" R4C150[1][B];
'''
 # Retain the qualified HS receiver neighborhood, without freezing the
 # unrelated GPU placement. A whole-design G22 hint no longer routes the
 # changed geometry netlist; the encrypted PHY itself is unchanged.
 usb_placements=ROOT/'tang/constr/prodock_softusb_placement.cst'
 if usb_placements.exists():
  supplemental=usb_placements.read_text()
  for cell in re.findall(r'^INS_LOC "([^"]+)"',supplemental,re.M):
   constraint_text=re.sub(r'^INS_LOC "'+re.escape(cell)+r'" [^\n]+;\s*$',
                          '// HS receiver anchor supplied below.',constraint_text,flags=re.M)
  constraint_text+='\n'+supplemental
  shutil.copy2(usb_placements,stage/'source/tang/constr/prodock_softusb_placement.cst')
 constraint_source.write_text(constraint_text)
 tcl=(TEMPLATE/'build.tcl').read_text().replace(str(TEMPLATE),str(stage)).replace('console_gpu_sdusb_c28','console_'+a.name)
 for option,value in [('place_option',a.place_option),('route_option',a.route_option),('replicate_resources',a.replicate_resources)]:
  tcl,count=re.subn(r'(?m)^set_option -'+option+r' \d+$',f'set_option -{option} {value}',tcl)
  if count!=1:raise RuntimeError('Expected one placement setting: '+option)
 tcl=tcl.replace('add_file {'+str(stage/'source/tang/rtl/video/gpu_v1.v')+'}', 'add_file {'+str(stage/'source/tang/rtl/video/gpu_v1.v')+'}\n'+'\n'.join('add_file {'+str(stage/'source'/rel)+'}' for rel in extra))
 for path in re.findall(r'^add_file \{(.*?)\}',tcl,re.M):
  if path.endswith('constraints_resolved.cst'):continue
  if not Path(path).is_file():raise RuntimeError('Missing baseline dependency: '+path)
 shutil.copy2(BASE/'constraints_resolved.cst',stage/'constraints_resolved.cst')
 report_sdc=stage/'source/diagnostics/timing_reports.sdc'
 report_sdc.write_text(re.sub(r'(?<=-max_paths )200\b',str(a.timing_paths),report_sdc.read_text()))
 manifest={str(f.relative_to(stage/'source')):hashlib.sha256(f.read_bytes()).hexdigest() for f in (stage/'source').rglob('*') if f.is_file()}
 provenance=dict(baseline=str(BASE),ide=str(IDE),changes=changed,clocks_changed=False,
                 usb_datapath_changed=any((ROOT/rel).read_bytes() != (BASE/'source'/rel).read_bytes()
                                         for rel in changed if rel.startswith('tang/rtl/usb/')),
                 usb_endpoint_reset_decode_registered=True,peripheral_bus_staged=True,timing_paths=a.timing_paths,removed_placements=removed_placements,place_option=a.place_option,route_option=a.route_option,replicate_resources=a.replicate_resources)
 if a.reuse_synthesis:
  parent=a.reuse_synthesis.resolve(strict=True)
  old_manifest=json.loads((parent/'sources.json').read_text())
  differences={s for s in manifest.keys()|old_manifest.keys() if manifest.get(s)!=old_manifest.get(s)}
  if differences-{'tang/constr/gpu.cst'}:raise RuntimeError('Synthesis reuse requires identical frozen HDL, data and timing sources')
  if differences:
   old_cst=(parent/'source/tang/constr/gpu.cst').read_text()
   if nonplacement_constraints(old_cst)!=nonplacement_constraints(constraint_text):
    raise RuntimeError('Synthesis reuse forbids changes to pins, banks or clocks')
   provenance['placement_constraints_changed']=dict(parent_sha256=old_manifest['tang/constr/gpu.cst'],sha256=manifest['tang/constr/gpu.cst'])
  for rel,digest in old_manifest.items():
   if hashlib.sha256((parent/'source'/rel).read_bytes()).hexdigest()!=digest:raise RuntimeError('Altered parent snapshot: '+rel)
  original=parent/f'impl/gwsynthesis/console_{parent.name}.vg'
  net=stage/f'impl/gwsynthesis/console_{stage.name}.vg';net.parent.mkdir(parents=True)
  shutil.copyfile(original,net)
  provenance['synthesis_reused']=dict(stage=str(parent),sha256=hashlib.sha256(net.read_bytes()).hexdigest())
  settings=[s for s in tcl.splitlines() if s.startswith(('set_device ','set_option '))]
  # A netlist-only project is essential: including RTL makes Gowin resynthesize.
  tcl='\n'.join(settings)+f'\nadd_file {{{net}}}\nadd_file {{{stage/"constraints_resolved.cst"}}}\nadd_file {{{stage/"source/diagnostics/timing_reports.sdc"}}}\nrun pnr\n'
  resolve_constraints(net,stage/'source/tang/constr/gpu.cst',stage/'constraints_resolved.cst')
 if a.placement_reference:
  source=a.placement_reference.resolve(strict=True);target=stage/'source/diagnostics/geometry_reference.p'
  if source.suffix!='.p':raise RuntimeError('Expected a Gowin .p placement file')
  shutil.copyfile(source,target);digest=hashlib.sha256(target.read_bytes()).hexdigest()
  manifest['diagnostics/geometry_reference.p']=digest
  provenance['placement_reference']=dict(path=str(source),sha256=digest)
  tcl=tcl.replace('run pnr',f'set_option -inc_place {{{target}}}\nrun pnr')
 (stage/'build.tcl').write_text(tcl)
 shutil.copyfile(Path(__file__),stage/'build_driver.py')
 (stage/'sources.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (stage/'geometry_build.json').write_text(json.dumps(provenance,indent=2)+'\n')
 env=environment()
 print(stage,flush=True)
 with (stage/'build.log').open('w') as log:r=subprocess.run([str(IDE/'bin/gw_sh'),'build.tcl'],cwd=stage,env=env,stdout=log,stderr=log)
 if r.returncode or re.search(r'^ERROR', (stage/'build.log').read_text(),re.M):raise RuntimeError('Gowin build failed: '+str(stage/'build.log'))
 if a.reuse_synthesis and ('Running GowinSynthesis' in (stage/'build.log').read_text() or hashlib.sha256(net.read_bytes()).hexdigest()!=provenance['synthesis_reused']['sha256']):raise RuntimeError('Synthesis reuse was not preserved')
 print('Gowin finished; timing and resource reports still require review',flush=True)
if __name__=='__main__':main()
