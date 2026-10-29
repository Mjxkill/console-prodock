#!/usr/bin/env python3
import hashlib,json,re
from pathlib import Path
root=Path(__file__).resolve().parent;r=json.loads((root/'result.json').read_text());end=json.loads((root/'final_identity.json').read_text())
assert not r['passed'] and r['restored_am1'] and end['pid']==1754
bench=r['benchmarks'];assert len(bench)==3 and not r['fixtures']
for k in ('errors','uf','invalid','sprites','fault'):assert end['display'][k]==0
pixel=(root/'op1_garden_pixels.log').read_text();assert 'pixels=96000 mismatch=28' in pixel
text=f'''OP1 — FAIL conservé, retour am1 terminé

Lot utilisateur : amber_paths_20261026_r4
ELF : {r['game']['sha256']}
Contrôleur : manifeste {r['manifest_sha256']}
Pilote de diagnostic séparé : {r['probe']['sha256']}

La pose d’arrivée passe les 96 000 pixels RGB565 et les deux banques HUD :
am1 initial {bench[0]['result']['fps']:.2f} FPS, candidat {bench[1]['result']['fps']:.2f} FPS,
am1 final {bench[2]['result']['fps']:.2f} FPS. Chaque mesure comprend 30 images après
3 images de chauffe, pose/animations figées, sans commande UART pendant
la fenêtre. Aucun gain ni percentile stable n’est annoncé. Les commandes
et compteurs géométriques attendus passent ; la garde de régression passe.

La première fixture, le jardin, charge un vrai fichier V4 et dessine trois
images. Comptes exacts : 189 commandes, 4 batches, 19 DRAW sur la dernière
image, 1 048 faces soumises ; 2 076 sommets transformés et 564 triangles raster
sur les trois images. Descripteurs/palette côté CPU conformes ; zéro erreur
GPU, géométrie et underflow. La comparaison RGB565 échoue : 28 différences
sur 96 000 pixels, CRC réel e89849b6 contre 7c0ccf51. Les premières différences
sont de petites variations de couleurs vertes. Leur cause n’est pas encore
établie : ni un défaut matériel ni une différence CPU/oracle ne sont déduits
de ce seul constat. Le test n’a pas été assoupli ou répété.

La maison, les cinq activités, le replay physique et les reprises matérielles
suivantes n’ont PAS été exécutés. Les PASS locaux antérieurs restent des
preuves locales. Le protocole aurait repris les défis à leur entrée ; les
426 images prévues échantillonnaient une simulation accélérée, avec certains
coups dt=0 sans image intermédiaire. Il ne s’agissait pas d’une mesure de
durée humaine ou de fluidité du parcours.

État final lu après récupération :
/tmp/luma3d-am1, PID {end['pid']}, startticks {end['start_ticks']}.
Sauvegarde active : {end['save']} (copie V3, RAM volatile).
Le compteur presents avance et les cinq compteurs d’erreur d’affichage sont
nuls. L’original /tmp/am1-live.save est conservé, SHA
{end['original_v3_sha256']},
CRC relu {end['original_v3_crc32_verified']}. Aucun retour NEBULA.
CDC11252024 et /tmp/prodock-diagnostic.lock ont été libérés et vérifiés libres.
FPGA G22r0 et noyau G3D1 inchangés ; zéro écriture FPGA/noyau/SD/flash.

Le paquet op1 est consommé : ne pas le relancer avec ses noms/PID/save périmés.
Le diagnostic suivant reste local ; tout nouvel essai exigera un nouveau
paquet, une identité fraîche et la revue du changement concret.
'''
(root/'REPORT.txt').write_text(text)
(root/'baseline_v3.save').write_bytes(bytes.fromhex(r['baseline_save']['hex']))
(root/'release.txt').write_text('PRODOCK_LOCK_FREE\nCDC11252024: no fuser owner after final read-only identity check.\n')
files={str(p.relative_to(root)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(root.rglob('*')) if p.is_file() and p.name!='archive_manifest.json'}
(root/'archive_manifest.json').write_text(json.dumps(dict(passed=False,restored_am1=True,files=files),indent=2)+'\n');print(root/'REPORT.txt')
