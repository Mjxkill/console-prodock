#!/usr/bin/env python3
"""Rebuild MC1 documentation from the untouched hardware result; no device I/O."""
import csv
import hashlib
import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULT_SHA = 'ea923bfaf569e7dbadc936e9512cdf0cf8e9c30f6adbc59ef5e215fae5760197'
raw = (HERE / 'result.json').read_bytes()
assert hashlib.sha256(raw).hexdigest() == RESULT_SHA
r = json.loads(raw)
assert r['passed'] and r['functional_passed'] and r['evidence_complete']
assert not r['performance_accepted'] and not r['candidate_promoted']
assert r['restored_gm1'] and len(r['fixtures']) == len(r['windows']) == 8
assert r['save_initial']['sha256'] == r['save_final']['sha256']
assert r['final_identity'] == dict(pid=3158, start_ticks=27508908)
for d in [x['display'] for x in r['fixtures']] + [x['result']['display'] for x in r['windows']] + [r['restored_display']]:
    assert all(d[k] == 0 for k in ('errors', 'uf', 'invalid', 'sprites', 'fault'))

labels = ('A1 GM1', 'B1 cache', 'B2 cache', 'A2 GM1')
scenes = {4: 'Maison', 8: 'Exploration'}
rows = []
for index, w in enumerate(r['windows']):
    for p, c, driver in zip(w['result']['phases'], w['result']['copies'], w['result']['counters']):
        rows.append(dict(window=index, scene=scenes[w['kind']], variant=labels[index % 4], phase=p['name'],
                         **{k: p[k] for k in ('frames', 'wall', 'fps', 'simulation', 'preparation', 'submit', 'present', 'p95_upper_ms', 'p99_upper_ms', 'max_frame', 'max_index', 'commands', 'batches', 'state_crc32')},
                         **{k: c[k] for k in ('requested', 'published', 'compared', 'allocated', 'copy_seconds')},
                         **{k: driver[k] for k in ('feed_us', 'wait_us', 'cache_us', 'present_us', 'vertices', 'triangles', 'culled', 'slivers', 'cycles_mod32')}))
buf = io.StringIO()
writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
writer.writeheader()
writer.writerows(rows)
(HERE / 'phase_costs.csv').write_text(buf.getvalue())
summary = dict(result_sha256=RESULT_SHA, functional_passed=True, performance_accepted=False,
               candidate_promoted=False, final_identity=r['final_identity'], save_sha256=r['save_final']['sha256'],
               phases=rows, comparison=r['comparison'],
               peaks=[dict(window=i, scene=scenes[w['kind']], variant=labels[i % 4], rows=w['result']['top']) for i, w in enumerate(r['windows'])],
               scope='One fixed 60 Hz simulation tick per measured image; not a real-time showcase. Copy time is nested in preparation; driver counters are not exclusive CPU/GPU times.')
(HERE / 'analysis.json').write_text(json.dumps(summary, indent=2) + '\n')

