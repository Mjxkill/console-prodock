"""Reproducible Yosys → nextpnr → Apicula builds, isolated per seed."""
import json
import math
from pathlib import Path
import re
import shutil
from collections import Counter

from runtime import ROOT, SUITE, run_tool, save, sha


def validate_project(project):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', project['top']):
        raise ValueError('Invalid top module')
    frequency = project['frequency_mhz']
    if not isinstance(frequency, (float, int)) or not math.isfinite(frequency) or frequency <= 0:
        raise ValueError('frequency_mhz must be positive and finite')
    if project['synth_family'] not in ('gw1n', 'gw2a', 'gw5a'):
        raise ValueError('Unsupported synth_family')
    if not project['sources']:
        raise ValueError('Empty RTL source list')
    if project.get('packer', 'bundled') not in ('bundled', 'legacy-0.32'):
        raise ValueError('Unknown Apicula packer')


def build(project_path, out, seeds=(1,), placer='heap', router='router1', timeout=1800):
    project_path = Path(project_path).resolve(strict=True)
    project = json.loads(project_path.read_text())
    validate_project(project)
    if placer not in ('heap', 'sa') or router not in ('router1', 'router2'):
        raise ValueError('Unsupported placement/routing strategy')
    if len(set(seeds)) != len(seeds) or not seeds or any(s < 0 or s > 0xffffffff for s in seeds):
        raise ValueError('Seeds must be unique unsigned 32-bit integers')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    frozen = out / 'source'
    frozen.mkdir()
    manifest = {}
    sources = []
    for index, source in enumerate(project['sources']):
        origin = (project_path.parent / source).resolve(strict=True)
        # Safe generated names also avoid Tcl/Yosys/shell interpolation.
        target = frozen / f'rtl_{index:03d}.v'
        shutil.copyfile(origin, target)
        manifest[target.name] = dict(origin=str(origin), sha256=sha(target))
        sources.append('source/' + target.name)
    cst = frozen / 'pins.cst'
    shutil.copyfile(project_path.parent / project['cst'], cst)
    manifest[cst.name] = dict(origin=project['cst'], sha256=sha(cst))
    sdc = None
    if project.get('sdc'):
        sdc = frozen / 'timing.sdc'
        shutil.copyfile(project_path.parent / project['sdc'], sdc)
        manifest[sdc.name] = dict(origin=project['sdc'], sha256=sha(sdc))
    result = dict(backend='nextpnr', status='RUNNING', project=project,
                  inputs=manifest, seeds=list(seeds), strategies=dict(placer=placer, router=router),
                  toolchain=json.loads((ROOT / 'toolchain.lock.json').read_text()), candidates=[])
    if project.get('packer') == 'legacy-0.32':
        result['legacy_packer'] = json.loads((ROOT/'apicula-legacy.lock.json').read_text())
    save(out / 'result.json', result)
    script = '\n'.join(['read_verilog -sv ' + ' '.join(sources),
                        f"synth_gowin -family {project['synth_family']} -top {project['top']} -json netlist.json",
                        'check -assert', 'stat']) + '\n'
    (out / 'synth.ys').write_text(script)
    command = run_tool('yosys', ['-Q', '-T', '-s', 'synth.ys'], out, out / 'synth.log', timeout)
    result['synthesis'] = command
    if command['returncode'] != 0 or not (out / 'netlist.json').exists():
        result['status'] = 'SYNTHESIS_FAILED'
        save(out / 'result.json', result)
        return result
    result['netlist_sha256'] = sha(out / 'netlist.json')
    mapped = json.loads((out/'netlist.json').read_text())['modules'][project['top']]['cells']
    result['mapped_cells'] = dict(Counter(cell['type'] for cell in mapped.values()))
    missing = {cell:count for cell, count in project.get('required_cells', {}).items()
               if result['mapped_cells'].get(cell, 0) < count}
    if missing:
        result.update(status='RESOURCE_MAPPING_FAILED', missing_cells=missing)
        save(out/'result.json', result)
        return result
    result['compatibility_key'] = sha(out / 'source/pins.cst') + ':' + result['netlist_sha256']
    for seed in seeds:
        stage = out / f'seed_{seed}'
        stage.mkdir()
        args = ['--device', project['device'], '--vopt', 'family=' + project['family'],
                '--vopt', 'cst=../source/pins.cst', '--json', '../netlist.json',
                '--write', 'routed.json', '--report', 'timing.json', '--detailed-timing-report',
                '--freq', str(project['frequency_mhz']), '--seed', str(seed),
                '--placer', placer, '--router', router]
        if sdc:
            args += ['--sdc', '../source/timing.sdc']
        record = dict(seed=seed, status='ROUTING', clock_mhz=project['frequency_mhz'])
        record['pnr'] = run_tool('nextpnr-himbaechel', args, stage, stage / 'pnr.log', timeout)
        record['status'] = 'PNR_FAILED'
        if record['pnr']['returncode'] == 0 and (stage / 'routed.json').exists() and (stage / 'timing.json').exists():
            timing = json.loads((stage / 'timing.json').read_text())
            record['timing'] = timing
            # nextpnr's report does not certify Gowin hold/pulse/CDC timing.
            # All reported clocks must meet their requested frequency.
            clocks = timing.get('fmax', {})
            timing_ok = bool(clocks) and all(v['achieved'] >= v['constraint'] > 0 for v in clocks.values())
            record['status'] = 'TIMING_FAILED' if not timing_ok else 'ROUTED'
            if timing_ok:
                packer = 'gowin_pack_legacy' if project.get('packer') == 'legacy-0.32' else 'gowin_pack'
                record['pack'] = run_tool(packer, ['-d', project['family'], '-o', 'design.fs', 'routed.json'],
                                          stage, stage / 'pack.log', timeout)
                record['status'] = 'PACK_FAILED'
                if record['pack']['returncode'] == 0 and (stage / 'design.fs').stat().st_size > 0:
                    record.update(status='COMPILED', bitstream_sha256=sha(stage / 'design.fs'))
        record['output_sha256'] = {name:sha(stage/name) for name in ('routed.json','timing.json','design.fs')
                                   if (stage/name).is_file()}
        save(stage / 'result.json', record)
        result['candidates'].append(record)
        save(out / 'result.json', result)
    result['status'] = 'COMPILED' if all(c['status'] == 'COMPILED' for c in result['candidates']) else 'FAILED'
    result['validation_scope'] = 'Compile-only; no hardware test, no Gowin STA equivalence or console IP qualification'
    save(out / 'result.json', result)
    return result
