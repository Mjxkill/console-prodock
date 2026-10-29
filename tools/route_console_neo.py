#!/usr/bin/env python3
"""Route a frozen Neo netlist with new physical/timing constraints only."""
import argparse,hashlib,json,os,re,shutil,subprocess
from pathlib import Path
from build_console_neo import ROOT,IDE
from gowin_toolchain import environment
from board_contract import before_build, record_build
from neo.gpu_debug import local_reset_constraints
from neo.gpu_reset import queue_reset_local, control_local_constraints
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--from-build',type=Path,required=True);p.add_argument('--name',required=True)
p.add_argument('--place',type=int,choices=(0,1,2,3,4))
p.add_argument('--route',type=int,choices=(0,1,2))
p.add_argument('--replicate',type=int,choices=(0,1))
p.add_argument('--ide',type=Path,default=IDE,help='Explicit Gowin installation for a same-netlist compiler comparison')
p.add_argument('--system-freetype',action='store_true',help='Use system FreeType with the newer IDE Qt libraries')
p.add_argument('--placement-cst',type=Path,help='Alternative INS_LOC records; all other constraints must match')
p.add_argument('--incremental-from',type=Path,help='Completed same-netlist route whose frozen placement/routing may be reused')
p.add_argument('--incremental-mode',choices=('place','pnr'),default='place')
p.add_argument('--timing-closure-reference',type=Path,
               help='Renormalize an existing Neo timing experiment from measured source latencies; full audit still required')
p.add_argument('--hdmi-clock-index',type=int,choices=(4,8,12),
               help='Characterized HDMI clock resource for the frozen timing experiment; USB clocks unchanged')
p.add_argument('--hdmi-clock-auto',action='store_true',
               help='Let P&R allocate the HDMI DCE clock resource; keep all other clocks fixed')
p.add_argument('--hdmi-reset-placement',choices=('pg8-c181','pg9-c181','sg0-c150','sg0-c160'),
               help='Characterized DCE site with three adjacent serializer reset drivers')
p.add_argument('--hdmi-reset-column',type=int,choices=(150,160),
               help='Move an already-frozen SG[0] HDMI reset placement between characterized columns')
p.add_argument('--cdc-clock-origins-zero',action='store_true',
               help='Use characterized local generated-clock origins and retain literal 8 ns CDC bounds')
p.add_argument('--hdmi-focused-reports',action='store_true',
               help='Keep unfiltered global reports and append all serializer reset edges explicitly')
p.add_argument('--ddr-phy-reference-timing',type=Path,
               help='DDR400 reference route proving fast-clock fanout stays inside the vendor PHY')
p.add_argument('--gpu-reset-local',action='store_true',
               help='N34 diagnostic only: request local routing for the four observed GPU reset copies')
p.add_argument('--gpu-queue-reset-local',action='store_true',
               help='N35 diagnostic only: request local routing for the command-queue reset copy')
p.add_argument('--gpu-control-local',action='store_true',
               help='N38 diagnostic only: keep four mapped non-clock GPU controls off LW')
p.add_argument('--gpu-control-primary',action='store_true',
               help='N38 diagnostic only: explicitly request PRIMARY for four non-clock GPU controls')
p.add_argument('--gpu-wide-controls-local',action='store_true',
               help='Same-netlist experiment: constrain locally driven wide GPU CE/reset nets off LW')
a=p.parse_args()
if sum((a.hdmi_clock_auto,a.hdmi_clock_index is not None,a.hdmi_reset_placement is not None,a.hdmi_reset_column is not None))>1:p.error('Choose one HDMI clock allocation')
if a.cdc_clock_origins_zero and a.timing_closure_reference:p.error('Choose one CDC normalization method')
ide=a.ide.resolve(strict=True)
env=environment(ide,system_freetype=a.system_freetype)
if not (ide/'bin/gw_sh').is_file():p.error('Gowin installation missing')
if sum((a.gpu_reset_local,a.gpu_queue_reset_local,a.gpu_control_local,a.gpu_control_primary,a.gpu_wide_controls_local))>1:p.error('Choose one control routing experiment')
gpu_controls=a.gpu_control_local or a.gpu_control_primary
if not re.fullmatch('[a-zA-Z0-9_]+',a.name):p.error('Invalid build name')
parent=a.from_build.resolve(strict=True);out=ROOT/'tang/impl'/a.name
manifest=json.loads((parent/'sources.json').read_text())
for rel,digest in manifest.items():
 if hashlib.sha256((parent/'source'/rel).read_bytes()).hexdigest()!=digest:raise ValueError('Changed parent '+rel)
