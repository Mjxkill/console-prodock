# Gowin Workbench

Chaîne locale de compilation, d'analyse et d'expérimentation du placement,
développée pendant le port de la console vers la Tang Neo 138K. Elle complète
Gowin et propose aussi un parcours libre Yosys → nextpnr → Apicula.

## État du 21 octobre 2026

La démarche retenue revient à **DDR 5.9 + FIFO CPU maison en bascules** :
N38 sert de référence conservée pour mémoire/TARGET et timing historique,
N33/N34 de témoins DDR et remplissages 2D. Les 104 fichiers source figés
de N38 sont vérifiés ; les empreintes et différences avec N52r8 sont dans
`TESTS/neo_720p_20261012/ddr59_baseline_20261020/reference.json`.
**N38r0 est restauré sur la Neo** : DDR5.9/300 MHz, interface 75 MHz,
FIFO maison, CPU arrêté et scanout désactivé. Les prétests mémoire/TARGET,
2 048 lectures par paires, 32 pages de 4 Kio réparties dans la DDR,
quatre remplissages GPU de 4 Kio et les 29 configurations TARGET passent.
Le profil `neo-fifo-registers` est désormais le défaut du constructeur Neo.
Les résultats sont dans
`TESTS/neo_720p_20261012/ddr59_baseline_20261020/restoration.json`.
N38 conserve ses défauts 3D et le constat sur le modèle des copies du
propriétaire GPU ; sa qualification reste `FAIL`. Le chargement de référence
est limité au bitstream exact et aux prétests sans Linux.
Pas de nouvelle série DDR6/400 MHz. R11 a terminé ; il est conservé sans
chargement et le validateur automatique reste arrêté.

Sur cette base, six essais pixels isolent un défaut de remise à zéro
interne au GPU : le masque, le tampon couleur et le sélecteur de perspective
se comportent comme si CHUNK ne les effaçait pas. Une nouvelle capture,
prédite avant l'essai, confirme exactement 16 Kio et 841 octets erronés.
Cela identifie le comportement, sans prouver la cause physique du signal.
La variante **N54** calcule la validité des pixels sur l'entrée D.
Les simulations et audits logiques passent ; N54r0 reste non chargé
(setup −3,725 ns, recovery −3,882 ns).
L'analyse Workbench a séparé les origines des horloges générées des délais
de distribution et repéré deux longs trajets de reset GPU. N54r1 corrige
ces deux trajets (+3,332/+4,645 ns) et passe les audits HDMI/CDC, mais reste
non qualifié (setup −3,609 ns, recovery −2,673 ns). **N54r2 échoue au routage**
avec 114 413 nets non routés ; son validateur s'arrête sans accès carte.
**N54r4 termine le routage sans cache incrémental** : mêmes 106 fichiers figés,
netlist, CST (94 ancrages), SDC et compilateur que R2. Seule l'option
`inc_place` est supprimée, pour distinguer l'effet de la reprise du placement
de celui des contraintes. Le validateur attend ce seul nouveau build ;
aucun N54 n'a encore été chargé. R3 a été interrompu au placement (10 %,
sessions terminées, aucun processus restant vérifié sur l'hôte) ; R4 reprend
ses entrées exactes. R4 donne setup +0,179 ns, hold +0,124 ns,
recovery −2,549 ns et removal −0,070 ns : il reste non chargé.
Les chemins recovery du PHY DDR passent à +0,246 ns minimum ; les
violations restantes concernent huit récepteurs GPU et trois resets HDMI.
DDR5.9/300, FIFO et arbitrage sont conservés.

La préparation **N55** ajoute seulement la capture sur D du sélecteur de
perspective, pour supprimer sa dépendance au même effacement CHUNK.
Les six tests pixels, la comparaison cycle par cycle et les 3 Mio du test
3D complet passent. Le mapping produit une DFFCE à CE constant et CLEAR
inactif, vérifiée avec 845 contrôles ; les 3 075 contrôles du masque passent
aussi. **N55r0 a terminé mais reste non chargé** : setup +0,003 ns,
hold +0,124 ns, recovery −1,100 ns, removal +0,352 ns. Tous les audits
structurels et d'horloges passent ; 43 chemins recovery restent négatifs
(11 récepteurs du reset vidéo et 32 du reset PHY DDR). À emplacements
identiques, la dernière branche du pire chemin DDR passe de 1,316 ns
dans N54r4 à 2,285 ns dans N55r0 : c'est une sensibilité au routage
mesurée en STA, sans preuve de sa responsabilité dans les erreurs matérielles.
**N55r2 est lancé avec la même netlist et le même SDC que N55r0** :
44 contraintes de placement ciblent ces chemins, HDMI SG[0]/colonne 160
reste inchangé. N55r1 a été refusé avant lancement du compilateur pour
une incohérence CST/manifeste HDMI ; son dossier est conservé. La préparation
R2 remet l'entrée en colonne 150 avant le déplacement contrôlé vers 160.
Le validateur est suivi d'une comparaison automatique des pixels, puis
de la 3D si les pixels passent. Les contrôles temporels précèdent le
chargement, et le prétest mémoire/TARGET précède les comparaisons graphiques.
**Essai matériel N55r2 effectué le 21 octobre** : le routage termine avec
setup +0,003 ns, hold +0,144 ns, recovery +0,461 ns, removal +0,193 ns,
sans violation ni audit en échec. Le prétest automatique charge la SRAM,
vérifie ILM et DDR, puis s'arrête sur un rejet de `TARGET` par le GPU v1.
Un second chargement du même bitstream reproduit exactement ce rejet.
Les 32 pages distinctes de 4 Kio réparties sur 1 Gio et le remplissage 2D
historique passent ; `TARGET` reste rejeté même envoyé mot par mot.
L'instantané cohérent GPU expire après chacun des deux chargements.
N55r2 reste donc **FAIL sur carte**, malgré sa qualification statique PASS.
La carte est laissée sur ce diagnostic, CPU arrêté, scanout désactivé,
sans Linux ni accès SD/flash. La suite pixels/3D n'a pas été exécutée.
Preuve : `n54_mask_work_20261020/n55r2_board_result.json` sous le dossier
de tests Neo. N38 et ses preuves restent conservés comme référence.
Preuves et état : `TESTS/neo_720p_20261012/n54_mask_work_20261020/`.

