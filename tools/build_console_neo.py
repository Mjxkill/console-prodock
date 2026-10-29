#!/usr/bin/env python3
"""Freeze a Neo 720p console build, regenerate its parking ITCM, run Gowin.

No access to the analyser worktree, board, flash or SD. Shared GPU sources
remain those used by the Pro Dock; all generated files live in this build.
"""
import argparse, hashlib, json, os, re, shutil, subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
from check_ddr_profile import audit as audit_ddr, freeze_variant, VARIANTS
from gowin_toolchain import IDE, environment
from board_contract import before_build, record_build
ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name', required=True)
    p.add_argument('--stage', choices=['syn','all'], default='all')
    p.add_argument('--place',type=int,choices=range(5),default=3)
    p.add_argument('--route',type=int,choices=range(3),default=2)
    p.add_argument('--replicate',type=int,choices=(0,1),default=0)
    p.add_argument('--placement-cst',type=Path,help='Candidate INS_LOC only; pins/banks/clocks must match')
    p.add_argument('--ddr-adapter',choices=VARIANTS,default='neo-fifo-registers',
                   help='DDR profile (default: %(default)s): original DDR3 5.9 at 300 MHz with register FIFOs; DDR3 6.0 requires explicit selection')
    p.add_argument('--gpu-debug',action='store_true',
                   help='Observe GPU state through an independent snapshot port in the frozen Neo copy only')
    p.add_argument('--gpu-reset-tree',action='store_true',
                   help='Neo experiment: twelve same-cycle GPU reset drivers on local routing; requires --gpu-debug')
    p.add_argument('--gpu-payload-prefetch',action='store_true',
                   help='Neo experiment: decouple idle DDR payload capture from REQUEST; no added transaction stage')
    p.add_argument('--gpu-shader-phase',action='store_true',
                   help='Neo experiment: retain shader read phase locally; no added transaction stage')
    p.add_argument('--gpu-local-payloads',action='store_true',
                   help='Neo experiment: prefetch clip operands and reset pixel masks without resetting payload')
    p.add_argument('--gpu-stream-payload',action='store_true',
                   help='Neo experiment: continuously sample held native payload, with unchanged valid/ack cycles')
    p.add_argument('--gpu-transform-check',action='store_true',
                   help='Neo experiment: register transform overflow with its sum, without extra FSM cycles')
    p.add_argument('--gpu-response-stage',action='store_true',
                   help='One UI-clock stage between DDR responses and GPU; CPU/scanout paths unchanged')
    p.add_argument('--gpu-command-prefetch',action='store_true',
                   help='Prefetch private geometry commands during IDLE with unchanged acceptance cycles')
    p.add_argument('--gpu-pixel-command-prefetch',action='store_true',
                   help='Prefetch private pixel commands during IDLE, preserving busy packet and acceptance cycles')
    p.add_argument('--gpu-raster-private',action='store_true',
                   help='Keep per-chunk payload clear, removing only the raster buffers global reset')
    p.add_argument('--gpu-bounds-prefetch',action='store_true',
                   help='Prefetch geometry clipping coefficients before multiplication, preserving FSM cycles')
    p.add_argument('--gpu-shader-inputs',action='store_true',
                   help='Prefetch texture coordinates and round alpha after the product, preserving FSM cycles')
    p.add_argument('--timing-closure-reference',type=Path,
                   help='Neo-only HDMI DCE/reset placement and audited CDC latency normalization from a prior timing report')
    p.add_argument('--system-reset-tree',action='store_true',
                   help='Neo-only same-cycle reset copies for six independent top-level consumers')
    p.add_argument('--ddr-startup',action='store_true',
                   help='Explicit DDR reset at 50 MHz and CPU release after lock/calibration')
    a = p.parse_args()
    if a.gpu_reset_tree and not a.gpu_debug:p.error('--gpu-reset-tree requires --gpu-debug')
    if a.gpu_payload_prefetch and not a.gpu_reset_tree:p.error('--gpu-payload-prefetch requires --gpu-reset-tree')
    if a.gpu_shader_phase and not a.gpu_reset_tree:p.error('--gpu-shader-phase requires --gpu-reset-tree')
    if a.gpu_local_payloads and not a.gpu_shader_phase:p.error('--gpu-local-payloads requires --gpu-shader-phase')
    if a.gpu_stream_payload and not (a.gpu_local_payloads and a.gpu_payload_prefetch):p.error('--gpu-stream-payload requires --gpu-local-payloads and --gpu-payload-prefetch')
    if a.gpu_transform_check and not a.gpu_stream_payload:p.error('--gpu-transform-check requires --gpu-stream-payload')
    if a.gpu_response_stage and not a.system_reset_tree:p.error('--gpu-response-stage requires --system-reset-tree')
    ddr = audit_ddr(ROOT)
    if not ddr['passed']:raise ValueError('DDR differs from Pro Dock: '+str(ddr['changed']))
    if not re.fullmatch('[a-zA-Z0-9_]+', a.name): p.error('Invalid build name')
    contract = before_build('neo', candidate=True)
    out = ROOT/'tang/impl'/a.name
    out.mkdir(exist_ok=False)
    record_build(out, contract)
    source = out/'source'
    files = re.findall(r'^add_file (\S+)', (ROOT/'tang/build_gpu.tcl').read_text(), re.M)
    files = ['tang/'+s for s in files if not s.startswith(('constr/','rtl/console_gpu.','rtl/video/gowin_pll_lcd.'))]
    files += [str(s.relative_to(ROOT)) for s in sorted((ROOT/'tang/boards/neo/vendor').glob('*.v'))]
    files += ['tang/boards/neo/console_neo.v','tang/boards/neo/neo_console_input.v','tang/boards/neo/neo_gamepads.v','tang/boards/neo/neo.cst','tang/boards/neo/neo.sdc']
    files += [str(s.relative_to(ROOT)) for s in sorted((ROOT/'tang/boards/neo/usbhost').glob('*.v'))]
    files += ['tang/boards/neo/usbhost/usb_hid_host_rom.hex','tang/boards/neo/neo_scan_queue.v']
    # Embedded font path is relative to the isolated build directory.
    files += ['tang/rtl/video/font8x16.hex','tang/boards/neo/soft_usb.vh']
    if a.gpu_debug:files += ['tang/boards/neo/neo_gpu_debug.v']
    if a.ddr_startup:files += ['tang/boards/neo/neo_ddr_startup.v']
    if a.gpu_response_stage:files += ['tang/boards/neo/neo_gpu_response.v']
    for name in files:
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/name,target)
    profile=source/'tang/boards/neo'
    if a.placement_cst:
        def fixed(path):
            clean='\n'.join(line.split('//',1)[0] for line in path.read_text().splitlines())
            statements=[' '.join(part.split()) for part in clean.split(';')]
            return [s for s in statements if s and not s.startswith('INS_LOC ')]
        if fixed(profile/'neo.cst')!=fixed(a.placement_cst):
            raise ValueError('Placement candidate changes pins/banks/non-placement constraints')
        shutil.copy2(a.placement_cst,profile/'neo.cst')
    freeze_variant(ROOT,source,a.ddr_adapter)
    if a.ddr_adapter in ('neo-ddr6-325-fifo-registers','neo-ddr6-400-fifo-registers'):
        mem=('3.076923','1.538462') if '325' in a.ddr_adapter else ('2.5','1.25')
        ui=('12.307692','6.153846') if '325' in a.ddr_adapter else ('10','5')
        sdc=profile/'neo.sdc';text=sdc.read_text()
        for old,new in [('-name ddr3_mem_clk -period 3.333 -waveform {0 1.667}',
                         f'-name ddr3_mem_clk -period {mem[0]} -waveform {{0 {mem[1]}}}'),
                        ('-name ddr3_sys_clk -period 13.333 -waveform {0 6.667}',
                         f'-name ddr3_sys_clk -period {ui[0]} -waveform {{0 {ui[1]}}}')]:
            if text.count(old)!=1:raise ValueError('Unknown DDR clock constraint')
            text=text.replace(old,new,1)
        sdc.write_text(text)
    if a.gpu_reset_tree:
        from neo.gpu_reset import split_resets
        split_resets(source)
    if a.gpu_payload_prefetch:
        from neo.gpu_reset import prefetch_payload
        prefetch_payload(source)
    if a.gpu_shader_phase:
        from neo.gpu_reset import register_shader_phase
        register_shader_phase(source)
    if a.gpu_local_payloads:
        from neo.gpu_reset import local_geometry_payloads
        local_geometry_payloads(source)
    if a.gpu_stream_payload:
        from neo.gpu_reset import stream_native_payload
        stream_native_payload(source)
    if a.gpu_transform_check:
        from neo.gpu_reset import register_transform_check
        register_transform_check(source)
    if a.gpu_command_prefetch:
        from neo.command_prefetch import freeze as freeze_command_prefetch
        freeze_command_prefetch(source)
    if a.gpu_pixel_command_prefetch:
        from neo.pixel_command_prefetch import freeze as freeze_pixel_command_prefetch
        freeze_pixel_command_prefetch(source)
    if a.gpu_raster_private:
        from neo.raster_payload import freeze as freeze_raster_payload
        freeze_raster_payload(source)
    if a.gpu_bounds_prefetch:
        from neo.gpu_reset import prefetch_bounds_ratio
        prefetch_bounds_ratio(source)
    if a.gpu_shader_inputs:
        from neo.gpu_reset import prefetch_shader_inputs
        prefetch_shader_inputs(source)
    if a.gpu_debug:
        from neo.gpu_debug import instrument
        instrument(source)
    if a.gpu_reset_tree:
        from neo.gpu_reset import constrain_local
        constrain_local(source)
    if a.ddr_startup:
        from neo.ddr_startup import freeze as freeze_ddr_startup
        freeze_ddr_startup(source)
    if a.system_reset_tree:
        from neo.system_reset import freeze as freeze_system_reset
        freeze_system_reset(source)
    if a.gpu_response_stage:
        from neo.gpu_response import freeze as freeze_gpu_response
        freeze_gpu_response(source)
    if a.timing_closure_reference:
        from neo.timing_closure import freeze
        freeze(source,a.timing_closure_reference)
    cfg=source/'tang/rtl/board/riscv_ae350_soc_ext/cfg'
    shutil.copy2(ROOT/'tang/rtl/board/riscv_ae350_soc_ext/cfg/riscv_ae350_soc.prj', cfg/'riscv_ae350_soc.prj')
    boot=source/'parking_itcm';boot.mkdir()
    payload=bytes.fromhex('730050106ff0dfff') # wfi; j -4, no peripheral/SD access
    (boot/'parking.bin').write_bytes(payload)
    for lane in range(4):
        (boot/f'itcm{lane}').write_text('\n'.join(f'{b:02x}' for b in payload[lane::4])+'\n')
    # This is the fabric boot RAM at 0x80000000, NOT the hard 64-KiB ILM
    # at 0xa0000000 used by launch_packed. 1024 words suffice for the parking
    # program and avoid spreading its unpipelined AHB address bus over 32 RAMs.
    (cfg/'gw_itcm_config.v').write_text(f'`define ITCM_SIZE 10\n`define ITCM_INIT_PATH "{boot}"\n')
    ip=out/'ae350_ip';ip.mkdir()
    tree=ET.parse(cfg/'riscv_ae350_soc.prj')
    tree.getroot().find('Device').attrib.update(id='GW5AST-138C',package='PBGA484A',
        speed='1',partNumber='GW5AST-LV138PG484AC1/I0')
    includes=tree.findall(".//Option[@type='include_path']")
    includes[0].set('value',str(cfg));includes[1].set('value',str(IDE/'ipcore/RiscV_AE350_SOC/data'))
    for n in tree.findall('.//File'):
        path=IDE/'ipcore'/n.get('path').split('/IDE/ipcore/')[1]
        if not path.is_file():raise FileNotFoundError(path)
        n.set('path',str(path))
    tree.write(ip/'cpu.prj',encoding='UTF-8',xml_declaration=True)
    env=environment()
    (out/'toolchain.json').write_text(json.dumps(dict(ide=str(IDE),
        ld_preload=env.get('LD_PRELOAD','')),indent=2)+'\n')
    print(out,flush=True)
    with (ip/'synth.log').open('w') as log:
        subprocess.run([str(IDE/'bin/GowinSynthesis'),'-prj',str(ip/'cpu.prj')],
                       cwd=ip,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    if 'GowinSynthesis finish' not in (ip/'synth.log').read_text():raise RuntimeError('AE350 IP generation incomplete')
    shutil.copy2(ip/'riscv_ae350_soc.vg',source/'tang/rtl/board/riscv_ae350_soc_ext/riscv_ae350_soc.v')
    for rel in ('rtl/video/font8x16.hex','font8x16.hex'):
        dest=out/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/'tang/rtl/video/font8x16.hex',dest)
    rom=out/'rtl/usbhost/usb_hid_host_rom.hex';rom.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source/'tang/boards/neo/usbhost/usb_hid_host_rom.hex',rom)
    commands=['set_device -name GW5AST-138C GW5AST-LV138PG484AC1/I0']
    commands += ['add_file {'+str(source/name)+'}' for name in files if not name.endswith(('.hex','.vh'))]
    commands += ['set_option -top_module console_neo', 'set_option -output_base_name console_neo',
        'set_option -verilog_std sysv2017','set_option -use_cpu_as_gpio 1','set_option -use_sspi_as_gpio 0',
        'set_option -include_path {'+str(source/'tang/rtl')+';'+str(source/'tang')+'}',
        'set_option -gen_text_timing_rpt 1','set_option -gen_verilog_sim_netlist 1','set_option -gen_sdf 1',
        f'set_option -place_option {a.place}',f'set_option -route_option {a.route}',f'set_option -replicate_resources {a.replicate}',
        'set_option -clock_route_order 1','run '+a.stage]
    (out/'build.tcl').write_text('\n'.join(commands)+'\n')
    manifest={str(f.relative_to(source)):hashlib.sha256(f.read_bytes()).hexdigest() for f in source.rglob('*') if f.is_file()}
    (out/'sources.json').write_text(json.dumps(manifest,indent=2)+'\n')
    with (out/'build.log').open('w') as log:
        result=subprocess.run([str(IDE/'bin/gw_sh'),'build.tcl'],cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode or re.search(r'^ERROR', (out/'build.log').read_text(),re.M):
        raise RuntimeError('Gowin failed: '+str(out/'build.log'))
    print('Build completed; timing/CDC and pin reports must be checked before loading.',flush=True)


if __name__=='__main__':main()
