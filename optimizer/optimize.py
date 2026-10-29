#!/usr/bin/env python3
"""Gowin Workbench: open PnR, measured timing, placement candidates and experiments."""
import argparse
import json
from pathlib import Path
import subprocess

from runtime import ROOT, SUITE, save, tool_command, tool_env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    doctor = commands.add_parser('doctor', help='Tool versions and 138K database presence')
    doctor.add_argument('--out', type=Path)
    open_cmd = commands.add_parser('open', help='Compile RTL with Yosys/nextpnr/Apicula; no board writes')
    open_cmd.add_argument('--project', type=Path, default=ROOT/'examples/neo_probe/project.json')
    open_cmd.add_argument('--out', type=Path, required=True)
    open_cmd.add_argument('--seeds', nargs='+', type=int, default=[1, 7, 42])
    open_cmd.add_argument('--placer', choices=['heap', 'sa'], default='heap')
    open_cmd.add_argument('--router', choices=['router1', 'router2'], default='router1')
    open_cmd.add_argument('--timeout', type=int, default=1800)
    report = commands.add_parser('report', help='Compare completed and failed Gowin builds, export interactive HTML')
    report.add_argument('builds', type=Path, nargs='+')
    report.add_argument('--out', type=Path, required=True)
    report.add_argument('--board-results', type=Path, nargs='+', default=[],
                        help='Explicit result.json files/directories; matched by bitstream SHA-256')
    placement = commands.add_parser('place', help='Propose a region for measured critical LUT/DFF cells')
    placement.add_argument('--build', type=Path, required=True)
    placement.add_argument('--cst', type=Path, required=True)
    placement.add_argument('--out', type=Path, required=True)
    placement.add_argument('--region', required=True)
    placement.add_argument('--paths', type=int, default=2)
    plan = commands.add_parser('plan', help='Freeze a reviewable sequential Gowin experiment plan')
    plan.add_argument('--parent', type=Path, required=True)
    plan.add_argument('--experiments', type=Path, required=True, help='JSON array of name/place/route/replicate/cst')
    plan.add_argument('--out', type=Path, required=True)
    run = commands.add_parser('run', help='Execute a frozen plan; does not load any FPGA')
    run.add_argument('plan', type=Path)
    search = commands.add_parser('search', help='Prepare 1..3 regional candidates automatically from critical paths')
    search.add_argument('--parent',type=Path,required=True)
    search.add_argument('--out',type=Path,required=True)
    search.add_argument('--prefix',required=True)
    search.add_argument('--trials',type=int,choices=[1,2,3],default=3)
    search.add_argument('--paths',type=int,default=2)
    search.add_argument('--split-paths',action='store_true',help='Use separate regions for disjoint critical paths')
    args = parser.parse_args()
    if args.command == 'doctor':
        versions = {}
        for tool, options in [('yosys', ['-V']), ('nextpnr-himbaechel', ['--version']), ('gowin_pack', ['--help'])]:
            result = subprocess.run(tool_command(tool, options), env=tool_env(), capture_output=True, text=True, timeout=30)
            versions[tool] = dict(returncode=result.returncode, output=(result.stdout+result.stderr).strip())
        result = dict(toolchain=json.loads((ROOT/'toolchain.lock.json').read_text()), tools=versions,
                      database_138k=(SUITE/'share/nextpnr/himbaechel/gowin/chipdb-GW5AST-138C.bin').exists())
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            save(args.out, result)
        print(json.dumps(result, indent=2))
    elif args.command == 'open':
        from openflow import build
        result = build(args.project, args.out, args.seeds, args.placer, args.router, args.timeout)
        print(result['status'] + ': ' + str(args.out))
        if result['status'] != 'COMPILED':
            raise SystemExit(1)
    elif args.command == 'report':
        from reports import comparison, attach_board_results
        from dashboard import export
        result = comparison(args.builds)
        attach_board_results(result, args.board_results)
        args.out.mkdir(parents=True, exist_ok=True)
        save(args.out/'comparison.json', result)
        export(result, args.out/'index.html')
        for item in result['builds']:
            print(f"{item['name']:28} {item['status']:14} WNS={item.get('wns_ns')} TNS={item.get('tns_ns')}")
        print(args.out/'index.html')
    elif args.command == 'place':
        from placement import propose
        result = propose(args.build, args.cst, args.out, args.region, args.paths)
        print(f"PROPOSED: {len(result['cells'])} cells, {args.out}; must route and qualify")
    elif args.command == 'plan':
        from gowinflow import make_plan
        make_plan(args.parent, args.out, json.loads(args.experiments.read_text()))
        print(args.out)
    elif args.command == 'run':
        from gowinflow import execute_plan
        state = execute_plan(args.plan)
        if not all(j['status'] == 'QUALIFIED' for j in state['jobs']):
            raise SystemExit(1)
    elif args.command == 'search':
        from search import prepare
        result=prepare(args.parent,args.out,args.prefix,args.trials,args.paths,args.split_paths)
        print(f"Prepared {len(result['experiments'])} experiments: {args.out/'plan.json'}")


if __name__ == '__main__':
    try:
        main()
    except (ValueError, FileNotFoundError, FileExistsError) as error:
        raise SystemExit(str(error))