La console complète DDR6/400 MHz reste **non qualifiée**. Avant cette
restauration, N52r8 a été chargé à la demande de l'utilisateur, en diagnostic.
Sa première
relecture DDR échoue sur 23 mots à l'offset 0x30 modulo 64 octets ; chaque
valeur correspond au mot attendu 16 octets avant. Les commandes GPU sont
transportées, mais les compteurs de rejet rendent le test TARGET invalide.
Le diagnostic précédent N50r2 passait les essais DDR ciblés et échouait
sur les commandes GPU. Le défaut de polarité des copies de `v1_select` est
démontré dans son modèle post-PNR ; sa présence dans le bitstream reste à établir.

Les nouveaux routages désactivent la réplication automatique. Les audits
structurels passent, mais la fermeture temporelle reste incomplète :

| Build | Setup (ns) | Recovery (ns) | Chargé |
|---|---:|---:|---|
| N52r1 | −5,708 | −1,247 | Non |
| N52r4 | −2,696 | −0,200 | Non |
| N52r5 | −5,680 | −0,206 | Non |
| N52r6 | −2,623 | −0,253 | Non |
| N52r7 | −1,659 | −0,403 | Non |
| N52r8 | −1,659 | −0,086 | Diagnostic demandé ; DDR/GPU FAIL |
| N53r0 | −5,078 | −0,395 | Non |

R6 et R8 sont refusés par le chargement automatique. R8 reprend R7 en déplaçant les
quatre groupes FIFO ; il reste 24 destinations négatives en recovery.
La comparaison R4/R7 montre que les violations suivent les emplacements
lorsque deux groupes échangent leurs places. Ce constat STA ne démontre
pas un défaut fonctionnel propre à un groupe FIFO.

R9 fixe les 80 FF FIFO sur des sites précis et rapproche six pilotes de
reset GPU. Sa reprise du placement R8 échoue avec 114 780 nets non routés,
sans résultat temporel exploitable. R10 reprend exactement ses netlist,
CST et SDC avec un placement neuf, mais échoue avec 110 nets non routés.
Le rapport ne nomme pas ces nets : la cause précise reste à établir.
R11 et R12 repartent du placement R8 qui routait complètement. R11 déplace
uniquement les 24 bascules DDR dont le recovery est négatif, dans une région
sans imposer chaque site. R12 ajoute les six régions des pilotes GPU.
R12 échoue avec 114 776 nets non routés ; R11 a terminé le routage et produit
un bitstream, conservé sans qualification ni essai sur carte à ce stade.
Netlist, SDC et contraintes hors placement sont identiques à R8. Le validateur automatique a été arrêté avant le
chargement explicite R8 pour conserver cette version sur la carte,
sans affichage. La demande suivante a restauré N38r0/DDR5.9.

N53r0 a terminé avec une capture privée des 256 bits de commande pixels
pendant IDLE, sans reset global du paquet ni cycle ajouté. Les comparaisons
RTL, les resets quatre états et les 80 configurations sur la netlist
synthétisée passent. Le routage obtenu reste moins bon que N52r8 :
le pire chemin GPU comporte 13,286 ns de routage pour 1,190 ns de logique.
N53r0 est refusé au chargement. Les fréquences DDR400/UI100 et les budgets
temporels sont conservés.

Comparaison interactive :
`TESTS/neo_720p_20261012/optimizer_ddr400_20261020/index.html`.
Journal détaillé et preuves : `TESTS/NEO_720P_20261012.md`,
`TESTS/neo_720p_20261012/n52_reset_placement_20261020/`.

## Résultats des 17 et 18 octobre 2026

