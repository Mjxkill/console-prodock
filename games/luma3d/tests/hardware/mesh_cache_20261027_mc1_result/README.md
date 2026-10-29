# MC1 R3 — essai Pro Dock du 27 octobre 2026

**Contrôles fonctionnels PASS ; performance refusée ; cache non retenu. GM1 restauré et animé.**

Les huit oracles matériels et les huit fenêtres A/B/B/A sont terminés. Le résultat JSON contient `passed=true` pour la conduite et les contrôles fonctionnels, `performance_accepted=false`, `evidence_complete=true` et `candidate_promoted=false`. Il ne faut pas lire le code retour 0 comme une acceptation de performance.

## Identités et état final

- Bundle R3 : `122e5573e1f1d4d86642692213c34f97f25086c69cf417c2a2aa4b6efb47671c`.
- Contrôleur : `603774e4aa5adae1bb978ee659230b49479f5c09ff0d743b30482e56b788e76a`.
- GM1 restauré : `/tmp/luma3d-gm1 --showcase`, PID **3158**, startticks **27508908**.
- ELF GM1 : `df529a3463d6f3138895eeefb6ac70d149d7a714f51be74fb79a73079054e29b`.
- Candidat normal correspondant aux diagnostics : `8d2b54d7b4f3b2fa27628c019860f36c3299e0b574b733bc5684c29710df942a` ; non promu.
- Sauvegarde `/tmp/op2-live.save`, V4 : `2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6`, strictement identique avant/après.
- Pro Dock série11252024 sur ax15 ; G22r0 conservé par continuité de chargement, G3D1 contrôlé ; noyau `6.12.112-prodock-luma3d-g3d1-r1`.
- Aucune écriture FPGA, noyau, SD ou flash. Aucune intervention Neo.
- GM1 est une boucle autonome en arrière-plan avec stdin `/dev/null` : les touches du shell ne pilotent pas cette instance.
- Reprise : 31 PRESENT supplémentaires, identité complète après progression/publication puis après lecture de sauvegarde ; cinq compteurs DISPLAY à zéro.
- Contrôleur terminé. Vérification hôte sans UART : verrou acquis/libéré par `flock -n … true` (RC0), `fuser` du CDC vide (RC1).

La reprise normale et le nettoyage n’ont reçu aucun signal différé ni rencontré d’erreur de journalisation. Les limites opérationnelles du [plan figé](../mesh_cache_20261027_mc1_prepared_r3/PLAN_MC1.md) restent conservées.

## Débit et régularité en mouvement

Chaque ligne mesure 360 images après 2 images d’entrée et 12 au repos. Un seul pas logique de 1/60 s est exécuté par image : charge déterministe comparable, pas vitesse d’une visite en temps réel. Le démarrage et la relecture de trajet avant la fenêtre ne sont pas inclus.

| Scène | Ordre | FPS | p95 ≤ ms | p99 ≤ ms | Max ms / index | Publication + comparaison, s | Octets publiés |
|---|---|---:|---:|---:|---:|---:|---:|
| Maison | A1 GM1 | 12.47 | 112 | 132 | 147.74 / 73 | 3.754 | 21495360 |
| Maison | B1 cache | 11.70 | 120 | 148 | 152.66 / 68 | 5.349 | 7202240 |
| Maison | B2 cache | 11.22 | 128 | 148 | 163.86 / 148 | 5.610 | 7202240 |
| Maison | A2 GM1 | 12.14 | 112 | 136 | 147.02 / 130 | 4.072 | 21495360 |
| Exploration | A1 GM1 | 9.66 | 140 | 232 | 303.57 / 15 | 0.000 | 0 |
| Exploration | B1 cache | 9.66 | 136 | 220 | 272.91 / 16 | 0.000 | 0 |
| Exploration | B2 cache | 9.65 | 144 | 220 | 290.87 / 15 | 0.000 | 0 |
| Exploration | A2 GM1 | 9.77 | 132 | 240 | 294.05 / 15 | 0.000 | 0 |

Dans la maison, le candidat écrit **7 202 240 octets au lieu de 21 495 360**, soit 66,49 % de moins. Pourtant, la fonction de publication avec comparaison prend 5,349/5,610 s contre 3,754/4,072 s. La latence moyenne augmente de **6,57 % et 8,23 %** dans les deux paires. Ce chronométrage inclut validation, comparaison et écritures ; il n’isole pas un coût de `memcmp` ni un débit DDR brut.

En exploration, aucun octet ne passe par ce cache. Les deux paires donnent +0,0008 % et +1,1863 % de latence moyenne : aucun gain attribuable à cette modification.

## Entrée, repos et gardes fixées avant l’essai

