# N56r2 : proposition de placement ciblée sur N56r1

Préparée le 21 octobre 2026 ; aucun routage ni accès matériel exécuté par cette
préparation. Le contrôle de la carte appartient à la tâche principale.

## Périmètre exact

Le parent est `tang/impl/console_neo_n56r1`, dont le bitstream diagnostic est
`426389b02a4c1c240a28a711546569315e5c4d9478199f12e1e38f46009d3d2d`.
N56r1 présente trois violations setup : −0,440, −0,065 et −0,049 ns.
Il n'est donc pas qualifié pour exploitation, malgré les premiers résultats
matériels de configuration positifs rapportés par la tâche principale.

Le candidat ajoute seulement quatre lignes `INS_LOC` au CST. Les deux premiers
placements concernent les deux étages d'un même synchroniseur d'observation.
Les trois lignes `CLOCK_LOC ... LOCAL_CLOCK` de N56r1 sont conservées exactement.
Le netlist de synthèse, les RTL, la DDR 5.9/300 MHz, le SDC, les fréquences,
la cible FPGA, les options de placement et de routage restent identiques.
Gowin recalculera toutefois le placement et le routage de l'ensemble : quatre
contraintes ajoutées ne signifient pas quatre seuls sites physiques modifiés.

Netlist SHA-256 :
`c05e9b7a4bcafba8cd31e4b985b4ba37ace8ecbd0e4b999745ac60d7a5fb461d`.
SDC SHA-256 :
`c8da535e839157a361e78b06b2f65b2912891f8e9dc48b02d5b315ae9f953113`.

## Choix de placement

| Chemin parent | Observation mesurée | Placement proposé | Effets à revérifier |
|---|---|---|---|
| `packet_17_s0/Q` → `observe_words_s1_49_s0/D`, −0,440 ns | Source R51C41, destination R50C136 ; fil 8,131 ns, contrainte CDC 8 ns | Les étages `s1_49` et `s2_49` dans R48:52/C65:70 | Entrée s1, résolution s1→s2, puis s2→`hrdata_17_s0` et recovery/removal du reset |
| `st_1_s0/Q` → `m_hrdata_3_s0/CE`, −0,065 ns | Source R4C150, LUT `n63_s0` R66C46, destination R68C138 ; fils 7,128 + 4,574 ns | LUT `n63_s0` dans R25:40/C135:150 | Ses trois entrées et les 32 CE `m_hrdata[31:0]` |
| `v1_select_s0/Q` → `state_13_s0/D`, −0,049 ns | Source R56C61, premier LUT R38C23 ; fil d'entrée 5,876 ns ; propriétaire à 466 charges | Premier LUT `n22637_s33` dans R40:50/C35:45 | Quatre entrées et les 51 bits d'état accessibles par son cône combinatoire |

Le synchroniseur reste à deux bascules. Contraindre les deux bascules dans la
même petite région évite de déplacer uniquement le premier étage et de laisser
le second à l'autre bout de la puce. La proximité effective et le timing doivent
encore être mesurés après routage. Il ne s'agit pas d'une capture atomique du bus.

Pour le pont CPU, deux des pilotes d'entrée du LUT sont explicitement fixés à
R4C150 par le CST existant. Les destinations rapportées sont autour de R68:70,
C136:139. Le détour horizontal par C46 ne suit donc pas la géométrie naturelle
de ce cône. La position du troisième pilote `st_3_s1` n'est pas publiée dans les
1 000 chemins setup disponibles : ce pilote reste à contrôler après routage.

Pour le pixel, déplacer le propriétaire `v1_select` à 466 charges toucherait de
nombreux consommateurs. Le déplacement choisi concerne seulement un LUT à six
charges directes, intermédiaire entre le propriétaire et les étages de décodage.
Il existe un compromis entre son entrée et ses sorties ; aucun gain en ns n'est
promis avant mesure. Les positions des trois autres pilotes du LUT ne figurent
pas dans ce rapport et ne sont pas déduites artificiellement.

## Vérification des chemins voisins

`placement_proof.json` conserve les primitives, les INIT et les connexions des
quatre éléments dans le netlist synthétisé et le netlist routé du parent. Il
liste leurs pilotes directs, charges directes et tous les endpoints séquentiels
atteints à travers LUT/MUX. Aucun cône de sortie de ces quatre éléments n'est
tronqué par une primitive non prise en charge : 1, 1, 32 et 51 endpoints.

Les chemins setup publiés passant par le LUT du pont CPU ont les marges
−0,065 / +0,017 / +0,104 ns vers `m_hrdata` 3, 29 et 7.
Le LUT pixel figure dans 41 chemins publiés ; le pire est −0,049 ns et le suivant
+0,524 ns. Dix de ses 51 endpoints ne sont donc pas individuellement caractérisés
par cette sélection de rapport. Les chemins s1→s2 et s2→`hrdata_17` ne sont pas
publiés non plus. Leur absence ne constitue pas une preuve de marge.

La qualification complète après routage devra vérifier setup, hold, recovery,
removal, les audits structurels DDR/horloges/CDC, la conservation des trois
contrôles locaux et la résolution effective des quatre régions. Elle devra
également rechercher de nouveaux endpoints négatifs hors des cônes ciblés.

## Préparation et lancement soumis à revue

Préparation exécutée avec succès :

```sh
python3 TESTS/neo_720p_20261012/n55_gpu_diagnosis_20261021/build_timing_placement.py --prepare-only
```

Le constructeur appelle `before_build('neo', candidate=True)`, vérifie les
sources figées contre `sources.json`, l'audit DDR, les empreintes des preuves
de N56r1 et l'empreinte du compilateur. Les quatre noms et types de primitives
sont résolus dans les deux netlists ; aucune contrainte existante n'est écrasée.

Manifeste préparé SHA-256 :
`e9b1715b50309be524aa2d603057eb1be3ad9cb5abba8b16a763ecaf66ad4e23`.
Une seconde lecture indépendante des entrées et des preuves préparées a confirmé
leur identité, ainsi que la garde commune toujours courante. Le constructeur
exige cette empreinte pour construire et refuse une dérive des entrées, du
script, des preuves ou du compilateur après préparation.

Commande proposée à la tâche principale, **non exécutée ici** :

```sh
python3 TESTS/neo_720p_20261012/n55_gpu_diagnosis_20261021/build_timing_placement.py --build-reviewed e9b1715b50309be524aa2d603057eb1be3ad9cb5abba8b16a763ecaf66ad4e23
```

## Limites fonctionnelles

Les résultats de configuration positifs de N56r1 ne suffisent pas à qualifier
le rendu GPU. Trois autres contrôles de géométrie restent en LW, sans modification
dans cette expérience : `n56864_3` (matériau), `n57378_3` (near/viewport),
`n59467_5` (faces). Leur fonction en rendu n'est pas prouvée par les treize seules
commandes de configuration. Aucune conclusion d'erratum matériel n'est tirée.