**Les chemins publiés pour N45r3 ont des marges positives**, avec zéro endpoint
signalé en violation : setup **+0,177 ns**, hold **+0,124 ns**, recovery **+0,119 ns**,
removal **+0,269 ns**. La largeur d'impulsion minimale garde +1,375 ns.
Les corrections portent sur la distribution du reset Neo, le placement
d'un diagnostic PLL et la distribution/position des resets HDMI. Les
fréquences et les quatorze bornes CDC effectives de 8 ns sont conservées.

Les 18 contrôles HDMI, les huit horloges PRIMARY et les sept pilotes de
reset après routage sont vérifiés. **La qualification globale reste FAIL**
sur les quatre contrôles GPU classés LW. Deux chargements de diagnostic
en SRAM ont ensuite réussi côté programmateur, mais le TAP AE350 n'a pas
répondu : aucun test DDR n'a pu démarrer. Le témoin N38 a été restauré,
son prétest mémoire a passé et le CPU a été laissé arrêté. Le timing N45r3
ne valide donc pas le fonctionnement de la console sur carte.
Preuves : `TESTS/neo_720p_20261012/n45r3_timing_closed.json` et tableau de
bord `TESTS/neo_720p_20261012/optimizer_n45_closed/index.html`.
Résultats sur carte : `TESTS/neo_720p_20261012/N45R3_BOARD_20261017.md`.

Le candidat N46r0 ajoute un reset explicite et régénère l'IP DDR6 pour
300 MHz. Son setup passe (+0,534 ns), mais sa recovery DDR échoue
(−2,964 ns). Il n'est pas chargé. Le nouveau tableau de bord est
`TESTS/neo_720p_20261012/optimizer_ddr_startup/index.html`. Le candidat
N47r0 à 400 MHz est routé mais échoue en setup (−7,395 ns) et recovery
(−8,637 ns), sur les commandes HOLD/RESET des cellules DQS du PHY DDR.
Il n'est pas chargé. Les relations d'horloges et la séquence de calibration
doivent être examinées avant d'en déduire une limite de fréquence.
Comparaison : `TESTS/neo_720p_20261012/optimizer_ddr_startup_400/index.html`.

La suite `check_constraint_semantics.py --suite ddr-clock-relations` reproduit
un défaut de couverture : un chemin interdomaines apparaît avec des périodes
10/2,5 ns ou 13,332/3,333 ns, mais disparaît avec 13,333/3,333 ns. Les anciens
rapports DDR300 arrondis ne suffisent donc pas à prouver la fermeture complète.
Preuve : `TESTS/neo_720p_20261012/ddr_clock_relations_20261017/result.json`.

N47r1, toujours DDR400/UI100, reprend la séparation de l'horloge rapide PHY
du modèle Sipeed Hynix 400 MHz ; sa frontière est auditée après routage et
les 14 bornes CDC de la console restent inchangées. Il échoue encore :
setup −2,346 ns, recovery −2,033 ns ; hold +0,124 ns, removal +0,145 ns.
N47r2 termine sans réplication, avec regroupement physique des resets et
registres de lecture AHB, sous **le même SDC que N47r1**. Sa recovery s'améliore
à −0,222 ns et le bus80 passe, mais le setup GPU/UI100 se dégrade à −3,446 ns
(1 303 endpoints de données, plus 24 recovery DDR). Le placement seul n'a
pas fermé ce candidat. Aucun de ces candidats n'est chargé. Comparaison :
`TESTS/neo_720p_20261012/optimizer_ddr400_closure/index.html`.

N48r0 poursuit à DDR400/UI100 avec un étage de réception GPU (+1 cycle,
1 réponse/cycle), sans modifier l’arbitre DDR partagé. Les simulations de
rafales/reset, 98 commandes géométrie/raster et 604 commandes 2D/affines
passent, avec vérification des pages et zones de garde. Les audits de
synthèse passent ; deux PNR comparent les contrôles locaux et leur allocation
automatique, avec la LUT de reset DDR placée à côté de son registre source.
N50r0 ajoute les préchargements des coefficients et des coordonnées texture,
ainsi que l’arrondi alpha après le produit enregistré. Les comparaisons RTL
et le test du DSP synthétisé passent. N50r0 termine : setup −4,157 ns,
recovery −0,563 ns ; les autres analyses et les audits passent. Le pire
chemin est un fil de 13,647 ns entre deux registres de retour GPU. N50r2
regroupe les registres de ce bus/cache et des récepteurs reset DDR, avec
le même RTL et le même SDC. Les N48/N50 sont maintenant terminés :
N50r2 ferme hold/recovery/removal/pulse (+0,124/+0,551/+0,145/+2,025 ns),
mais son setup reste à −6,567 ns. N50r3, même placement avec l'option de
routage 1, échoue avec 7 941 connexions non routées.