if 'GowinSynthesis finish' not in (parent/'build.log').read_text():
 raise ValueError('Parent synthesis is incomplete')
if not (parent/'impl/gwsynthesis/console_neo.vg').is_file():
 raise FileNotFoundError('Parent synthesis netlist is missing')
# Validate this narrowly scoped non-placement experiment before creating output.
reset_nets=[];reset_cst=None;wide_control_record=None
if a.gpu_wide_controls_local:
 from neo.gpu_control_routes import constrain
 if not (parent/'source/tang/boards/neo/gpu_stream_payload.json').is_file():
  raise ValueError('Wide-control experiment requires the N40 payload profile')
 reset_cst,wide_control_record=constrain(
     (a.placement_cst or parent/'source/tang/boards/neo/neo.cst').read_text(),
     (parent/'impl/gwsynthesis/console_neo.vg').read_text())
if a.gpu_reset_local or a.gpu_queue_reset_local or gpu_controls:
 if not (parent/'source/tang/boards/neo/gpu_debug.json').is_file():
  raise ValueError('GPU reset experiment requires the observation-instrumented build')
 base_cst=a.placement_cst or parent/'source/tang/boards/neo/neo.cst'
 if a.gpu_queue_reset_local and not (parent/'source/tang/boards/neo/gpu_reset.json').is_file():
  raise ValueError('Queue reset experiment requires N35 reset profile')
 if gpu_controls and not (parent/'source/tang/boards/neo/gpu_shader_phase.json').is_file():
  raise ValueError('Control routing experiment requires the N38 shader phase profile')
 operation=control_local_constraints if gpu_controls else queue_reset_local if a.gpu_queue_reset_local else local_reset_constraints
 reset_cst,reset_nets=operation(base_cst.read_text(),
     (parent/'impl/gwsynthesis/console_neo.vg').read_text(),**({'primary':a.gpu_control_primary} if gpu_controls else {}))
contract=before_build('neo',candidate=True)
out.mkdir(exist_ok=False)
record_build(out,contract)
shutil.copytree(parent/'source',out/'source')
for name in ['neo.cst','neo.sdc']:
 # A physical experiment must keep the parent's exact pins and clocks,
 # even if another build has since changed the working-tree profile.
 original=parent/'source/tang/boards/neo'/name
 if name=='neo.cst' and a.placement_cst:
  def fixed_constraints(path):
   clean='\n'.join(line.split('//',1)[0] for line in path.read_text().splitlines())
   statements=[' '.join(part.split()) for part in clean.split(';')]
   return [s for s in statements if s and not s.startswith('INS_LOC ')]
  if fixed_constraints(original)!=fixed_constraints(a.placement_cst):
   raise ValueError('Alternative CST changes pins, banks or other non-placement constraints')
  original=a.placement_cst.resolve(strict=True)
 shutil.copy2(original,out/'source/tang/boards/neo'/name)
 if name=='neo.cst' and reset_cst is not None:
  (out/'source/tang/boards/neo'/name).write_text(reset_cst)
if (out/'source/tang/boards/neo/system_reset.json').is_file():
 from neo.system_reset import constrain as constrain_system_reset
 constrain_system_reset(out/'source',parent/'impl/gwsynthesis/console_neo.vg')
if a.timing_closure_reference:
 from neo.timing_closure import refresh
 refresh(out/'source',a.timing_closure_reference)
