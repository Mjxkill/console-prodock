#!/usr/bin/env python3
"""Archive a completed PASS trial, without any device or network access."""
from pathlib import Path
import argparse,hashlib,json,re
p=argparse.ArgumentParser();p.add_argument('--trial',type=Path,required=True);a=p.parse_args();out=a.trial.resolve();r=json.loads((out/'result.json').read_text())
assert r['passed'] and r['comparison']['accepted'] and r['amber']['phase']==5 and r['amber']['region']==0
assert r['save_before_resume']['sha256']==r['save_after_resume']['sha256']
assert r['baseline_v2']['sha256']==r['baseline_v2_final']['sha256']
identity=re.search(r'^(\d+) \(luma3d-am1\) ([^\r\n]+)',r['live_identity'],re.M);assert identity
pid=int(identity[1]);start=int(identity[2].split()[19]);assert identity[2].split()[0] not in ('Z','X')
for key in ('baseline_v2','baseline_v2_final','save_before_resume','save_after_resume'):
 data=bytes.fromhex(r[key]['hex']);assert hashlib.sha256(data).hexdigest()==r[key]['sha256']
 path=out/(key+'.save')
 if path.exists():assert path.read_bytes()==data
 else:path.write_bytes(data)
assert 'PRODOCK_LOCK_FREE' in (out/'ax15_release.log').read_text()
lines=['Les Terrasses d’ambre R9 — essai Pro Dock am1','',
 'PASS fonctionnel. Nouveau jeu laissé en visite automatique :',
 f'/tmp/luma3d-am1, PID {pid}, startticks {start}.',
 'Ancre /tmp/luma3d-live.pid ; sauvegarde visible /tmp/am1-live.save, V3, volatile.',
 'Le lancement --advance 10730 effectue réellement ces pas de simulation pour',
 'commencer aux Terrasses. La visite rejoint Nora/Nils puis revient à la vallée ;',
 'ce n’est pas une boucle qui reste indéfiniment dans la nouvelle région.',
 'Son entrée est fermée : les commandes clavier nécessitent une relance interactive.',
 'Ws1 /tmp/luma3d-ws1 et /tmp/ws1-live.save V2 sont conservés pour retour.',
 'Aucun NEBULA. Aucun changement FPGA, noyau, SD ou flash.',
 'Contrôleur terminé ; aucun propriétaire CDC retourné et verrou diagnostic libre.',
 'FPGA G22r0 conservé par continuité d’état ; noyau '+r['kernel']+'.',
 'Aucun nouveau chargement ou lecture JTAG ; identité processus/noyau/ABI vérifiée,',
 'signature G3D contrôlée à chaque ouverture du moteur.',
 '', 'ELF : '+r['game']['sha256'],f"{r['game']['bytes']} octets ; CRC32 {r['game']['crc32']}.",
 'Manifeste essai : '+r['manifest_sha256'],
 'Résultat JSON : '+hashlib.sha256((out/'result.json').read_bytes()).hexdigest(),
 f"Transport RAM : {sum(t['bytes'] for t in r['transfers'])} octets, {sum(t['retries'] for t in r['transfers'])} retransmissions de blocs, CRC finaux validés.",'',
 'Sept scènes : 30 images mesurées après 3 de chauffe, aucune écriture UART',
 'entre lancement et marqueur EXIT. Pixels 96 000 et banques HUD exacts pour',
 'chaque référence. Le CRC des indices HUD n’est pas une photographie du LCD ;',
 'palettes et descripteurs sont couverts par les contrats locaux.',
 'Les poses --advance sont des fixtures distinctes du parcours réel ci-dessous.',
 '', 'Version | Pose | FPS | Commandes/image | Batches/image | DRAW/image | Faces soumises/image']
for s in r['scenes']:
 x=s['result'];lines.append(f"{s['variant']} | {s['pose']} | {x['fps']:.2f} | {x['commands']/x['frames']:.0f} | {x['batches']/x['frames']:.0f} | {x['draws_last']} | {x['triangles_last']}")
c=r['comparison'];e=r['endurance'];g=r['endurance_counters']
lines += ['',f"Temps/image arrivée R9 : {c['arrival_slowdown']*100:+.2f} % par rapport au témoin initial.",
 f"Dérive témoin finale : {c['witness_drift']*100:+.2f} % selon la formule figée.",
 'Les gardes prédéfinies +10 % / dérive absolue 5 % passent. Aucun gain ni',
 'percentile stable revendiqué. R9 ajoute un passage, les images diffèrent de ws1.',
 '', 'Parcours depuis une nouvelle partie, sans --advance : courrier, atelier,',
 'retour à Maëlle, entrée des Terrasses, Nora, prise/vanne, passerelle, Nils,',
 'retour à Nora puis retour réel dans la vallée. État final ambre5/région0,',
 'prise1/vanne2, courrier4/relais3/4lettres et atelier4/mode5 vérifiés.',
 'Fenêtre de 300 s sans écriture UART après démarrage ; processus encore vivant',
 'à la fin, arrêté proprement pour lire les compteurs et le fichier.',
 f"Total processus : {e['frames']} images / {e['elapsed']:.3f} s = {e['fps']:.2f} FPS ; simulation {r['story']['sim']:.2f} s.",
 'Ce total inclut les contrôles autour de la fenêtre, pas une mesure isolée des',
 '300 s ni une durée humaine de découverte. Aucun objectif 30 FPS atteint.',
 f"Erreurs GPU/géométrie/underflows/fault : zéro ; {g['slivers']} sliver(s) écarté(s).",'',
 'Sauvegarde /tmp/am1-progress.save : V3, 136 octets. Reprise manuelle d’une',
 'image avec octets strictement identiques : '+r['save_before_resume']['sha256']+'.',
 'Sauvegarde V2 ws1 identique avant/après : '+r['baseline_v2']['sha256']+'.',
 'Les quatre fichiers relus sont archivés à côté. Le stockage /tmp reste volatil.',
 '', 'Limites : deux petites régions, trois missions courtes, modèles simples et',
 'personnages en partie dérivés. Pas de campagne de plusieurs heures, combat,',
 'véhicules ou son 3D intégré. Les ressources restent résidentes ; les objets',
 'et animations d’eau de la région inactive sont exclus du rendu, sans prétendre',
 'disposer déjà du streaming d’un grand monde. Aucun essai Neo qualifié ici.',
 'Les échecs/archives antérieurs et les sauvegardes ws1/sf2 restent préservés.']
(out/'REPORT.txt').write_text('\n'.join(lines)+'\n')
files={str(f.relative_to(out)):dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='archive_manifest.json'}
(out/'archive_manifest.json').write_text(json.dumps(dict(files=files),indent=2)+'\n')
print(json.dumps(dict(pid=pid,start_ticks=start,fps=e['fps'],result_sha256=files['result.json']['sha256'],evidence_files=len(files)),indent=2))