N50r2 a été chargé en SRAM en **diagnostic**, CPU au parking. La DDR6 à
400 MHz passe les 32 pages réparties sur 1 Gio, 2 048 lectures de paires,
1 120 lectures à phases variables et les échanges CPU/JTAG. Le remplissage
GPU 2D historique passe aussi. Toutefois, les 22 descripteurs TARGET valides
du test de configuration sont tous rejetés ; ce n'est pas une console
qualifiée. Aucune écriture SD/flash, aucun Linux lancé. Le rapport
`TESTS/neo_720p_20261012/optimizer_ddr400_board/index.html` joint les résultats
contradictoires à l'empreinte exacte du bitstream.

N51r0 retire le reset global de 512 bits privés du raster, en gardant leur
clear CHUNK. N52r0 précharge en plus les 312 bits privés de commande/fins
d'adresse géométriques pendant IDLE. Les comparaisons cycle par cycle,
les tests de reset et les audits de synthèse passent ; ces deux candidats
ont été comparés sous le même SDC, avec le regroupement des récepteurs DDR.
N51r0 termine avec setup −4,851 ns et tous les contrôles hold/reset positifs.

L'inspection post-PNR révèle cependant que les cinq copies automatiques du
sélecteur GPU `v1_select` perdent les inversions CE et RESET dans le modèle
exporté. La simulation des cellules extraites reproduit la divergence avec
l'original. Ce défaut se retrouve dans N38, N45, N48, N50 et N51 ; il reste
à distinguer un défaut du bitstream d'un défaut d'export par comparaison sur
carte. Le nouvel audit obligatoire `gpu_owner_replication` empêche de charger
ces candidats, y compris en diagnostic. Le tableau de bord affiche les
raisons de rejet et vérifie l'empreinte de la netlist routée associée.
N50r4 compare exactement N50r2 avec la seule réplication automatique
désactivée. N52r1 applique la même option aux dernières modifications RTL.
Les preuves sont dans `TESTS/neo_720p_20261012/n50_replication_polarity/`.

## Résultat concret du 13 octobre 2026

Sur **la même netlist complète de console N18**, le placement de 13 cellules
LUT/DFF dans `R[80:100]C[146:160]` donne :

| Essai | Setup en erreur | Hold en erreur | Marge minimale | TNS setup |
|---|---:|---:|---:|---:|
| N18 | 2 | 0 | −0,249 ns | −0,393 ns |
| N18r2, candidat produit par Workbench | 0 | 0 | **+0,135 ns** | **0 ns** |

Les broches, horloges, délais CDC et fonctions sont conservés. Le placement
et le routage utilisent les mêmes stratégies Gowin 3/2/1. Le candidat passe
aussi les audits des deux régressions de synthèse DSP connues du projet.

**Cette réussite de timing ne valide pas encore le port sur carte.** Le
premier chargement N18r2 a détecté des corruptions DDR et n'a pas démarré
Linux. Les bitstreams libres décrits ci-dessous sont uniquement compilés,
pas chargés. Cette distinction est conservée dans les statuts et rapports.

## Fonctions disponibles

- Installation locale de versions figées avec SHA-256 des archives officielles.
- Compilation RTL, synthèse Yosys, placement/routage nextpnr et bitstream
  Apicula, avec exploration reproductible de plusieurs graines.
- Vérification de la présence effective de primitives attendues dans la netlist.
- Analyse des rapports Gowin : setup, hold, recovery, removal, pulse width,
  WNS, TNS, violations par horloge, ressources, arcs et fanout des chemins.
- Séparation du délai logique et du délai de routage sur chaque chemin détaillé.
- Relevé PRIMARY/LW/HCLK des horloges et resets, avec les avertissements de
  contraintes d'horloge ignorées ou de routage générique (CT1018/PR1014).
  Une allocation LW est un point à examiner, pas une preuve de panne.
- Comparaison par groupes de netlist, contraintes temporelles, broches,
  FPGA et moteur identiques. Un changement de fréquence crée un autre groupe.
- Tableau de bord HTML autonome : filtre, sélection des chemins, positions,
  ressources et sélection graphique d'une région candidate.
- Génération de contraintes `INS_LOC` régionales pour les LUT/DFF des chemins
  setup négatifs ; conservation des ancrages préexistants et des broches.
- Préparation automatique de jusqu'à trois régions candidates à partir des
  positions mesurées sur les chemins critiques.
- File séquentielle d'essais **Gowin Neo**, à priorité CPU réduite, avec netlist
  réutilisée, sources figées, empreintes, journaux et qualification automatique.
- Conservation des échecs et des travaux incomplets. Aucun chargement matériel
  n'est lancé par Workbench.

Le tableau de bord sert à préparer une expérience. Il ne prétend pas prédire
le routage final : chaque déplacement doit être placé, routé puis mesuré.

## Installation

Python système récent, `curl`, Linux x86-64. Aucun paquet système modifié.

```sh
python3 optimizer/bootstrap.py
python3 optimizer/bootstrap.py --component legacy-pack
python3 optimizer/optimize.py doctor --out optimizer/runs/doctor.json
```

