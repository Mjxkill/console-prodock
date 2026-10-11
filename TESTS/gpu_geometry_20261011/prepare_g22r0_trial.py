#!/usr/bin/env python3
"""Prepare the specific G22r0 SRAM experiment requested by the user on Oct 11.

Does not create physical_qualification.json or bitstream.sha256.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
from check_geometry_timing import inspect
from build_astrilla import TC


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    stage = ROOT/'tang/impl/gpu_geometry_g22r0'
    timing = inspect(stage)
    if (timing['minimum_slack_ns'], timing['violated_endpoints']) != (-.564, {'setup': 9, 'hold': 0}):
        raise RuntimeError('Not the G22r0 result selected by the user')
    log = (stage/'build.log').read_text()
    if 'ERROR' in log or 'Bitstream generation completed' not in log or 'Power analysis completed' not in log:
        raise RuntimeError('Incomplete physical build')
    sources = json.loads((stage/'sources.json').read_text())
    for name, digest in sources.items():
        if sha(stage/'source'/name) != digest:
            raise RuntimeError('Changed frozen source: '+name)
    build = json.loads((stage/'geometry_build.json').read_text())
    for name in build['changes']:
        if sha(ROOT/name) != sources[name]:
            raise RuntimeError('Current RTL differs: '+name)
    netlist = stage/'impl/gwsynthesis/console_gpu_geometry_g22r0.vg'
    if sha(netlist) != build['synthesis_reused']['sha256']:
        raise RuntimeError('Changed netlist')
    if sha(stage/'rtl/video/font8x16.hex') != sources['tang/rtl/video/font8x16.hex']:
        raise RuntimeError('Changed font mirror')
    bitstream = stage/'impl/pnr/console_gpu_geometry_g22r0.fs'
    out = ROOT/'TESTS/gpu_geometry_20261011/g22r0_trial_pack'
    out.mkdir(exist_ok=False)
    record = dict(experimental=True, timing_qualified=False, user_request='ok on teste celui la',
                  stage=stage.name, bitstream_sha256=sha(bitstream), timing=timing,
                  programming='SRAM only', physical_sd_writes=0, applications={})
    # Hash every transported stage file; no edits to the immutable build.
    files = [stage/'source'/name for name in sources]
    files += [stage/name for name in ('sources.json', 'geometry_build.json', 'build.tcl',
              'build_driver.py', 'build.log', 'constraints_resolved.cst', 'rtl/video/font8x16.hex')]
    files += [bitstream, netlist, stage/'impl/pnr/console_gpu_geometry_g22r0.tr',
              stage/'impl/pnr/console_gpu_geometry_g22r0.rpt.txt']
    record['stage_files'] = {str(p.relative_to(stage)): sha(p) for p in files}
    fw_sources = {str(p.relative_to(ROOT)): sha(p) for p in (ROOT/'fw_console').glob('*')
                  if p.is_file() and p.suffix in ('.c', '.h', '.ld', '.S')}
    fw_sources['fw_console/Makefile'] = sha(ROOT/'fw_console/Makefile')
    preflight = json.loads((out.parent/'apps_preflight.json').read_text())
    for app, flags in [('world3d', '-ffp-contract=off'),
                       ('astrilla', '-ffp-contract=off -DASTRILLA_HW_GEOMETRY')]:
        subprocess.run(['make', '-s', '-C', str(ROOT/'fw_console'), 'MAIN='+app+'_main.c',
                        'BUILD=build/'+app+'_geometry', 'EXTRA_SRCS=gpu_geometry.c',
                        'CFLAGS_EXTRA='+flags, 'LD='+str(ROOT/'fw_console/astrilla.ld')], check=True)
        binary = ROOT/'fw_console/build'/ (app+'_geometry') / 'console_test.bin'
        if sha(binary) != preflight[app]['sha256']:
            raise RuntimeError('Application changed since preflight: '+app)
        symbols = subprocess.check_output([str(TC), str(binary.with_suffix('.elf'))], text=True)
        entry = int(next(s.split()[0] for s in symbols.splitlines() if s.endswith(' T _start')), 16)
        if not 0xa0000000 <= entry < 0xa0000000+binary.stat().st_size <= 0xa0010000:
            raise RuntimeError('Invalid ILM image')
        filename = app+'_hw.bin'
        (out/filename).write_bytes(binary.read_bytes())
        meta = dict(binary=filename, geometry_abi='G3D1', load=0xa0000000, entry=entry,
                    bytes=binary.stat().st_size, sha256=sha(binary), fpga_stage=stage.name,
                    fpga_sha256=sha(bitstream), experimental=True, timing_qualified=False,
                    assets_sha256=sha(ROOT/'assets/astrilla/packed/astrilla.bin'), sources=fw_sources)
        (out/(app+'.json')).write_text(json.dumps(meta, indent=2)+'\n')
        record['applications'][app] = dict(manifest_sha256=sha(out/(app+'.json')), **preflight[app])
    (out/'experiment.json').write_text(json.dumps(record, indent=2)+'\n')
    print('Prepared experimental G22r0:', record['bitstream_sha256'], flush=True)


if __name__ == '__main__':
    main()
