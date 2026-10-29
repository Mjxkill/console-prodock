#!/usr/bin/env python3
"""Qualify a frozen Neo build: complete routing, clocks, timing and hashes."""
import argparse,json,re
from pathlib import Path
from check_geometry_timing import inspect,sha
from check_gpu_copy_synthesis import audit as audit_copy
from check_gpu_scanout_synthesis import audit as audit_scanout
from check_ddr_profile import audit as audit_ddr, PROFILE as DDR_PROFILE, SELECTION
from check_neo_fifo_synthesis import audit as audit_fifo
p=argparse.ArgumentParser(description=__doc__);p.add_argument('build',type=Path)
a=p.parse_args();build=a.build.resolve(strict=True)
report=build/'impl/pnr/console_neo.tr'
log=(build/'build.log').read_text()
if (re.search(r'^ERROR',log,re.M) or 'Bitstream generation completed' not in log
        or f'Generate file "{report}" completed' not in log):
    raise SystemExit('Incomplete build or timing report still being written')
result=inspect(build,'console_neo')
text=report.read_text()
from neo.timing import timing_checks
result['timing_checks_ns']=timing_checks(text)
if any(value<0 for value in result['timing_checks_ns'].values()):result['status']='FAIL'
if '<Part Number>: GW5AST-LV138PG484AC1/I0' not in text:raise SystemExit('Wrong FPGA part')
constraints=re.findall(r'^\s*TC_\S+\s+(\S+)\s+(.+?)\s*$',text,re.M)
if not constraints or any(state!='Actived' for state,command in constraints):
    raise SystemExit('Missing or inactive timing constraints')
normalize=lambda line:' '.join(line.split())
expected={normalize(line) for line in (build/'source/tang/boards/neo/neo.sdc').read_text().splitlines()
          if line.startswith(('create_', 'set_', 'report_timing '))}
if expected!={normalize(command) for state,command in constraints}:
    raise SystemExit('Timing report does not cover the complete frozen SDC')
result['active_timing_constraints']=len(constraints)
requested=(build/'build.tcl').read_text()
actual=(build/'impl/pnr/cmd.do').read_text()
result['pnr_options']={}
for key in ['place_option','route_option']:
    want=re.findall(r'^set_option -'+key+r' (\d+)$',requested,re.M)
    got=re.search(r'^-'+key+r' (\d+)$',actual,re.M)
    if not want or not got or want[-1]!=got[1]:raise SystemExit('PNR option not applied: '+key)
    result['pnr_options'][key]=int(got[1])
want=re.findall(r'^set_option -replicate_resources ([01])$',requested,re.M)
replicated=bool(re.search(r'^-replicate$',actual,re.M))
if not want or replicated!=bool(int(want[-1])):raise SystemExit('PNR replication option not applied')
result['pnr_options']['replicate_resources']=int(replicated)
if re.search(r'^set_option (place_option|route_option|replicate_resources) ',requested,re.M):
    raise SystemExit('Malformed PNR option in frozen Tcl (missing hyphen)')
frequencies={'clk50':50,'bus80_clk':80,'core_clk':800,'rtc_clk':10,
             'ddr3_mem_clk':300,'ddr3_sys_clk':75,'vid_pclk':74.375,'vid_clk5x':371.875}
top=(build/'source/tang/boards/neo/console_neo.v').read_text()
if '.DDR_REF_FROM_PLL(1)' in top:
    frequencies['ddr3_ref_clk']=50
    result['ddr_reference']='pll_50mhz'
elif '.DDR_REF_FROM_PLL(0)' in top:
    result['ddr_reference']='board_50mhz'