if a.hdmi_clock_index is not None:
 from neo.timing_closure import select_hdmi_clock
 select_hdmi_clock(out/'source',a.hdmi_clock_index)
if a.hdmi_clock_auto:
 from neo.timing_closure import auto_hdmi_clock
 auto_hdmi_clock(out/'source')
if a.hdmi_reset_placement:
 from neo.timing_closure import select_hdmi_placement
 select_hdmi_placement(out/'source',a.hdmi_reset_placement)
if a.hdmi_reset_column is not None:
    from neo.timing_closure import move_hdmi_resets
    move_hdmi_resets(out/'source',a.hdmi_reset_column)
if a.cdc_clock_origins_zero:
 from neo.timing_closure import zero_clock_origins
 zero_clock_origins(out/'source')
if a.hdmi_focused_reports:
 from neo.timing_closure import focused_hdmi_reports
 focused_hdmi_reports(out/'source')
if a.ddr_phy_reference_timing:
 from neo.ddr_phy_timing import freeze as freeze_phy_timing
 freeze_phy_timing(out/'source',a.ddr_phy_reference_timing)
for original in (parent/'source').rglob('*.hex'):
 if original.name=='font8x16.hex': target=out/'rtl/video/font8x16.hex'
 elif original.name=='usb_hid_host_rom.hex': target=out/'rtl/usbhost/usb_hid_host_rom.hex'
 else: continue
 target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(original,target)
 if original.name=='font8x16.hex':shutil.copy2(original,out/'font8x16.hex')
net=out/'console_neo.vg';shutil.copy2(parent/'impl/gwsynthesis/console_neo.vg',net)
incremental=None
if a.incremental_from:
 from neo.incremental import freeze as freeze_incremental
 incremental=freeze_incremental(a.incremental_from,out,a.incremental_mode)
(out/'sources.json').write_text(json.dumps({str(f.relative_to(out/'source')):hashlib.sha256(f.read_bytes()).hexdigest() for f in (out/'source').rglob('*') if f.is_file()},indent=2)+'\n')
(out/'route.json').write_text(json.dumps({'parent':str(parent),'netlist_sha256':hashlib.sha256(net.read_bytes()).hexdigest(),
 'incremental':incremental,
 'ide':str(ide),'system_freetype':a.system_freetype or ide==IDE.resolve(),
 'wide_gpu_controls_local':a.gpu_wide_controls_local,
 'requested_local_gpu_reset_nets':[] if gpu_controls else reset_nets,
 'requested_local_gpu_control_nets':reset_nets if a.gpu_control_local else [],
 'requested_primary_gpu_control_nets':reset_nets if a.gpu_control_primary else []},indent=2)+'\n')
if wide_control_record is not None:
 (out/'wide_gpu_controls.json').write_text(json.dumps(wide_control_record,indent=2)+'\n')
settings=[l for l in (parent/'build.tcl').read_text().splitlines() if l.startswith(('set_device ','set_option '))]
if any(l.startswith(('set_option -inc_place ','set_option -inc_pnr ')) for l in settings):
 raise ValueError('Parent contains untracked incremental options')
if incremental:
 settings.append('set_option -inc_'+incremental['mode']+' {'+str(out/incremental['cache'])+'}')
for key,value in [('place_option',a.place),('route_option',a.route),('replicate_resources',a.replicate)]:
 if value is not None:
  settings=[l for l in settings if not l.startswith('set_option -'+key+' ')]
  settings.append(f'set_option -{key} {value}')
settings += [f'add_file {{{net}}}',f'add_file {{{out}/source/tang/boards/neo/neo.cst}}',f'add_file {{{out}/source/tang/boards/neo/neo.sdc}}','run pnr']
(out/'build.tcl').write_text('\n'.join(settings)+'\n')
with (out/'build.log').open('w') as log:
 r=subprocess.run([str(ide/'bin/gw_sh'),'build.tcl'],cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT)
if r.returncode or re.search(r'^ERROR',(out/'build.log').read_text(),re.M):raise RuntimeError(out/'build.log')
print(out)
