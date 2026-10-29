#!/usr/bin/env python3
"""Generate navigation by board without moving frozen or shared source files."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'ARCHI/CARTES'


def link(path, base):
    return os.path.relpath(path, base)


def main():
    ownership = json.loads((ROOT / 'tang/boards/ownership.json').read_text())
    inventory = json.loads((HERE / 'build_inventory.json').read_text())
    bits = json.loads((HERE / 'bitstreams.json').read_text())['files']
    deleted = json.loads((HERE / 'deletion_candidates.json').read_text())['files']
    removed = Counter()
    for row in deleted:
        if not (ROOT / row['path']).exists():
            removed[row['build']] += row['size']
    counts = Counter(v['owner'] for v in ownership['files'].values())
    special = {
        'gpu_geometry_g22r0': 'Référence historique Pro Dock protégée. Setup −0,564 ns ; limites USB documentées. Le statut référence ne vaut pas timing PASS.',
        'console_neo_n56r19_capture_ce_local': 'Diagnostic Neo actuellement chargé le 26 octobre après coupure utilisateur. Mire visible et JTAG actif ; CPU arrêté. GPU complet non qualifié ; CLEAR natif bloquait dans les essais historiques. Timing FAIL.',
        'console_neo_n56r8_hdmi_sg4': 'Repli Neo pour la mire HDMI, conservé. Ne qualifie pas le framebuffer DDR ni le GPU complet.'}
    board_intro = {
        'commun': ('Sources communes', 'Le GPU, les adaptateurs de bus et les pilotes partagés restent uniques. Le préfixe « prodock » d’un pilote ne suffit pas à le classer spécifique à cette carte.'),
        'neo': ('Tang Console Neo 138K', 'Sortie HDMI 1280×720. Les expériences de portage restent dans les snapshots Neo et dans tools/neo. DDR 5.9/300 MHz conservée pour le diagnostic R19.'),
        'prodock': ('Tang Mega Pro Dock 138K', 'Sortie LCD 800×480. La référence FPGA G22r0 et le paquet NEBULA R17 restent protégés ; le jeu courant est un candidat logiciel distinct.'),
        'archives': ('Builds historiques non classés', 'Ces dossiers sont conservés et inventoriés ; leur nom ou leur ancienneté ne constitue pas une preuve de validation matérielle.')}
    for category, (title, intro) in board_intro.items():
        directory = OUT / category
        directory.mkdir(parents=True, exist_ok=True)
        owner = 'shared' if category == 'commun' else category
        sources = [{**v, 'path': k} for k, v in ownership['files'].items() if v['owner'] == owner]
        wanted = 'historical_unclassified' if category == 'archives' else category
        builds = []
        for row in inventory:
            if row['category'] != wanted:
                continue
            build = dict(row)
            build['path'] = 'tang/impl/' + row['name']
            build['cleanup_bytes_removed'] = removed[row['name']]
            build['logical_bytes_after_cleanup'] = row['bytes'] - removed[row['name']]
            build['bitstreams'] = [{k: b[k] for k in ('path', 'size', 'digest')}
                                  for b in bits if b['build'] == row['name']]
            build['qualification_note'] = special.get(row['name'],
                'Snapshot historique/candidat ; présence du bitstream et compilation terminée ne valent pas validation de timing ou de carte.')
            builds.append(build)
        data = dict(schema=1, category=category, source_of_truth='tang/boards/ownership.json',
                    ownership_sha256=hashlib.sha256((ROOT / 'tang/boards/ownership.json').read_bytes()).hexdigest(),
                    sources=sources, builds=builds,
                    note='Navigation only. Original paths and shared source uniqueness preserved. No release promotion.')
        (directory / 'catalogue.json').write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
        lines = [f'# {title}', '', intro, '', '[Retour à la carte du dépôt](../README.md)', '',
                 'Catalogue détaillé : [catalogue.json](catalogue.json).', '']
        if category in ('neo', 'prodock'):
            lines += ['Les [sources communes](../commun/README.md) complètent cette liste.', '']
        if category == 'neo':
            for p, label in [('tang/boards/neo/console_neo.v', 'Top Neo'), ('tang/boards/neo/neo.cst', 'Brochage et placement'),
                             ('tang/boards/neo/neo.sdc', 'Contraintes temporelles'), ('tools/build_console_neo.py', 'Constructeur Neo'),
                             ('TESTS/neo_720p_20261012/local_capture_20261026/handoff.json', 'État du diagnostic R19')]:
                lines.append(f'- [{label}]({link(ROOT / p, directory)})')
            lines.append('')
        if category == 'prodock':
            for p, label in [('tang/boards/prodock/reference.json', 'Empreintes et fichiers protégés'),
                             ('TESTS/prodock_restore_20261021/README.md', 'Restauration matérielle de référence'),
                             ('games/luma3d/candidates/arcade_polish_r1/PLAN.md', 'Jeu en cours de refonte')]:
                lines.append(f'- [{label}]({link(ROOT / p, directory)})')
            lines.append('')
        if sources:
            lines += [f'## {len(sources)} entrées de développement', '', '| Fichier unique | Type |', '|---|---|']
            for s in sources:
                lines.append(f"| [{s['path']}]({link(ROOT / s['path'], directory)}) | {s['kind']} |")
            lines.append('')
        if builds:
            lines += [f'## {len(builds)} dossiers de construction', '',
                'Les chemins historiques restent en place : les scripts, Tcl et preuves les référencent. Les déplacer sans migration de ces dépendances casserait la reproductibilité.', '',
                '| Snapshot | FS conservés | Taille après nettoyage | Protection / état |', '|---|---:|---:|---|']
            for b in builds:
                state = special.get(b['name'], 'Conservé : dépendance ou référence' if b['protection'] else 'Historique, sources et rapports conservés')
                lines.append(f"| [{b['name']}]({link(ROOT / b['path'], directory)}) | {len(b['bitstreams'])} | {b['logical_bytes_after_cleanup'] / 2**20:.1f} Mio | {state} |")
        (directory / 'README.md').write_text('\n'.join(lines) + '\n')
    (OUT / 'README.md').write_text('''# Carte du dépôt : commun, Pro Dock, Neo

Cette navigation sépare les responsabilités sans dupliquer les sources ni déplacer
les snapshots figés. L’inventaire machine de référence reste
[ownership.json](../../tang/boards/ownership.json).

| Ensemble | Entrées | Point d’entrée |
|---|---:|---|
''' + f"| Commun | {counts['shared']} | [GPU, bus, pilotes et outils partagés](commun/README.md) |\n"
        + f"| Pro Dock | {counts['prodock']} | [Sources, référence protégée et builds LCD](prodock/README.md) |\n"
        + f"| Neo | {counts['neo']} | [Sources, substitutions et builds HDMI](neo/README.md) |\n"
        + '''| Historique non classé | — | [Catalogue conservé](archives/README.md) |

Les sources de développement, les copies figées de construction et les preuves
de test sont trois ensembles distincts. Un fichier de snapshot Neo peut différer
du source commun : le catalogue ne prétend pas les rendre équivalents.

Références protégées : Pro Dock **G22r0 / NEBULA R17**. La Neo **N56r19** reste
un diagnostic avec mire et JTAG fonctionnels ; son GPU complet et son timing
ne sont pas qualifiés. N56r8 reste un repli HDMI.

- [Règles de compatibilité](../COMPATIBILITE_CARTES.md)
- [Revue des grands fichiers HDL](../../TESTS/hdl_inventory_20261026/analysis/REVIEW.txt)
- [Nettoyage exécuté et journal](../../TESTS/cleanup_20261026_gowin_inventory/README.md)

Les chemins des sources et snapshots restent ceux des constructeurs. Les caches
PnR retirés des anciens builds imposeraient un reroutage complet pour les reprendre ;
leurs sources, netlists, timing, bitstreams et rapports restent disponibles.
''')
    print(json.dumps(dict(source_counts=dict(counts), catalogues=4, sources_moved=0,
                          snapshots_moved=0, duplicate_sources_created=0)))


if __name__ == '__main__':
    main()