| Scène / phase | Latence B/A, paire AB | Latence B/A, paire BA | Dérive symétrique A | Verdict de phase |
|---|---:|---:|---:|---|
| Maison / entry | +14.102 % | +10.791 % | 0.203 % | REFUS |
| Maison / rest | -5.477 % | +5.208 % | 3.830 % | REFUS |
| Maison / moving | +6.566 % | +8.229 % | 2.699 % | PASS garde |
| Exploration / entry | -6.962 % | -1.919 % | 2.997 % | PASS garde |
| Exploration / rest | +4.335 % | +4.326 % | 2.353 % | PASS garde |
| Exploration / moving | +0.001 % | +1.186 % | 1.096 % | PASS garde |

L’entrée de la maison dépasse la garde +10 % dans les deux paires ; le témoin au repos dérive de 3,83 %, au-delà de la garde 3 %. Le mouvement maison reste sous la tolérance de non-régression de +10 %, mais son ralentissement mesuré ne constitue évidemment pas un gain. Les seuils p99 (+25 % +4 ms) et maximum (+50 % +20 ms) passent. Les 2 images d’entrée et 12 au repos sont de petits échantillons, conservés tels quels ; aucune répétition opportuniste n’a été faite.

## Ventilation des phases en mouvement

| Scène / ordre | Simulation s | Préparation s | SUBMIT s | PRESENT appel s | feed s | wait s | cache s | PRESENT compteur s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Maison / A1 GM1 | 1.543 | 7.712 | 14.395 | 5.128 | 0.272 | 11.884 | 0.505 | 4.632 |
| Maison / B1 cache | 1.510 | 9.711 | 14.566 | 4.901 | 0.282 | 11.852 | 0.457 | 4.649 |
| Maison / B2 cache | 1.584 | 10.574 | 14.770 | 5.082 | 0.275 | 11.911 | 0.442 | 5.189 |
| Maison / A2 GM1 | 1.525 | 8.149 | 14.626 | 5.265 | 0.284 | 11.922 | 0.496 | 4.939 |
| Exploration / A1 GM1 | 1.397 | 4.240 | 26.932 | 4.604 | 17.629 | 4.533 | 0.933 | 4.362 |
| Exploration / B1 cache | 1.321 | 4.144 | 26.897 | 4.817 | 17.672 | 4.487 | 0.917 | 4.369 |
| Exploration / B2 cache | 1.363 | 4.366 | 26.960 | 4.517 | 17.668 | 4.467 | 0.891 | 4.183 |
| Exploration / A2 GM1 | 1.290 | 4.170 | 26.767 | 4.542 | 17.634 | 4.526 | 0.900 | 4.133 |

La publication fait partie de la préparation. Les compteurs pilote feed/wait/cache ne doivent pas être ajoutés à SUBMIT : ils en détaillent le chemin interne. Feed désigne l’alimentation mesurée dans le pilote, avec ses attentes éventuelles ; ce n’est pas un profil CPU exclusif. SUBMIT n’est pas intégralement du raster. Les frontières du compteur PRESENT pilote et de l’appel chronométré ne sont pas identiques ; les deux valeurs restent séparées. Les cycles géométrie sont conservés modulo32, sans conversion en durée GPU exclusive.

Commandes, batches, états finaux, mouvements, contacts, sommets et triangles concordent entre variantes. Maison en mouvement : 8 427 commandes /360 batches, compteurs G3D de 1 028 620 sommets, 247 542 triangles et 263 888 rejets. Exploration : 70 440 commandes /1 117 batches, 459 025 sommets, 229 747 triangles et 465 387 rejets. Les indices et la ventilation des huit images les plus lentes de chaque phase sont dans [analysis.json](analysis.json).

## Portée des preuves

- Huit oracles matériels : RGB publié, sources UI publiées, dernière géométrie ; restart et BACK inclus.
- Aucun écart de pixel/plage attendue, aucune erreur GPU/underflow/invalid layer/sprite/fault dans les contrôles.
- Le bundle lie aussi 80 images sélectionnées localement sur deux profils (commandes/codecs/32 MiB exacts), 16 fixtures RV32/QEMU et quatre fenêtres RV32.
- La carte n’a pas relu 70 dumps complets de 32 MiB, ni la palette/descripteurs/composition LCD finale ; aucune équivalence matérielle Neo déduite.
- Ce lot ne mesure pas une nouvelle boucle complète de jeu et ne qualifie pas 30/60 FPS.

## Archives

- [result.json](result.json) SHA-256 `ea923bfaf569e7dbadc936e9512cdf0cf8e9c30f6adbc59ef5e215fae5760197` ; empreinte remote puis copie locale identiques.
- [phase_costs.csv](phase_costs.csv) : toutes les phases et compteurs, unités explicites.
- [analysis.json](analysis.json) : comparaison, pics et identité finale sans duplication des octets de sauvegarde.
- Les journaux bruts, les refus de revue R2 et le bundle R3 restent conservés.
- [summarize_result.py](summarize_result.py) régénère ce rapport depuis le résultat figé, sans accès matériel.

Transfert RAM : 686,624 octets, 11 reprises de blocs, CRC finaux conformes. Ces reprises ne sont pas cachées ; elles précèdent les fenêtres silencieuses.
