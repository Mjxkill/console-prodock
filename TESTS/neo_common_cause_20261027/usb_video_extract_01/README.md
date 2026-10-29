# Extraction hors carte UTNA et vidéo

Cet outil lit les journaux du contrôleur `../usb_video_trial_prepared` sans
importer ses fonctions matérielles. Il n’accède à aucune carte et n’écrit que
dans un nouveau répertoire de résultats. Le contrôleur en revue reste intact.

```sh
python3 TESTS/neo_common_cause_20261027/usb_video_extract_01/extract.py \
  --r19-log <essai>/r19_usb_video.log \
  --candidate-log <essai>/coupled_usb_video.log \
  --trial-result <essai>/result.json \
  --out <nouveau-dossier>
```

Les noms réels des journaux sont à reprendre dans le résultat du contrôleur.
`--trial-result` vérifie leur SHA et leur répertoire ; il conserve séparément
la qualification globale et l’état de restauration. Sans cette option, la
provenance matérielle du journal n’est pas affirmée. Un journal incomplet ou
incohérent produit un rapport avec ses erreurs et un code de sortie 1 ; une
erreur de provenance bloque l’extraction avant création du dossier de sortie.

`comparison.md` donne les valeurs parallèles R19/candidat. `result.json`
conserve les mots bruts, lignes de provenance, séquences/états d’ACK,
horodatages hôte et tous les contrôles. `capture_consistent` signifie seulement
que les données du journal satisfont le protocole ; ce n’est pas un PASS USB,
vidéo, timing ou matériel. Une vidéo qui ne compte aucune image peut donc
constituer une capture cohérente d’un dysfonctionnement.

## Indices vérifiés dans les sources figées

Le programme vérifie la concaténation réelle de `usb_idle_trace.v`, son SHA
`97854f943d523304877e4fafc52c53e71ef03cb3e54940f13cd1a7a0bdbe8d9f`
et l’identité du fichier R19/R21r2. Il vérifie également les expressions du
multiplexeur de lecture `gpu_scanout.v` et journalise son SHA.

| Banque UTNA, mot | Signification exacte |
|---:|---|
| 0 / 1 / 2 | ID `55544e41` / version 1 / commande capturée |
| 3 | Cycles armés `ticks` |
| 13 | Cycles avec `rx_error_sample` affirmé pendant l’armement |
| 15 | Fronts montants observés de `bus_reset_sample` pendant l’armement |
| 16 | Cycles avec `sof_sample` affirmé pendant l’armement |
| 17 | Cycles armés avec `tx_valid_sample && !tx_ready_sample` |
| 31 | `armed` bit 10, `pending` bit 9, adresse cible bits 6:0 |

Les trois mots de contrôle MMIO ID/statut/séquence sont des registres de
contrôle vivants, distincts de cette banque. Les compteurs vidéo utiles sont
les mots 6 (images), 7 (underflows), 24 (somme affichée). Le mot 1 est la base
shadow, **pas le mode** ; le mode shadow est au mot 2.

Le protocole attendu est 1/6/2/2. ARM capture l’état avant effacement.
DISARM capture l’ancien état armé et son nombre de cycles ; l’ultime cycle
armé conduit à `ticks(STOPPED) = ticks(DISARM)+1 modulo 2^32`. STABLE conserve
ce nombre. Chaque banque doit être identique sur deux lectures et encadrée
par des statuts idle/séquence attendus.

L’heure `UTNA_WRITE` précède l’écriture MMIO : elle ne date pas exactement le
front de capture FPGA. Aucun calcul de fréquence physique ni de verrouillage
PLL n’est déduit. Un compteur USB nul ne prouve pas l’absence de reset CPU,
PLL ou USB en dehors de la fenêtre. Aucune énumération HS n’est inférée.
Les compteurs RX error/TX stall représentent des cycles, pas des paquets.
Les captures dynamiques NCP non qualifiées ne sont pas utilisées.

## Tests hors carte

`tests_02/result.json` : 20 contrôles PASS. Les données de test sont
**synthétiques** : les traces de protocole proviennent des mocks Tcl déjà
exécutés, leurs valeurs vidéo sont remplacées explicitement dans des copies.
Des sentinelles distinctes aux indices 12 à 19 détectent un décalage silencieux
de décodage ; elles ne représentent pas un trafic mesuré. Les contre-tests
couvrent mots invalides ou trop larges, en-tête/séquence erronés, banque
instable, tick final erroné, temps inversés, doublon, absence de marqueur,
capture partielle, faute déclarée et manifeste SHA altéré. Six journaux
d’échec du Tcl exact sont également rejetés après adaptation des seuls mocks
d’identité vidéo. Aucune simulation RTL ni suite commune n’est revendiquée
par ces tests de parsing. La première campagne `tests_01` est conservée ; la
seconde lie le comportement final de code de sortie aux empreintes finales.