elif re.search(r'\bae350_soc\s+u_soc\s*\(', top) and (build/'source'/DDR_PROFILE).is_file():
    selection=build/'source'/SELECTION
    variant=json.loads(selection.read_text())['variant'] if selection.is_file() else 'prodock'
    if selection.is_file() and SELECTION not in json.loads((build/'sources.json').read_text()):
        raise SystemExit('Untracked DDR variant selection')
    result['ddr_profile']=audit_ddr(build/'source',variant,
        system_reset=(build/'source/tang/boards/neo/system_reset.json').is_file(),
        ddr_startup=(build/'source/tang/boards/neo/ddr_startup.json').is_file())
    if not result['ddr_profile']['passed']:raise SystemExit('DDR differs from its frozen reference profile')
    result['ddr_reference']=('neo_ddr6_board_50mhz' if variant.startswith('neo-ddr6-') else
                             'neo_tagged_board_50mhz' if variant.startswith('neo-tagged')
                             else 'prodock_board_50mhz')
else:raise SystemExit('Unknown DDR reference wiring')
result['features']={'soft_usb_hs':'soft_usb.vh' in top,'gamepads': 'neo_gamepads u_gamepads' in top}
if result['features']['soft_usb_hs']:
    frequencies.update(CLK_48M=48,PHY_CLKOUT=60,fclk_960M=960,sclk=120)
result['clock_mhz']={}
if result.get('ddr_profile',{}).get('variant')=='neo-ddr6-325-fifo-registers':
    frequencies.update(ddr3_mem_clk=325,ddr3_sys_clk=81.25)
if result.get('ddr_profile',{}).get('variant')=='neo-ddr6-400-fifo-registers':
    frequencies.update(ddr3_mem_clk=400,ddr3_sys_clk=100)
for clock,wanted in frequencies.items():
    found=re.search(r'^\s*\d+\s+'+clock+r'\s+(?:Base|Generated)\s+[\d.]+\s+([\d.]+)MHz',text,re.M)
    if not found or abs(float(found[1])-wanted)>.051:raise SystemExit('Missing/wrong clock '+clock)
    result['clock_mhz'][clock]=float(found[1])
from check_ddr_profile import IP_PROFILES, IP_CLOCK_MHZ, hynix_efr_clock_range
if result.get('ddr_profile',{}).get('variant') in IP_CLOCK_MHZ:
    _,iproot=IP_PROFILES[result['ddr_profile']['variant']]
    generated=json.loads((build/'source'/iproot/'generation.json').read_text())
    configured=1000000/int(generated['generated_parameters']['tCK'])
    observed=result['clock_mhz']['ddr3_mem_clk']
    # tCK is an integer number of ps in the generated IP.
    if abs(1000000/observed-int(generated['generated_parameters']['tCK']))>1.01:
        raise SystemExit('DDR IP tCK disagrees with the routed memory clock')
    result['ddr_memory_clock_consistency']={'configured_mhz':configured,'routed_mhz':observed,'passed':True}
    result['ddr_device_clock_range']=hynix_efr_clock_range(generated['generated_parameters'],observed)
    if not result['ddr_device_clock_range']['passed']:result['status']='FAIL'
manifest=json.loads((build/'sources.json').read_text())
for rel,digest in manifest.items():
    if sha(build/'source'/rel)!=digest:raise SystemExit('Changed frozen source '+rel)
# $readmemh paths are resolved against the build working directory. Checking
# only the canonical frozen source would miss a changed ROM/font mirror.
mirrors={'rtl/video/font8x16.hex':'tang/rtl/video/font8x16.hex',
         'font8x16.hex':'tang/rtl/video/font8x16.hex'}
if result['features']['gamepads']:
    mirrors['rtl/usbhost/usb_hid_host_rom.hex']='tang/boards/neo/usbhost/usb_hid_host_rom.hex'
result['memory_init_sha256']={}
for runtime,canonical in mirrors.items():
    digest=sha(build/runtime)
    if digest!=sha(build/'source'/canonical):raise SystemExit('Changed memory initialization '+runtime)
    result['memory_init_sha256'][runtime]=digest