La suite OSS CAD est celle du **2026-10-13** : Yosys `0.69+286 / 37f25dae9`,
nextpnr `0.11.1-59 / 837d0eed`, Apicula fourni `0.35.dev2+g834c9e891`.
L'installation complémentaire d'Apicula **0.32** reste séparée. Elle évite une
régression reproduite dans le packer récent : `GW5AST_138C` n'y possède pas
`get_MULT12X12_fuses`. Le routage DSP réussit, puis le packer récent échoue.
La chaîne ne masque pas cet échec et ne bascule pas silencieusement de version.

`toolchain.lock.json` et `apicula-legacy.lock.json` contiennent les URL, tailles,
empreintes et sources. `--archive PATH` permet d'utiliser une archive déjà
téléchargée. Les outils se trouvent dans `.tools/`, les essais dans `runs/` ;
ces deux dossiers sont ignorés par Git. Prévoir plusieurs Go pour la suite.

## Parcours libre validé en compilation

```sh
python3 optimizer/optimize.py open \
  --project optimizer/examples/neo_probe/project.json \
  --out optimizer/runs/probe_new --seeds 1 7 42

python3 optimizer/optimize.py open \
  --project optimizer/examples/neo_dsp/project.json \
  --out optimizer/runs/dsp_new --seeds 1 7 42
```

Le premier exemple infère une RAM et multiplie deux nombres signés de 18 bits.
Yosys n'infère actuellement pas de DSP GW5A pour cette expression : le produit
utilise des LUT. Le second instancie explicitement un `MULT12X12` pipeliné et
sélectionne `packer: legacy-0.32`. Les deux produisent un bitstream sur chacune
des trois graines, avec **2 BSRAM** ; le second utilise **1 MULT12X12**.

Leurs Fmax nextpnr sont respectivement 95,329–96,927 MHz et
350,754–378,644 MHz pour une contrainte de 50 MHz. Ce sont deux circuits et
deux latences différents : ces chiffres ne mesurent pas un gain de performance
de la console, ni sa fréquence utilisable sur carte.

Un projet JSON décrit `top`, `device`, `family`, `synth_family`, `sources`,
`cst`, `frequency_mhz` et éventuellement `sdc`, `required_cells`, `packer`.
Les chemins sont relatifs au projet. Le premier adaptateur couvre des sources
Verilog/SystemVerilog autonomes ; les dépendances `include`, ROM externes et
IP chiffrées ne sont pas importées automatiquement.

Options d'exploration : `--placer heap|sa`, `--router router1|router2`,
`--seeds ...`, `--timeout SECONDS`. Chaque lancement exige un dossier nouveau.
Les sorties comprennent les sources copiées, la netlist JSON, les commandes,
les temps d'exécution, les journaux, les positions et `design.fs` par graine.

`COMPILED` signifie uniquement que la chaîne a terminé avec les Fmax rapportées
supérieures aux contraintes et un bitstream produit. nextpnr n'est pas ici un
substitut aux contrôles hold/pulse/CDC et aux essais matériels de la console.

## Lire et comparer les résultats

```sh
python3 optimizer/optimize.py report \
  tang/impl/console_neo_n18 tang/impl/console_neo_n18r2 \
  optimizer/runs/neo_probe_001 optimizer/runs/neo_dsp_legacy_002 \
  --out optimizer/runs/dashboard
```

Ouvrir `optimizer/runs/dashboard/index.html` dans un navigateur. Aucun serveur,
compte, CDN ou accès réseau n'est nécessaire. `comparison.json` contient
l'ensemble des chemins ; le HTML conserve tous les chemins négatifs et
jusqu'à 40 chemins positifs par build.

La carte Gowin montre **seulement les cellules des chemins publiés** dans le
rapport. La vue nextpnr peut montrer toutes ses cellules placées. Les traits
dessinés relient les cellules ; ce ne sont pas les pistes physiques détaillées.
Les coordonnées X/Y nextpnr ne sont pas converties en R/C Gowin. Les fichiers
de placement propriétaires `.p` et `.pr` ne sont ni décodés ni modifiés.

Statuts Gowin : `INCOMPLETE`, `BUILD_FAILED`, `UNVERIFIED`, `TIMING_FAIL`,
`TIMING_PASS`. Un rapport tronqué, une source changée, un SDC non couvert ou
une erreur de routage ne devient jamais `TIMING_PASS`. La qualification du
projet reste affichée séparément et ses empreintes sont vérifiées.

## Déplacer et mesurer avec Gowin

Exemple reproductible de la région ayant corrigé N18 :

```sh
python3 optimizer/optimize.py place \
  --build tang/impl/console_neo_n18 \
  --cst tang/impl/console_neo_n18/source/tang/boards/neo/neo.cst \
  --region 'R[80:100]C[146:160]' --paths 2 \
  --out optimizer/runs/new_region/neo.cst
```