lines = ['# MC1 R3 — essai Pro Dock du 27 octobre 2026', '',
         '**Contrôles fonctionnels PASS ; performance refusée ; cache non retenu. GM1 restauré et animé.**', '',
         'Les huit oracles matériels et les huit fenêtres A/B/B/A sont terminés. '
         'Le résultat JSON contient `passed=true` pour la conduite et les contrôles fonctionnels, '
         '`performance_accepted=false`, `evidence_complete=true` et `candidate_promoted=false`. '
         'Il ne faut pas lire le code retour 0 comme une acceptation de performance.', '',
         '## Identités et état final', '',
         '- Bundle R3 : `122e5573e1f1d4d86642692213c34f97f25086c69cf417c2a2aa4b6efb47671c`.',
         '- Contrôleur : `603774e4aa5adae1bb978ee659230b49479f5c09ff0d743b30482e56b788e76a`.',
         '- GM1 restauré : `/tmp/luma3d-gm1 --showcase`, PID **3158**, startticks **27508908**.',
         '- ELF GM1 : `df529a3463d6f3138895eeefb6ac70d149d7a714f51be74fb79a73079054e29b`.',
         '- Candidat normal correspondant aux diagnostics : `8d2b54d7b4f3b2fa27628c019860f36c3299e0b574b733bc5684c29710df942a` ; non promu.',
         '- Sauvegarde `/tmp/op2-live.save`, V4 : `2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6`, strictement identique avant/après.',
         '- Pro Dock série11252024 sur ax15 ; G22r0 conservé par continuité de chargement, G3D1 contrôlé ; noyau `6.12.112-prodock-luma3d-g3d1-r1`.',
         '- Aucune écriture FPGA, noyau, SD ou flash. Aucune intervention Neo.',
         '- GM1 est une boucle autonome en arrière-plan avec stdin `/dev/null` : les touches du shell ne pilotent pas cette instance.',
         '- Reprise : 31 PRESENT supplémentaires, identité complète après progression/publication puis après lecture de sauvegarde ; cinq compteurs DISPLAY à zéro.',
         '- Contrôleur terminé. Vérification hôte sans UART : verrou acquis/libéré par `flock -n … true` (RC0), `fuser` du CDC vide (RC1).', '',
         'La reprise normale et le nettoyage n’ont reçu aucun signal différé ni rencontré d’erreur de journalisation. '
         'Les limites opérationnelles du [plan figé](../mesh_cache_20261027_mc1_prepared_r3/PLAN_MC1.md) restent conservées.', '',
         '## Débit et régularité en mouvement', '',
         'Chaque ligne mesure 360 images après 2 images d’entrée et 12 au repos. '
         'Un seul pas logique de 1/60 s est exécuté par image : charge déterministe comparable, '
         'pas vitesse d’une visite en temps réel. Le démarrage et la relecture de trajet avant la fenêtre ne sont pas inclus.', '',
         '| Scène | Ordre | FPS | p95 ≤ ms | p99 ≤ ms | Max ms / index | Publication + comparaison, s | Octets publiés |',
         '|---|---|---:|---:|---:|---:|---:|---:|']
for x in rows:
    if x['phase'] == 'moving':
        lines.append(f"| {x['scene']} | {x['variant']} | {x['fps']:.2f} | {x['p95_upper_ms']:.0f} | {x['p99_upper_ms']:.0f} | {x['max_frame'] * 1000:.2f} / {x['max_index']:.0f} | {x['copy_seconds']:.3f} | {x['published']:.0f} |")
lines += ['', 'Dans la maison, le candidat écrit **7 202 240 octets au lieu de 21 495 360**, '
          'soit 66,49 % de moins. Pourtant, la fonction de publication avec comparaison prend '
          '5,349/5,610 s contre 3,754/4,072 s. La latence moyenne augmente de **6,57 % et 8,23 %** '
          'dans les deux paires. Ce chronométrage inclut validation, comparaison et écritures ; '
          'il n’isole pas un coût de `memcmp` ni un débit DDR brut.', '',
          'En exploration, aucun octet ne passe par ce cache. Les deux paires donnent '
          '+0,0008 % et +1,1863 % de latence moyenne : aucun gain attribuable à cette modification.', '',
          '## Entrée, repos et gardes fixées avant l’essai', '',
          '| Scène / phase | Latence B/A, paire AB | Latence B/A, paire BA | Dérive symétrique A | Verdict de phase |',
          '|---|---:|---:|---:|---|']
for scene in r['comparison']:
    for p in scene['phases']:
        pairs=p['pairs']
        lines.append(f"| {scenes[scene['kind']]} / {p['name']} | {(pairs[0]['mean_frame_ratio']-1)*100:+.3f} % | {(pairs[1]['mean_frame_ratio']-1)*100:+.3f} % | {(p['baseline_symmetric_drift_ratio']-1)*100:.3f} % | {'PASS garde' if p['accepted'] else 'REFUS'} |")