result['sources_sha256']=sha(build/'sources.json')
result['bitstream_sha256']=sha(build/'impl/pnr/console_neo.fs')
result['timing_sha256']=sha(report)
result['constraints_sha256']={n:sha(build/'source/tang/boards/neo'/n) for n in ['neo.sdc','neo.cst']}
if (build/'route.json').exists():
    parent=json.loads((build/'route.json').read_text())
    if sha(build/'console_neo.vg')!=parent['netlist_sha256']:raise SystemExit('Reused netlist changed')
netlist=(build/'console_neo.vg') if (build/'route.json').exists() else (build/'impl/gwsynthesis/console_neo.vg')
# Keep the known Gowin DSP-mapping regressions inside the loading gate, too.
# These structural audits supplement timing and RTL tests, not equivalence.
result['synthesis_audits']={'copy':audit_copy(netlist),'scanout':audit_scanout(netlist)}
from neo.gpu_replication import audit as audit_gpu_replication
result['synthesis_audits']['gpu_owner_replication']=audit_gpu_replication(build/'impl/pnr/console_neo.vo')
if 'ddr_device_clock_range' in result:
    # Keep this mandatory in the parked-CPU diagnostic loading gate, too.
    result['synthesis_audits']['ddr_device_clock_range']=result['ddr_device_clock_range']
if (build/'route.json').exists() and parent.get('incremental'):
    from neo.incremental import audit as audit_incremental
    result['synthesis_audits']['incremental']=audit_incremental(build,parent['incremental'])
if (build/'source/tang/boards/neo/system_reset.json').is_file():
    from neo.system_reset import audit as audit_system_reset, audit_routed as audit_routed_reset
    result['synthesis_audits']['system_reset']=audit_system_reset(netlist)
    result['synthesis_audits']['system_reset_routed']=audit_routed_reset(build/'impl/pnr/console_neo.vo')
if (build/'source/tang/boards/neo/ddr_startup.json').is_file():
    from neo.ddr_startup import audit_mapped as audit_ddr_startup
    result['synthesis_audits']['ddr_startup']=audit_ddr_startup(netlist)
if (build/'source/tang/boards/neo/ddr_phy_timing.json').is_file():
    from neo.ddr_phy_timing import audit as audit_ddr_phy_timing
    result['synthesis_audits']['ddr_phy_timing']=audit_ddr_phy_timing(
        build/'source',build/'impl/pnr/console_neo.vo')
if (build/'source/tang/boards/neo/timing_closure.json').is_file():
    from neo.timing_closure import audit as audit_timing_closure
    result['synthesis_audits']['timing_closure']=audit_timing_closure(build/'source',report)
if result.get('ddr_profile',{}).get('variant') in ('neo-fifo-registers',*IP_PROFILES):
    result['synthesis_audits']['cpu_ddr_fifo_registers'] = audit_fifo(netlist)
if (build/'source/tang/boards/neo/gpu_reset.json').exists():
    from neo.gpu_reset import audit_reset_tree
    result['synthesis_audits']['gpu_reset_tree'] = audit_reset_tree(
        netlist, build/'impl/pnr/console_neo.rpt.txt',
        control_local='gpu_debug_state[43]' in (build/'source/tang/boards/neo/neo.cst').read_text())
if (build/'source/tang/boards/neo/gpu_local_payloads.json').exists():
    from neo.gpu_reset import audit_local_payloads
    result['synthesis_audits']['gpu_local_payloads']=audit_local_payloads(
        netlist,build/'impl/pnr/console_neo.rpt.txt')
if (build/'source/tang/boards/neo/gpu_stream_payload.json').exists():
    from neo.gpu_reset import audit_stream_payload
    result['synthesis_audits']['gpu_stream_payload']=audit_stream_payload(
        netlist,build/'impl/pnr/console_neo.rpt.txt')
if (build/'source/tang/boards/neo/gpu_transform_check.json').exists():
    from neo.gpu_reset import audit_transform_check
    result['synthesis_audits']['gpu_transform_check']=audit_transform_check(netlist)
if (build/'source/tang/boards/neo/gpu_response.json').exists():
    from neo.gpu_response import audit_mapped as audit_gpu_response
    result['synthesis_audits']['gpu_response']=audit_gpu_response(netlist)