La sélection exclut les DSP, BSRAM, PLL, IO, les ancrages existants et les
internes `u_soc/` / `u_usb_`. Le nombre de places disponibles n'est qu'une
borne géométrique ; Gowin reste responsable des règles électriques et de
légalité. Le fichier JSON voisin décrit chaque cellule et sa position passée.

Créer `experiments.json`, par exemple :

```json
[
  {"name":"console_neo_region_trial","place":3,"route":2,"replicate":1,
   "cst":"optimizer/runs/new_region/neo.cst"},
  {"name":"console_neo_strategy_trial","place":4,"route":2,"replicate":1}
]
```

```sh
python3 optimizer/optimize.py plan --parent tang/impl/console_neo_n18 \
  --experiments experiments.json --out optimizer/runs/new_region/plan.json
python3 optimizer/optimize.py run optimizer/runs/new_region/plan.json
```

Le plan est figé avant lancement : netlist, CST, SDC, manifeste, Tcl et scripts
de construction/qualification. Les sources du parent sont aussi revérifiées
par le routeur. Chaque essai utilise un nouveau répertoire `tang/impl/NAME`.
Un verrou empêche deux exécutions simultanées du même plan. La file est
séquentielle et ne tue ni ne modifie les compilations d'autres sessions.
Les essais terminés ne sont pas relancés ; un travail interrompu marqué
`RUNNING` exige une inspection, pour éviter un doublon.

Pour préparer automatiquement les régions, sans lancer les compilations :

```sh
python3 optimizer/optimize.py search --parent tang/impl/console_neo_n18 \
  --out optimizer/runs/auto_regions_new --prefix console_neo_auto --trials 3
python3 optimizer/optimize.py run optimizer/runs/auto_regions_new/plan.json
```

Cette recherche utilise l'emprise des cellules des chemins setup négatifs et
deux contractions. C'est une heuristique de départ, pas une prédiction de gain.

Pour des chemins indépendants, `--split-paths` produit une région par groupe
de chemins partageant des cellules. Il évite de placer deux fonctions
éloignées dans une seule grande boîte. Les groupes qui se recoupent sont
fusionnés, y compris lorsqu'un troisième chemin relie deux groupes ; les
ancrages restent intacts. Un chemin entre horloges différentes est refusé
par ce mode automatique et demande une analyse CDC préalable.

```sh
python3 optimizer/optimize.py search --parent tang/impl/console_neo_n21 \
  --out optimizer/runs/n21_groups_new --prefix console_neo_groups \
  --trials 1 --paths 2 --split-paths
```

Sur N21, cela prépare deux régions séparées : six cellules du bus vidéo et
dix du blitter. La proposition ne vaut pas validation de timing ; le reset
du blitter a notamment une forte charge que la proximité seule peut ne pas
résoudre.

Gowin 1.9.12 et une licence valide sont nécessaires. Dans l'environnement
Codex, sa vérification d'identifiant réseau nécessite l'exécution hors bac à
sable. L'adaptateur de lancement actuel utilise `tools/route_console_neo.py` ;
les rapports Pro Dock sont lisibles, mais leur file de construction spécifique
n'est pas encore intégrée à cet adaptateur.

## Vérification et limites

```sh
python3 -m unittest discover -s optimizer/tests -v
node optimizer/tests/test_dashboard.cjs
```

Les tests Python couvrent les échecs silencieux de qualification, rapports
incomplets, contraintes inactives, sources modifiées, qualification périmée,
respect des broches et ancrages, protection contre l'injection dans le HTML.
Le test navigateur optionnel utilise Playwright et Chrome déjà installés
(`PLAYWRIGHT_MODULE`, `CHROME_BIN` personnalisables), vérifie filtre,
chemins, sélection de région, commande proposée et affichage mobile.

L'outil n'a pas encore de modèle de congestion complet Gowin ni de moteur
autonome capable de remplacer son routeur. Les résultats positifs portent
sur un premier cas réel de placement et deux circuits libres de référence.
Le support de la console entière dans la chaîne libre — AE350, DDR3, PHY
USB chiffré et primitives spécifiques — reste **non établi**.

Sur N20, le rapport détaille maintenant le délai des fils, celui des cellules
combinatoires, le clock-to-Q et la charge maximale de chaque chemin publié.
Le pourcentage de routage inclut le clock-to-Q dans son dénominateur, comme
Gowin, et exclut les trajets de distribution d'horloge. Les pistes proposées
(regroupement, registres locaux, pipeline) sont des hypothèses à tester.
Un chemin entre horloges différentes demande d'abord une analyse CDC ;
aucune exception de timing n'est créée automatiquement. Les rapports sans
arcs détaillés ne reçoivent pas de diagnostic inventé.

Exemple réel : le pire chemin N20 vers le refill du cache compte 11,835 ns
de routage, 2,006 ns de logique et 0,382 ns de clock-to-Q, soit 83,2 % de
routage ; la charge maximale observée est de 257 destinations. Le tableau
de bord `runs/n20_review/index.html` compare N20 et les candidats en cours.
Les nouveaux contrôles portent à 28 le nombre de tests unitaires, dont la
conservation d'un ancrage `INS_LOC` placé après une autre instruction sur
la même ligne CST.