lines += ['', 'L’entrée de la maison dépasse la garde +10 % dans les deux paires ; '
          'le témoin au repos dérive de 3,83 %, au-delà de la garde 3 %. '
          'Le mouvement maison reste sous la tolérance de non-régression de +10 %, '
          'mais son ralentissement mesuré ne constitue évidemment pas un gain. '
          'Les seuils p99 (+25 % +4 ms) et maximum (+50 % +20 ms) passent. '
          'Les 2 images d’entrée et 12 au repos sont de petits échantillons, conservés tels quels ; '
          'aucune répétition opportuniste n’a été faite.', '',
          '## Ventilation des phases en mouvement', '',
          '| Scène / ordre | Simulation s | Préparation s | SUBMIT s | PRESENT appel s | feed s | wait s | cache s | PRESENT compteur s |',
          '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for x in rows:
    if x['phase'] == 'moving':
        vals=[x[k] for k in ('simulation','preparation','submit','present')]+[x[k]/1e6 for k in ('feed_us','wait_us','cache_us','present_us')]
        lines.append('| '+x['scene']+' / '+x['variant']+' | '+' | '.join(f'{v:.3f}' for v in vals)+' |')
lines += ['', 'La publication fait partie de la préparation. Les compteurs pilote feed/wait/cache '
          'ne doivent pas être ajoutés à SUBMIT : ils en détaillent le chemin interne. '
          'Feed désigne l’alimentation mesurée dans le pilote, avec ses attentes éventuelles ; '
          'ce n’est pas un profil CPU exclusif. SUBMIT n’est pas intégralement du raster. '
          'Les frontières du compteur PRESENT pilote et de l’appel chronométré ne sont pas identiques ; '
          'les deux valeurs restent séparées. Les cycles géométrie sont conservés modulo32, sans conversion en durée GPU exclusive.', '',
          'Commandes, batches, états finaux, mouvements, contacts, sommets et triangles concordent entre variantes. '
          'Maison en mouvement : 8 427 commandes /360 batches, compteurs G3D de 1 028 620 sommets, 247 542 triangles et 263 888 rejets. '
          'Exploration : 70 440 commandes /1 117 batches, 459 025 sommets, 229 747 triangles et 465 387 rejets. '
          'Les indices et la ventilation des huit images les plus lentes de chaque phase sont dans [analysis.json](analysis.json).', '',
          '## Portée des preuves', '',
          '- Huit oracles matériels : RGB publié, sources UI publiées, dernière géométrie ; restart et BACK inclus.',
          '- Aucun écart de pixel/plage attendue, aucune erreur GPU/underflow/invalid layer/sprite/fault dans les contrôles.',
          '- Le bundle lie aussi 80 images sélectionnées localement sur deux profils (commandes/codecs/32 MiB exacts), 16 fixtures RV32/QEMU et quatre fenêtres RV32.',
          '- La carte n’a pas relu 70 dumps complets de 32 MiB, ni la palette/descripteurs/composition LCD finale ; aucune équivalence matérielle Neo déduite.',
          '- Ce lot ne mesure pas une nouvelle boucle complète de jeu et ne qualifie pas 30/60 FPS.', '',
          '## Archives', '',
          f'- [result.json](result.json) SHA-256 `{RESULT_SHA}` ; empreinte remote puis copie locale identiques.',
          '- [phase_costs.csv](phase_costs.csv) : toutes les phases et compteurs, unités explicites.',
          '- [analysis.json](analysis.json) : comparaison, pics et identité finale sans duplication des octets de sauvegarde.',
          '- Les journaux bruts, les refus de revue R2 et le bundle R3 restent conservés.',
          '- [summarize_result.py](summarize_result.py) régénère ce rapport depuis le résultat figé, sans accès matériel.', '',
          f"Transfert RAM : {sum(t['bytes'] for t in r['transfers']):,} octets, {sum(t['retries'] for t in r['transfers'])} reprises de blocs, CRC finaux conformes. "
          'Ces reprises ne sont pas cachées ; elles précèdent les fenêtres silencieuses.', '']
(HERE / 'README.md').write_text('\n'.join(lines))
