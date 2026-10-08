#!/usr/bin/env python3
"""Audit de routage des pointeurs Gray des FIFO MSC dans le SDF Gowin.

Toutes les liaisons vers les deux étages synchroniseurs doivent être
présentes et directes depuis une sortie Q. Budget conservateur de 6,25 ns
(demi-période du domaine le plus rapide, 80 MHz), sans modifier le SDC.
Ce contrôle de routage complète les tests CDC/reset ; il ne calcule pas le
MTBF et ne remplace pas l'analyse setup/hold ni la validation du PHY.
--flush-ack vérifie aussi les cinq liaisons de la purge acquittée (C2+).
--bot-guard vérifie les cinq liaisons de demande/statut du verrou BOT (C27+).
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def audit(path, flush_ack=False, bot_guard=False):
    groups = {f'{fifo}_{pointer}_{stage}': {} for fifo in ('tx', 'rx')
              for pointer in ('wr', 'rd') for stage in (1, 2)}
    errors = []
    flush_sources = {'flush_s_0': 'flush_count_7', 'flush_s_1': 'flush_s_0',
                     'flush_u': 'flush_s_1', 'flush_ack_h_0': 'flush_u',
                     'flush_ack_h_1': 'flush_ack_h_0'}
    flush_paths = {}
    guard_sources = {'halt_s_0': 'u_usb_msc_port/halt_toggle',
                     'halt_s_1': 'u_usb_msc_port/halt_s_0',
                     'halt_s_2': 'u_usb_msc_port/halt_s_1',
                     'halted_h_0': 'u_usb_msc_guard/halted',
                     'halted_h_1': 'u_usb_msc_port/halted_h_0'}
    guard_paths = {}
    guard_pattern = re.compile(r'INTERCONNECT (\S+) '
                               r'(u_usb_msc_port/(halt_s_[012]|halted_h_[01])_s\d+/D) '
                               r'\(([^)]+)\)')
    flush_pattern = re.compile(r'INTERCONNECT (\S+) '
                               r'(u_usb_msc_port/(flush_s_[01]|flush_u|flush_ack_h_[01])_s\d+/D) '
                               r'\(([^)]+)\)')
    pattern = re.compile(r'INTERCONNECT (\S+) '
                         r'(u_usb_msc_port/u_(tx|rx)/(wr|rd)_gray_s([12])_(\d+)_s\d+/D) '
                         r'\(([^)]+)\)')
    with path.open() as stream:
        for line in stream:
            if 'INTERCONNECT' not in line or 'u_usb_msc_port\\/' not in line:
                continue
            line = line.replace('\\/', '/')
            if bot_guard:
                guard = guard_pattern.search(line)
                if guard:
                    source, target, name, delay = guard.groups()
                    corners = [float(d) for d in delay.split(':')]
                    if name in guard_paths:
                        errors.append(f'Liaison BOT dupliquée : {target}')
                    guard_paths[name] = dict(source=source, target=target, corners_ns=corners)
                    expected = rf'{guard_sources[name]}_s\d+/Q'
                    if not re.fullmatch(expected, source):
                        errors.append(f'Source BOT inattendue : {source} -> {target}')
                    if max(corners) >= 6.25:
                        errors.append(f'Budget de routage BOT dépassé : {target}')
            if flush_ack:
                flush = flush_pattern.search(line)
                if flush:
                    source, target, name, delay = flush.groups()
                    corners = [float(d) for d in delay.split(':')]
                    if name in flush_paths:
                        errors.append(f'Liaison de purge dupliquée : {target}')
                    flush_paths[name] = dict(source=source, target=target, corners_ns=corners)
                    expected = rf'u_usb_msc_port/{flush_sources[name]}_s\d+/Q'
                    if not re.fullmatch(expected, source):
                        errors.append(f'Source de purge inattendue : {source} -> {target}')
                    if max(corners) >= 6.25:
                        errors.append(f'Budget de routage de purge dépassé : {target}')
            match = pattern.search(line)
            if not match:
                continue
            source, target, fifo, pointer, stage, bit, delay = match.groups()
            key = f'{fifo}_{pointer}_{stage}'
            bit = int(bit)
            corners = [float(d) for d in delay.split(':')]
            if bit in groups[key]:
                errors.append(f'Liaison dupliquée : {target}')
            groups[key][bit] = dict(source=source, target=target, corners_ns=corners)
            # Le bit Gray de poids fort peut partager le registre binaire.
            expected = (rf'u_usb_msc_port/u_{fifo}/{pointer}_(gray|bin)_{bit}_s\d+/Q'
                        if stage == '1' else
                        rf'u_usb_msc_port/u_{fifo}/{pointer}_gray_s1_{bit}_s\d+/Q')
            if not re.fullmatch(expected, source):
                errors.append(f'Source synchroniseur inattendue : {source} -> {target}')
            if max(corners) >= 6.25:
                errors.append(f'Budget de routage dépassé : {target}')
    result = {}
    for name, paths in groups.items():
        width = 11 if name.startswith('tx_') else 10
        if set(paths) != set(range(width)):
            errors.append(f'Couverture incomplète : {name}, {sorted(paths)} / {width}')
        delays = [d for p in paths.values() for d in p['corners_ns']]
        result[name] = dict(expected=width, found=len(paths),
                            max_route_ns=max(delays) if delays else None,
                            paths=[dict(bit=b, **p) for b, p in sorted(paths.items())])
    if flush_ack and set(flush_paths) != set(flush_sources):
        errors.append('Liaisons de purge manquantes : ' + ', '.join(sorted(set(flush_sources) - set(flush_paths))))
    if bot_guard and set(guard_paths) != set(guard_sources):
        errors.append('Liaisons BOT manquantes : ' + ', '.join(sorted(set(guard_sources) - set(guard_paths))))
    return dict(passed=not errors, errors=errors, groups=result, flush_ack_checked=flush_ack,
                flush_paths=flush_paths,
                bot_guard_checked=bot_guard, guard_paths=guard_paths,
                sdf=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                route_budget_ns=6.25,
                scope='84 liaisons Gray' + (' + 5 liaisons de purge' if flush_ack else '') +
                      (' + 5 liaisons BOT' if bot_guard else '') +
                      ', Q vers D ; routage uniquement')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdf', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--flush-ack', action='store_true')
    parser.add_argument('--bot-guard', action='store_true')
    args = parser.parse_args()
    report = audit(args.sdf, args.flush_ack, args.bot_guard)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    for name, group in report['groups'].items():
        print(name, group['found'], '/', group['expected'], 'max', group['max_route_ns'], 'ns')
    if not report['passed']:
        raise SystemExit('; '.join(report['errors']))
    print('PASS routage des 84 liaisons Gray MSC')
    if args.flush_ack:
        print('PASS 5 liaisons de purge, max',
              max(d for p in report['flush_paths'].values() for d in p['corners_ns']), 'ns')
    if args.bot_guard:
        print('PASS 5 liaisons BOT, max',
              max(d for p in report['guard_paths'].values() for d in p['corners_ns']), 'ns')


if __name__ == '__main__':
    main()