Le premier essai régional N20 donne −0,699 ns de pire marge au lieu de
−1,178 ns, mais **58 violations setup** au lieu de 13 et un TNS plus mauvais :
il est rejeté. N21, avec correction RTL du cache et nouveau placement, donne
5 violations / −0,740 ns. Ces mesures illustrent pourquoi la qualification
porte sur le circuit entier et pas seulement sur le chemin visé.

Sources principales : [nextpnr](https://github.com/YosysHQ/nextpnr),
[Apicula](https://github.com/YosysHQ/apicula),
[OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build),
[manuel Gowin](https://cdn.gowinsemi.com.cn/SUG100E.pdf).
Les contraintes régionales suivent le manuel local Gowin SUG1018-1.7E Arora V.

### Inspection des horloges (13 octobre, N20r1/N21r1)

Les deux candidats ferment le timing (+0,138 / +0,116 ns) mais leurs essais
physiques échouent au contrôle DDR ; les résultats ne valident donc pas le
port Linux. Le relevé de routage montre la référence 50 MHz et plusieurs
resets sur LW. Le tableau de bord affiche désormais ces allocations et les
avertissements de contraintes d'horloge. Les **30 tests unitaires** et le
contrôle Chrome 155 passent. Les essais de routage local des resets et de
distribution de la référence d'horloge sont détaillés dans
`TESTS/NEO_720P_20261012.md`.

### Associer les essais sur carte au rapport

Ajouter `--board-results chemin/essai/result.json ...` à `report` pour
afficher ces verdicts à côté du timing. Chaque résultat doit fournir
`bitstream_sha256` et un booléen `passed`. Le SHA-256 doit correspondre
exactement à un bitstream du rapport ; les noms de dossiers ne servent
pas à l'association. Les preuves contradictoires sont conservées.
Ces résultats couvrent seulement les essais fournis, pas toute la carte.

La lecture de ces preuves ne lance aucune opération matérielle. Les
34 tests unitaires couvrent notamment les associations erronées et les
verdicts absents ; le navigateur vérifie l'affichage d'un échec physique
à côté d'un timing positif.

### Reprise sur N42/N43 et essai nextpnr du 17 octobre

La chaîne déjà installée du 13 octobre est réutilisée sans réinstallation.
Le rapport actualisé est sous
`TESTS/neo_720p_20261012/optimizer_n42_n43/index.html` : N38 reste positif
en timing uniquement, N42 et N43 échouent. Le gain historique N18r2 venait
des contraintes régionales Workbench exécutées par **Gowin**, tandis que les
exemples `neo_probe` et `neo_dsp` utilisaient effectivement nextpnr.

Deux essais supplémentaires précisent les limites du parcours libre :

- Import direct de la netlist complète N43 par Yosys : arrêt à la ligne
  111972 sur `` `pragma protect ``. Les blocs chiffrés restent intacts et ne
  sont pas remplacés par des boîtes noires pour prétendre compiler la console.
  Preuve : `TESTS/neo_720p_20261012/nextpnr_n43_import/`.
- Reproducteur réel de distribution des resets, avec observation JTAG,
  horloges 50 MHz et 1 MHz : synthèse terminée, mais nextpnr annonce
  **BUFG 2/1** puis refuse le placement faute de site BUFG. Il s'agit de
  la capacité exposée par la base installée, pas d'un relevé des ressources
  physiques disponibles dans le FPGA. Preuve finale :
  `TESTS/neo_720p_20261012/nextpnr_reset_jtag_cells/build/seed_1/pnr.log`.

Les premières variantes de ce reproducteur ont révélé que les commentaires
`syn_preserve`, puis même `keep` sur le vecteur, ne conservaient pas quatre
bascules distinctes dans la synthèse Yosys. Elles sont archivées dans
`nextpnr_reset_jtag` et `nextpnr_reset_jtag_kept`, sans valeur de comparaison
physique du défaut de reset. La variante finale instancie quatre DFFCE avec
`keep` sur chaque cellule, comme les drivers mappés de l'essai Gowin. L'audit
`mapping_audit.json` confirme quatre sorties distinctes et les mêmes entrées
D/CLK/CE/CLEAR. Cette variante rencontre encore la limite BUFG 2/1.

Aucun résultat de routage, gain de timing ou test physique n'est donc obtenu
avec nextpnr sur ce reproducteur. Les deux fréquences sont contraintes, mais
ce projet expérimental n'apporte pas une qualification CDC/IO complète.
Le support des exemples à une horloge ne suffit pas à établir celui de la
console complète. La voie complémentaire de placement Workbench → Gowin
reste disponible ; les passages entre horloges et resets N42/N43 demandent
leur analyse propre avant une nouvelle recherche régionale.

### Fermeture des horloges et resets Neo (N44 expérimental)

`check_constraint_semantics.py` complète la recherche régionale par des
circuits isolés de caractérisation Gowin. Par exemple :

```bash
python3 optimizer/check_constraint_semantics.py --suite hdmi-dce-place \
  --columns 160 150 140 --out /tmp/neo_hdmi_placement_trial
```

`complete: true` dans son résultat signifie que la compilation a terminé,
**pas** que le timing passe. Tous les types de contrôle doivent être lus,
avec vérification de la présence des chemins attendus. Les essais ont
notamment rejeté un multicycle qui faisait disparaître les contrôles HDMI.

Le profil `tools/neo/timing_closure.py`, activé explicitement à la construction
Neo, applique le placement caractérisé, puis vérifie après routage la
présence des 18 contrôles de reset HDMI et la normalisation des bornes CDC.
Une latence de source différente invalide cette normalisation : le budget
effectif ne doit pas dépasser les 8 ns d'origine. Ce profil conserve les
fréquences, les exceptions existantes et les sources communes Pro Dock.
Preuves détaillées : `TESTS/NEO_720P_20261012.md`, section N44.

Le lecteur générique refuse aussi un verdict `TIMING_PASS` lorsque l'une
des quatre analyses détaillées est vide. Un circuit sans reset peut être
légitime, mais l'absence de ses contrôles demande une justification
structurelle que ce lecteur ne déduit pas. Le contre-test HDMI multicycle
est ainsi classé incomplet ; les 36 tests de l'optimiseur passent.

L'essai `--suite cdc-generated` compare aussi les bornes corrigées par une
latence mesurée à des origines d'horloge locales fixées à zéro. Cette
seconde méthode conserve les bornes littérales de 8 ns et, pour HDMI,
la même origine sur les deux horloges liées. Les contre-tests conservent
les marges des deux sens du CDC à 0,001 ns près, ainsi que les marges HDMI.
La route Neo peut l'activer via `--cdc-clock-origins-zero` ; l'audit vérifie
les valeurs effectivement publiées après routage. Les circuits isolés
ne sont jamais chargés et ne qualifient pas la console entière.

Les essais de pression sur les ressources s'exécutent par exemple avec :

```bash
python3 optimizer/check_constraint_semantics.py --suite hdmi-clock-pressure \
  --dce-sites pg0 sg0 sg8 --out /tmp/neo_clock_pressure_trial
```

Ces circuits chargent huit domaines par des compteurs. Ils servent à comparer
les allocations PRIMARY/LW/HCLK, sans simuler un contrôleur DDR ou USB.
`--suite hdmi-dce-sites --dce-sites sg0 --columns 150 160 170` mesure ensuite
le placement des resets HDMI. Les rapports N44 ont montré que conserver les
instructions `CLOCK_LOC` ne suffit pas à préserver les ressources réelles.
Le profil `--hdmi-reset-placement sg0-c150` exige donc après routage le site
DCE confirmé dans les chemins et les huit horloges d'origine sur PRIMARY.
Cette vérification complète les marges de timing ; elle ne remplace pas les
essais sur carte.

Le profil Neo optionnel `--system-reset-tree` répartit le reset bus entre
sept registres de même fonction et de même latence. Il s'applique à une
copie de sources figée. L'audit refuse les copies fusionnées, un changement
de D/horloge/enable/reset/initialisation, ou une modification étrangère au
profil DDR. Le routeur lie les contraintes aux vrais réseaux du netlist
vérifié, car `syn_keep` peut supprimer les alias de ports. La qualification
recontrôle aussi les sept registres dans le netlist après routage. La preuve
RTL par induction se trouve dans
`TESTS/neo_720p_20261012/system_reset_equivalence/` ; elle ne remplace pas
les contrôles temporels et les essais sur carte.

Le routeur Neo accepte aussi `--incremental-from <build complet>` et
`--incremental-mode place` (par défaut) ou `pnr`. Il copie et hache le cache
Gowin dans le nouveau build. Le netlist, les broches, les horloges et les
contraintes temporelles doivent rester identiques ; seules les positions
`INS_LOC` peuvent changer. Une ancienne compilation au timing négatif peut
servir de référence physique, sans transmettre une quelconque qualification.
L'audit final vérifie le cache et l'option réellement passée à Gowin.

La caractérisation `--suite hdmi-incremental --reference-build <probe SG0 C150>`
compare les modes placement/routage sur un circuit isolé, avec et sans
déplacement des trois resets. Les deux essais **placement** ont terminé :
les positions demandées C150 puis C160 sont confirmées dans les chemins,
et les quatre analyses temporelles passent. Les deux essais en mode `pnr`
ont ensuite terminé avec les mêmes vérifications positives. Les résultats
sont dans `incremental_hdmi_20261017/analysis.json`. **L'essai complet
N45r4 en mode `pnr` échoue toutefois avec 115 791 connexions non routées**,
malgré les mêmes entrées que N45r3. Il est rejeté ; ce mode reste
expérimental pour la console et aucun gain global n'est établi.