if (build/'source/tang/boards/neo/gpu_command_prefetch.json').exists():
    from neo.command_prefetch import audit_mapped as audit_command_prefetch
    result['synthesis_audits']['gpu_command_prefetch']=audit_command_prefetch(netlist)
if (build/'source/tang/boards/neo/gpu_raster_payload.json').exists():
    from neo.raster_payload import audit_mapped as audit_raster_payload
    result['synthesis_audits']['gpu_raster_payload']=audit_raster_payload(netlist)
if (build/'source/tang/boards/neo/gpu_pixel_mask.json').exists():
    from neo.pixel_mask import audit as audit_pixel_mask
    result['synthesis_audits']['gpu_pixel_mask']=audit_pixel_mask(netlist)
    result['synthesis_audits']['gpu_pixel_mask_routed']=audit_pixel_mask(
        build/'impl/pnr/console_neo.vo',routed=True)
if (build/'source/tang/boards/neo/gpu_pixel_selector.json').exists():
    from neo.pixel_selector import audit as audit_pixel_selector
    result['synthesis_audits']['gpu_pixel_selector']=audit_pixel_selector(netlist)
    result['synthesis_audits']['gpu_pixel_selector_routed']=audit_pixel_selector(
        build/'impl/pnr/console_neo.vo',routed=True)
if (build/'source/tang/boards/neo/gpu_pixel_command_prefetch.json').exists():
    from neo.pixel_command_prefetch import audit_mapped as audit_pixel_command_prefetch
    result['synthesis_audits']['gpu_pixel_command_prefetch']=audit_pixel_command_prefetch(netlist)
if (build/'source/tang/boards/neo/gpu_bounds_prefetch.json').exists():
    from neo.gpu_reset import audit_bounds_prefetch
    result['synthesis_audits']['gpu_bounds_prefetch']=audit_bounds_prefetch(netlist)
if (build/'source/tang/boards/neo/gpu_shader_inputs.json').exists():
    from neo.gpu_reset import audit_shader_inputs
    result['synthesis_audits']['gpu_shader_inputs']=audit_shader_inputs(netlist)
if ((build/'wide_gpu_controls.json').exists() or
    ((build/'route.json').exists() and parent.get('wide_gpu_controls_local'))):
    from neo.gpu_control_routes import audit as audit_wide_controls
    catalog=json.loads((build/'wide_gpu_controls.json').read_text())
    # Also prove every catalogued constraint is in the frozen CST.
    cst=(build/'source/tang/boards/neo/neo.cst').read_text()
    for entry in catalog['entries']:
        if f'CLOCK_LOC "{entry["net"]}" LOCAL_CLOCK;' not in cst:
            raise SystemExit('Missing frozen wide-control constraint '+entry['net'])
    result['synthesis_audits']['gpu_wide_controls']=audit_wide_controls(
        netlist,build/'impl/pnr/console_neo.rpt.txt',catalog)
if (build/'route.json').exists():
    route_record=json.loads((build/'route.json').read_text())
    primary=bool(route_record.get('requested_primary_gpu_control_nets'))
    controls=route_record.get('requested_primary_gpu_control_nets' if primary else 'requested_local_gpu_control_nets',[])
    if controls:
        from neo.gpu_reset import audit_control_routing,control_local_constraints
        # Revalidate the frozen mapping as well as the physical result.
        _,expected_controls=control_local_constraints('',netlist.read_text())
        if controls!=expected_controls:raise SystemExit('Changed control routing experiment')
        result['synthesis_audits']['gpu_control_routing']=audit_control_routing(
            build/'impl/pnr/console_neo.rpt.txt',controls,primary=primary)
if not all(audit['passed'] for audit in result['synthesis_audits'].values()):result['status']='FAIL'
print(json.dumps(result,indent=2))
(build/'qualification.json').write_text(json.dumps(result,indent=2)+'\n')
if result['status']!='PASS':raise SystemExit('Timing or synthesis audit failed: candidate cannot be qualified')
