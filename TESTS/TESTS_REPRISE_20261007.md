# Reprise carte vidéo, ORBITAL et SD/USB — 7 octobre 2026

Suite de cette reprise : les cinq défauts de revue sont corrigés et
**C37 est qualifié le 9 octobre 2026**. Voir les
[corrections et preuves](CORRECTIONS_REVUE_20261008.md) et
[l’archive C37](../bitstreams/console_gpu_sdusb_guard_800.md).
Ce document conserve les résultats historiques C22.

## Périmètre et état

Demande : examiner les ajouts de Claude et corriger l'ensemble carte vidéo,
ORBITAL R6, pilote SD et stockage USB composite. CPU 800 MHz, AHB 80 MHz,
GPU 75 MHz, LCD 35 MHz et USB HS 480 Mbit/s conservés.

Les succès fonctionnels sur R40 ne constituent pas une validation de son
timing. Aucun nouveau bitstream n'est déclaré validé tant que le contrôle
du timing puis les essais sur carte ne sont pas terminés.

Avant modification, les fichiers non committés ont été sauvegardés dans
`reprise_20261007/sources_avant_corrections.tar.gz`, avec leur empreinte et
le diff. Cette sauvegarde locale redondante n'est pas versionnée ; son
empreinte et le diff sont conservés dans Git. Les archives de sources des
versions qualifiées C22 et C37 sont, elles, versionnées.
Le commit Luma `e0608ec` reste inchangé.

État final, 8 octobre : **C22 est chargé, qualifié sur carte et archivé**.
Timing complet, audits de synthèse/CDC, trois rechargements HS, suite GPU,
SD en lecture, reprises USB et disque DDR passent. ORBITAL R6 passe ses
51 références et deux boucles d'endurance ; l'utilisateur confirme une
image correcte et fluide. La démo reste en marche. C21 est terminé et
refusé pour quatre défauts GPU ; aucune compilation de cette reprise ne
reste en cours. Après une indisponibilité SSH temporaire, ax15 est accessible.

Archive : [console_gpu_sdusb_800.md](../bitstreams/console_gpu_sdusb_800.md).
Les limites de stockage restent explicites au § 8 ; cette qualification
n'est pas une validation des écritures sur la SD physique.

## 1. Diagnostic physique

Rapports Gowin des instantanés conservés :

| Build | Pire marge | Extrémités setup en défaut | Conclusion |
|---|---:|---:|---|
| R40 | −0,702 ns | 4 | Fonctionnel sur carte, timing non validé |
| R325 | −0,487 ns | 2 | Chemin GPU vers un multiplicateur |
| R622 | −5,985 ns | 10 | Régression de placement/routage, bus et GPU |
| C1b | −3,699 ns | 17 | Refusé : chemins reset/bus/GPU et PHY |
| C2 | −1,920 ns | 35 | Refusé : cache de textures, reset DSP, ITCM, contrôleur USB |
| C3 | −1,635 ns | 28 | Refusé : ITCM ; copie indexée à −0,484 ns |
| C4 | −1,182 ns | 4 | Refusé : GPU ; bus CPU et USB passent |
| C6 | −1,003 ns | 41 | Refusé : resets/émission MSC et lecture de statut GPU ; moteurs GPU et ITCM passent |
| C7 | −2,773 ns | 17 | Refusé : placement imposé de shadow_base et alignement PHY ; un chemin ITCM à −0,327 ns |
| C8 | −2,344 ns | 22 | Routage 1 : le placement de shadow_base reste pénalisant, plus GPU/PHY |
| C9 | −1,988 ns | 35 | AHB corrigé ; autres ancrages hérités pénalisent le lecteur vidéo et le PHY USB |
| C10 | −1,185 ns | 10 | AHB et USB passent ; réplication défavorable au reset du blitter et au DMA |
| C13 | −0,369 ns | 2 | GPU et USB passent ; boucle HREADY et reset du diagnostic USB côté AHB |
| C14 | −7,684 ns | 534 | Placement par défaut défavorable ; non retenu |
| C15 | −0,782 ns | 3 | Routage 1 : AHB et USB passent, défauts GPU ; non retenu |
| C17 | −0,687 ns | 7 | GPU et USB passent ; détour du mux HREADY vers le pont CPU |
| C18 | −0,694 ns | 2 | Retour CPU corrigé ; détour HSEL vers MSC et un chemin raster à −0,004 ns |
| C19 | −0,715 ns | 21 | Trajets C18 corrigés ; retour des registres GPU, HREADY vers CE du pont et reset DMA |
| C20 | −0,726 ns | 4 | AHB et reset DMA corrigés ; trois chemins PHY 120 MHz et un chemin GPU à −0,044 ns |
| C21 | −2,258 ns | 4 | Routage 1 : AHB et USB passent, défauts GPU/DDR ; non retenu |
| C22 | +0,009 ns | 0 | Timing, audits et qualification matérielle passés ; archive retenue |

R622 : bus donné pour 54,098 MHz au lieu de 80 MHz, GPU pour 67,751 MHz
au lieu de 75 MHz. Le simple achèvement de la génération du `.fs` ne suffit
donc pas à accepter ce build.

Corrections ciblées :

- `gpu_line_reader.v` : anticiper la phase CLEAR dans trois registres locaux
  conservés par la synthèse. Le décodage d'état à 293 destinations, avec un
  fil de 9,597 ns, ne commande plus à lui seul les 256 bits de pixels et les
  32 bits de couverture. Aucun cycle de composition ajouté.
- `blitter.v` : préparer pendant la découpe la largeur et la visibilité des
  segments de disques pleins. La comparaison signée et le calcul de largeur
  ne se trouvent plus devant le chargement de `rw` au cycle suivant.
- `console_top.v` : conserver la sortie du multiplexeur de registres du GPU
  avant le multiplexeur des esclaves. R622 avait dispersé sa logique dans
  le pont CPU, avec un fil de 11,632 ns depuis `read_select[13]`.

Builds isolés : `gpu_sdusb_c1` arrêté avant synthèse par la licence sous le
bac à sable ; `gpu_sdusb_c1b` relancé hors du bac à sable, routage 1 ;
`gpu_sdusb_c2` inclut aussi la purge USB acquittée, routage 2.
Les sources de chaque build sont figées. Les autres compilations Gowin ne
sont pas modifiées ni arrêtées.

C2 confirme la disparition du chemin critique CLEAR et du calcul des
cercles visés au départ. Son nouveau pire chemin est `tw[6]` vers le port
d'adresse du cache de textures : huit niveaux de logique, puis un fil de
6,741 ns. C3 enregistre cette adresse dans PRIME, lit la BSRAM dans SAMPLE,
puis utilise le texel dans TEST : les états existaient déjà et le nombre de
cycles de dessin reste exact. C3 conserve aussi une copie distincte du
dernier étage de reset par moteur ; C2 utilisait une sortie pour 11 871
charges, jusqu'aux resets DSP éloignés. Ces copies ont exactement les mêmes
cycles d'assertion et de retrait que le registre original.

C3 utilise placement 3, routage 2, sans nouvelle exception de timing ni
modification des horloges. Son rapport confirme la disparition des défauts
du cache de textures et des resets DSP, mais il reste 19 extrémités ITCM et
9 GPU négatives. USB et LCD passent ; ce résultat ne valide pas l'ensemble.
Les rapports refusés et leurs empreintes sont conservés dans
`reprise_20261007/timing_c1b_c2.json`, `timing_c3.json` et les `.tr` associés.

C4 compare les mêmes sources graphiques et USB que C3 avec le routage 1
utilisé par R31. C5 poursuit deux corrections ciblées, routage 2 :

- la longueur restante d'un segment de copie se calcule directement depuis
  sa position de fin dans le bloc de 512 mots ; le chemin précédent
  enchaînait soustraction, comparaison, sélection puis soustraction
  (13 niveaux). Un contrôle exhaustif des 1 048 576 couples représentables
  vérifie longueur et reste contre `min(N,512-offset)`. Les 604 commandes
  indexées gardent les mêmes pixels et 122 223 transactions DDR aux mêmes
  cycles (`c5_copy_bounds.json`, `c5_indexed.json`/`.log`).
- les 14 LUT d'adresse ITCM, le décodeur de lecture et la LUT d'écriture
  sont rapprochés du CPU R0C160, depuis R24C88…92.
  C3 perdait jusqu'à 6,147 ns dans le fil précédant le premier décodeur.
  Il s'agit uniquement de contraintes de placement ; les cellules de l'IP
  fournisseur ne sont pas modifiées.

C5 s'arrête à la lecture des contraintes : R10C112…116 se trouve sur une
rangée de BSRAM et ne peut pas recevoir ces LUT. C6 corrige uniquement
les sites vers R11C112…116, sur une rangée logique. C4 garde quatre
extrémités GPU négatives. C6 fait passer tous les chemins du domaine GPU
et ceux de l'ITCM. Ses défauts restants sont dans le port MSC : compteur
de purge vers rassembleur RX4 et reset USB vers écriture EP1, ainsi qu'un
chemin de reset vers la lecture de statut du GPU. Les rapports C4/C6 et
leurs empreintes sont conservés avec les autres preuves. Aucun de ces
essais n'est chargé sur carte.

C7 corrige ces chemins :

- état « purge en cours » enregistré, exactement égal à `flush_count != 0`,
  sans son décodeur combinatoire devant RX4 ;
- registre commun en sortie MSC pour données, validité et compteur publié.
  Il ajoute un cycle USB (16,67 ns), sans changer le débit. Le compteur
  attend les données ; un reset annule aussi l'octet dans ce registre ;
- statut FULL du GPU lu directement dans le registre de sa FIFO. Pendant
  une lecture AHB valide, il vaut exactement `!READY` ; le masque de reset
  de READY n'a pas à traverser le multiplexeur de données du CPU.

La simulation GPU conserve 87 052 transactions DDR identiques cycle par
cycle pour 751 commandes (`c7_v1.json`/`.log`). Les trois cadences et phases
USB passent, y compris une seconde purge alors que la première attend
l'horloge, et un reset exactement avant l'écriture d'un octet enregistré
dans EP1 (`c7_msc_cdc/`). Le modèle officiel HS 3.3 passe aussi : 1 562 octets
IN, 6 175 OUT, quatre retransmissions et CDC actif (`c7_msc_controller.json`).
Le routage C7 fait passer les chemins MSC corrigés, tous les chemins du
domaine GPU et le retour de statut GPU. L'audit SDF passe aussi : les
84 liaisons Gray culminent à 0,961 ns, les cinq liaisons de purge à
0,464 ns (`c7_msc_cdc_timing.json`). L'ensemble reste cependant refusé :
16 extrémités AHB et une extrémité PHY 120 MHz sont négatives.

C8 utilise les mêmes corrections, avec le routage 1 au lieu de 2 ; les
deux builds sont isolés. La régression USB étendue vérifie 68 097 octets
continus après reset, donc le retour à zéro des compteurs 16 bits, avec
paquets en attente et ACK perdus. Les trois couples de fréquences/phases
passent (`c7_msc_wrap/`, 228 paquets IN par cas). Les sources correspondantes
sont sauvegardées avec leurs empreintes dans `correctifs_c7.tar.gz`/`.json`.

C9 conserve exactement le RTL de C7/C8 et retire deux placements imposés
devenus inadaptés :

- la validation `shadow_base` restait à R85C120, alors que ses registres
  étaient désormais à R26C158. Le fil final seul coûte 7,043 ns et le
  chemin finit à −2,773 ns ;
- la bascule `bit_align_wr_act` du PHY restait à R45C176, tandis que sa
  logique de contrôle est à R12C174. Le chemin finit à −0,954 ns.

Le placement redevient libre pour ces deux cellules ; aucune logique
fournisseur ni exception de timing n'est modifiée. C7 garde aussi un
chemin ITCM à −0,327 ns, qui sera recontrôlé. C8 et C9 sont en cours.
C10 reprend les contraintes C9 avec l'option Gowin `replicate_resources=1`
(au lieu de 0), pour comparer le traitement des réseaux à forte charge.
Les sources et les horloges sont identiques ; aucune nouvelle modification
fonctionnelle n'est introduite par ces trois essais.

C9 fait passer tous les chemins AHB. Il révèle trois autres détours
imposés par des contraintes héritées, retirées dans C11 (même RTL,
placement 3/routage 2/réplication 0) :

- sélection sprite/image : contrôle R53C176, LUT fixée R70C110, registres
  R61C170 ; deux fils de 5,863 et 7,158 ns, marge −0,726 ns ;
- TXREADY : logique R8C165, LUT fixée R38C142, contrôleur R8C107 ;
  6,316 ns de fil sur ce détour, marge −1,988 ns ;
- reset FIFO PHY fixé R72C172 vers pointeur R22C166 : fil de 4,054 ns sur
  un trajet entre deux fronts opposés, marge −0,160 ns.

Deux autres chemins de C9 sont légèrement négatifs : arbitrage vidéo
vers raster (−0,158 ns) et alignement PHY (−0,028 ns). Tous seront
recontrôlés dans le rapport complet ; aucune marge négative n'est ignorée.

C10 fait passer les domaines CPU/USB, mais les registres ajoutés par la
réplication automatique dispersent le blitter : reset à 2 670 charges
vers logique d'état, puis retour vers un registre répliqué, marge
−1,185 ns. Le DMA garde aussi −0,667 ns. C11 conserve donc la réplication
désactivée. C12 compare le placement par défaut (0) au placement 3 de C11,
avec les mêmes contraintes nettoyées et le même routage 2.

C11/C12 s'arrêtent avant synthèse : le script de build exigeait encore
deux ancrages RX PHY (RAM et reset), alors que celui du reset a été retiré
volontairement. Le contrôle est adapté pour exiger toujours la RAM exacte,
accepter seulement cet ancien reset en option, et refuser tout autre
chemin ou doublon. C13/C14 reprennent respectivement C11/C12 avec ce
contrôle adapté ; les emplacements mémoire, broches et horloges restent
inchangés.

C13 fait passer tous les chemins GPU (minimum +0,976 ns), USB 60 MHz
(+1,395 ns), PHY 120 MHz et LCD. Il ne reste que deux chemins AHB :
`bus_command` revient à sa propre entrée via le HREADY global puis HSEL
(−0,369 ns), et le reset du diagnostic USB vers `write_pending` perd
10 ns dans un fil (−0,017 ns). C15 compare le routage 1 sur cet instantané.
Il fait passer AHB et USB, mais introduit trois défauts GPU : activation de
la mémoire de commandes (−0,782 ns), donnée V1 vers DDR (−0,295 ns) et
reset du blitter (−0,054 ns). Il n'est pas chargé sur carte ; rapport et
empreinte conservés dans `reprise_20261007/timing_c15.json`.

C16 retire la première boucle : lorsque le GPU est l'esclave de données,
son HSEL n'est plus masqué par son propre HREADY retransmis dans le mux
global. Le GPU conditionne déjà toutes ses captures d'adresse à son
HREADY local ; les attentes des autres esclaves continuent à masquer HSEL.
Ce n'est ni un cycle ajouté ni une nouvelle exception de timing.

Preuves : 512 combinaisons de sélection et disponibilité comparées à partir
des expressions extraites des deux vrais tops (`c16_address_accept.*`).
Le GPU complet est ensuite comparé à R31 avec une adresse suivante
présentée pendant 1 209 026 cycles d'attente : 751 commandes, 87 052
transactions DDR et tous les pixels/gardes restent identiques cycle par
cycle (`c16_self_ready.*`). Le premier lancement n'exerçait pas ce cas,
car le maître du banc retirait HSEL pendant l'attente ; le banc a été
étendu avant de déclarer cette comparaison validée.

C16 s'arrête à la lecture des contraintes : la factorisation a supprimé
la LUT `vid_hready_s1`, toujours citée dans le CST hérité de r606/r607.
C17 conserve le RTL vérifié et retire les deux ancrages nominatifs de
ce multiplexeur. Le placement du petit pont CPU et son contrôle de
driver restent conservés. Aucune nouvelle simulation fonctionnelle n'est
requise pour ce seul retrait de placements.

C17 supprime les deux défauts de C13. Les sept extrémités restantes sont
toutes alimentées par `applied_sync[1]`, via le même multiplexeur HREADY :
la logique vidéo est à R35C153, les deux LUT du mux à R17C83, et le pont
à R21C141. Ce détour coûte 4,854 + 2,866 ns de fil. C18 place uniquement
les deux nouvelles LUT du mux à R20C132, entre les extrémités. Les noms et
fonctions ont été vérifiés dans la netlist figée de C17. GPU, USB et
l'ensemble AHB seront de nouveau contrôlés après routage.

C18 supprime les sept chemins négatifs de C17 mais déplace le problème
vers HSEL MSC : `u_commands/full` traverse C59 → mux fixé C132 → C72 →
registre MSC C48. Les deux fils autour du mux coûtent 3,068 + 2,514 ns ;
la marge est de −0,694 ns. Le rasteriseur présente aussi un chemin à
−0,004 ns vers `right[14]`. Les autres domaines, dont USB, passent.
C19 place les mêmes deux LUT en R20C110, entre les contrôles de gauche
et le pont CPU, sans nouvelle modification RTL. Les deux défauts restent
bloquants tant que le rapport complet n'est pas positif.

C19 corrige les deux trajets négatifs de C18, mais son placement disperse
la lecture des statistiques : `read_select[10]` est en R105C81, le mux GPU
en R103C76 et le retour du pont en R49C143 (−0,715 ns). Quatorze retours
CE du pont manquent aussi environ 0,1 ns. Côté GPU, cinq adresses BSRAM
du blitter dépendent du reset commun blitter/DMA : R33C64 → gate DMA
R32C116 → adresses blitter R33C65, jusqu'à 10,5 ns de fil aller-retour.

C20 conserve le placement central et traite ces deux sources de dispersion :
une copie du dernier étage de reset propre au DMA, et quatre copies du
décodage de lecture AHB, chacune alimentant un octet de la réponse. Les
registres sont conservés à la synthèse. Aucun cycle ni valeur de registre
ne doit changer. Le banc d'équivalence ajoute un balayage des 256 adresses
d'octet, dont les adresses non alignées et non implémentées, après les
commandes graphiques.

Les trois suites passent avec les enfants R31 figés : 751 commandes V1
(87 052 transactions), 604 indexées (122 223) et 785 perspective (181 665),
pixels et gardes exacts, contrôles et transactions identiques à chaque
cycle. Chaque suite lit ensuite les 256 adresses. V1 couvre également
1 209 026 attentes avec une adresse suivante déjà présentée. Preuves
`c20_v1`, `c20_indexed`, `c20_perspective` (`.json` et `.log`), instantanés
des sources et bancs dans `correctifs_c20.tar.gz`. C20 utilise le routage 2 ;
C21 compare le routage 1 sur les mêmes sources.

Audit de la netlist synthétisée C20 : les quatre registres `engine_resetn`
et les 72 registres `read_select` sont présents dans `gpu_accel` ; les
copies n'ont pas été fusionnées. Preuve et empreinte de la netlist :
`c20_preserved_registers.json`.

C20 fait passer tout le domaine AHB et les chemins reset/DMA corrigés.
Il reste trois extrémités du PHY 120 MHz issues de `de_data_dly[6]`
(−0,726 / −0,565 / −0,246 ns), ainsi qu'un chemin de priorité vidéo vers
l'état du rasteriseur à −0,044 ns. Le build reste refusé. C21 poursuit son
routage 1. C22 regroupe les huit LUT simples de la chaîne RX en R15C171 :
types LUT2/3/4 et noms vérifiés dans la netlist de simulation officielle C20.
Il ne modifie ni l'IP fournisseur ni la fréquence USB. Le résultat doit
être jugé sur l'ensemble du rapport, y compris le défaut GPU.

C22 passe : 1 085 chemins détaillés, aucun TNS ni extrémité setup/hold en
défaut. Minimum GPU +0,009 ns, AHB +0,047 ns, USB 60 MHz +0,856 ns,
PHY 120 MHz +0,150 ns. Les marges GPU et AHB restent étroites ; ce sont
les marges annoncées par le rapport aux contraintes conservées, sans
prétendre à une marge supplémentaire. Le minimum GPU relie la demande
de tuiles au registre `v1_pending`, via l'arbitrage DDR.

L'audit CDC MSC couvre les 84 liaisons Gray (maximum 1,109 ns) et les
cinq liaisons de purge acquittée (maximum 0,906 ns), budget 6,25 ns.
Preuves : `timing_c22.json`, `console_gpu_sdusb_c22.tr`,
`c22_msc_cdc_timing.json`. Bitstream SHA-256 :
`aacb08e0bca7d8948606cf497b2f2ba113476afd0e23adb80156ef89c7bfdadc`.

Occupation totale du FPGA C22 après routage : logique 67 603/138 240
(49 %), registres 45 699/139 140 (33 %), CLS 49 385/69 120 (72 %),
BSRAM 251/340 (74 %), DSP 83/298 (28 %). Ces valeurs concernent le
système complet, USB/AE350/DDR/vidéo compris, pas seulement le GPU.

À 22 h 35 le 7 octobre, ax15 ne répond plus sur SSH : résolution du nom
réussie, connexion au port 22 expirée, y compris hors du bac à sable.
Aucun chargement FPGA n'a été tenté pendant cette indisponibilité.
L'accès est ensuite rétabli pendant le placement C19 : SSH répond
`michael-AX15`, et l'utilisateur confirme le PC allumé et connecté.

## 2. Régressions graphiques

Comparaison avec les sources figées de R31, enfants du GPU inclus :

- 751 commandes V1 : pixels et zones de garde exacts, 87 052 transactions
  DDR identiques cycle par cycle (`accel_equivalence.json`/`.log`).
- 604 commandes indexées : pixels et gardes exacts, 122 223 transactions
  identiques, y compris la nouvelle préparation des cercles
  (`indexed_r2.json`/`.log`). Le premier lancement utilisait un nombre
  d'erreurs attendues incorrect (2 au lieu de 1) ; aucune divergence de
  transactions, corrigé dans l'invocation suivante.
- 16 couches, tuiles 8/16/32, 64 sprites, composition RGB : 77 670 746 cycles
  du lecteur comparés, arbitre également comparé ; aucune différence
  (`layers_r1.json`/`.log`).

ORBITAL R6 répondait sur ax15, USB négocié à 480 Mbit/s : 8 826 700 images,
55,04 images/s, `errors=0`, `uf=0`, `invalid=0`, `badsprite=0`, `rejected=0`.
Son texte « R31 » est une référence applicative codée en dur, pas une preuve
de l'identité du FPGA chargé. Le dernier chargement conservé est celui de
R40 (`diag_sdusb/demo_r40.log` sur ax15).

Après les essais SD/USB : 51 poses d'ORBITAL R6 correspondent aux références,
puis 520,7 secondes d'animation, 28 547 images, deux boucles complètes,
environ 54,81 images/s, aucun underflow ni erreur de dessin. Le journal et
les résultats sont dans `reprise_20261007_orbital_check/`. L'application a
été remise en fonctionnement après l'essai de récupération USB C2.

Régressions après la préparation de C3, contre les sources complètes R31 :

| Séquence | Commandes | Cycles DDR comparés | Transactions identiques |
|---|---:|---:|---:|
| Perspective, textures, alpha, profondeur | 785 | 4 566 547 | 181 665 |
| Graphisme indexé historique | 604 | 2 081 517 | 122 223 |
| Extension GPU V1 | 751 | 1 151 189 | 87 052 |

Tous les pixels et zones de garde correspondent également aux références.
Preuves : `c3_perspective`, `c3_indexed`, `c3_v1` (`.json` et `.log`). Le
premier essai raster isolé a été lancé avec un nombre de commandes/rejets
incorrect ; il n'a pas été retenu. Les trois comparaisons complètes utilisent
les bons paramètres, dont 18 rejets attendus sur la séquence perspective.
La synthèse de C3 conserve les trois bascules `engine_resetn`, avec leur
entrée commune `mrst[0]`, et les quatorze bascules d'adresse de texture.
Les contrôles des DSP du scanout et des copies RGB565 passent également
(`c3_pipeline_synthesis.json`, `c3_scanout_synthesis.json`,
`c3_copy_synthesis.json`).

## 3. Défaut logiciel USB reproduit et corrigé

Le firmware MSC lisait RX_COUNT, puis tous les mots RX4 annoncés sans
recontrôler le reset en fin de lot. Une purge USB au milieu de ces lectures
pouvait remplacer les octets restants par des zéros ; `receive()` déclarait
quand même le tampon valide et `disk.write()` l'écrivait.

Le modèle injecte maintenant un reset du bus ou Bulk-Only après 128 octets
sur une commande WRITE de 4 Kio. Les lectures après purge rendent zéro,
comme un registre vidé. Avant correction, le test échoue sur le nombre de
blocs écrits (`msc_reset_before.log`). Après correction : état relu pendant
et à la fin de la réception, commande également recontrôlée avant exécution.
Le média doit rester identique à sa copie, et la commande suivante réussir.

`python3 TESTS/test_usb_msc.py` : PASS sous ASan/UBSan, 1 616 857 contrôles,
six combinaisons de cadence/taille de paquets. Les cas 64 octets éprouvent le
protocole en simulation ; aucun build FS n'est chargé sur carte.

## 4. Purge des FIFO et horloge arrêtée

La purge était une temporisation AHB de 255 cycles transmise par deux
bascules au domaine USB. Arrêter l'horloge USB pendant toute cette durée
faisait perdre la demande : l'AHB annonçait la purge terminée sans que les
FIFO USB aient été vidées. Reproduction : `msc_clock_before.log`.

Le compteur attend maintenant l'acquittement synchronisé de l'assertion de
`flush_u`, puis celui de sa désassertion. Le bit « purge en cours » reste
lisible pendant l'arrêt ; aucune attente AHB n'est ajoutée.

`python3 TESTS/test_usb_msc_port.py --out /tmp/console_msc_cdc_20261007` :
PASS pour trois couples de demi-périodes USB/AHB (ns) et phases :

| USB | AHB | Phase AHB |
|---:|---:|---:|
| 8,333 | 6,250 | 0 |
| 8,342 | 6,242 | 2,137 |
| 8,325 | 6,258 | 5,731 |

Le banc exerce les reprises après ACK perdu, la contre-pression, les accès
par mots, les resets, le chien de garde, puis une purge avec horloge USB
arrêtée. À la reprise, l'ancien paquet disparaît et les données neuves sont
exactes (`msc_cdc_sweep.log`). Simulation numérique, sans preuve analogique
ni de timing physique.

Contrôle séparé du SDF de C2 : les 84 liaisons des pointeurs Gray MSC
sont présentes, directement issues de bascules ; maximum de 0,918 ns vers
le premier étage et 1,066 ns entre les deux étages. Le budget conservateur
est de 6,25 ns. Ce résultat n'annule pas les défauts setup du reste de C2.
Commande : `tools/check_usb_msc_cdc_timing.py`, preuve
`c2_msc_cdc_timing.json`.

## 5. SD : capacité et polarité

- `sd_init()` ne doit pas annoncer READY après un défaut de CRC sur le CSD.
  Cette erreur est maintenant propagée ; une capacité nulle est refusée.
- Lectures/écritures refusées avant tout transfert si l'intervalle dépasse
  la capacité ; comparaison sans débordement de `sector + count`.
- Calcul de capacité SDSC en 64 bits pour éviter un décalage négatif sur un
  CSD mal formé. La suite hôte utilise une carte SDHC simulée.
- Tests SD/FatFs avec injections CRC, image FAT32 et relecture indépendante
  par mtools : PASS (`sd_host.log`).
- `sd_port_present()` lit maintenant DET/GPIO 1 (actif bas), au lieu de
  répondre toujours « présent ». La carte physique est bien reconnue par le
  firmware C2 ; le retrait physique n'a pas été exercé à distance.

La documentation héritée indiquait une mauvaise polarité des sorties OE.
La sonde sur R40 reproduit les résultats du 5 octobre : seul COMBO=1,
OE haut et GPIO 0 en sortie, fait battre l'horloge et initialise la carte
de 31 116 288 secteurs. Après rechargement du FPGA, GPIO 4 revient à zéro
et ce R40 de diagnostic ne communique plus avec la SD.

Les sources actuelles du SoC, déjà corrigées avant cette reprise, fixent
OE haut et retirent ce sélecteur de diagnostic. La sonde est corrigée pour
laisser R40 dans le mode fonctionnel avant le téléchargement suivant.
Preuve : `reprise_20261007_sd_probe_c1/console.txt`.

## 6. Essais matériels du firmware corrigé sur R40

Application USBDISK téléchargée en ILM, sans écriture de flash :

- Disque DDR de 32 Mio : 8 Mio écrits à 5,51 Mio/s, relus à 7,07 Mio/s,
  CRC32 PC/firmware `DDA1A698`, identique. Zéro timeout/perte/resynchronisation
  (`reprise_20261007_disk_c1/`).
- SD : deux lectures de 8 Mio à environ 0,90 Mio/s, identiques, signature
  d'amorce 55AA, zéro timeout/perte/resynchronisation. Aucune écriture sur la
  SD physique pendant cet essai (`reprise_20261007_disk_sd_c1/`).
- Le CDC reste disponible sur le périphérique composite, HS 480 Mbit/s.
- Firmware C2 : douze READ10 de 64 Kio volontairement interrompus après
  512, 1 024 ou 1 536 octets, suivis de BOT Reset + Clear Halt et d'une
  relecture de 4 Kio. Les douze reprises donnent le même CRC32 `2f0c41e3`.
  `RESETS` passe de 0 à 12 ; `FAILED` de 1 à 13, conformément aux douze
  commandes abandonnées ; TIMEOUTS, LOSSES et RESYNCS restent nuls.
  WRITTEN reste nul. Preuve : `reprise_20261007_recovery_c2/result.json`,
  provenance du firmware et du script dans `usbdisk_c2_manifest.json`.

Ces essais vérifient le firmware corrigé sur l'ancien FPGA. Les essais du
bitstream corrigé C22 sont consignés séparément ci-dessous.

Confirmation visuelle reçue le 7 octobre pendant la compilation C19 :
« Oui, correcte et fluide » pour ORBITAL R6 (couloir, drones et tirs).
Cette confirmation concerne l'ancien FPGA R40 laissé en service.

## 7. Outil PC : écriture SD et identification de la cible

`check_usb_disk.py` protégeait la vue brute par `--allow-sd-write`, mais
la vue fichiers pouvait monter la SD et y écrire `ESSAI.BIN` sans cette
option. Les essais matériels de cette reprise utilisaient déjà `--no-files`
et n'ont donc pas emprunté ce chemin.

Correction : avec MEDIA=SD, la vue fichiers est omise par défaut, sans
montage. La vue brute conserve ses deux lectures de 8 Mio. Une écriture
explicitement autorisée utilise un nom FAT 8.3 unique créé exclusivement,
au lieu d'écraser un éventuel `ESSAI.BIN` préexistant. Le périphérique USB
est choisi par série 11252024, puis bus/adresse ; le CDC est ouvert en
mode exclusif.

`TESTS/test_usb_disk_tool.py` : trois tests passent sur ax15, avec accès
matériels simulés (SD par défaut, SD avec autorisation explicite, DDR).
Preuve et empreintes : `usb_disk_tool_policy.json`. L'interpréteur local
ne dispose pas de pyusb ; le test utilise celui d'ax15, qui possède déjà
les dépendances des outils de validation.

Essai matériel sur R40 avec la commande par défaut, sans `--no-files` :
la vue fichiers est bien omise sur SD ; deux lectures de 8 Mio à
0,90 Mio/s sont identiques, amorce 55AA. WRITTEN reste à zéro,
TIMEOUTS/LOSSES/RESYNCS également. Preuve :
`reprise_20261007_sd_readonly_default/`. ORBITAL est ensuite restauré.

## 8. Qualification matérielle C22

Bitstream `gpu_sdusb_c22`, SHA-256
`aacb08e0bca7d8948606cf497b2f2ba113476afd0e23adb80156ef89c7bfdadc`.
Chargement SRAM sur la Pro Dock FTDI 2023112818 d'ax15. Aucun chargement de
flash. Les répertoires cités sont sous `TESTS/reprise_20261007/`.

- Trois rechargements câble USB branché, nouvelle énumération HS 480 Mbit/s
  à chaque fois, 100 séries d'échos par rechargement : **1 632 300 octets
  binaires exacts**. `reprise_20261007_c22_reloads_r2/result.json`.
- Suite complète : G0/G1 DDR, G2 dessin/texte/copies, G3 16 couches,
  G4 64 sprites, G5 triangles, L11 tuiles, G6/FAST course, L12 affine,
  L13–L15 couleur/alpha/profondeur, perspective/composition, GPU V1.
  Empreintes couleur/Z/LCD et gardes exactes ; underflows nuls. La copie
  entre pages et le changement de cible Z passent (`V1 MEMORY PASS`).
  Journal : `reprise_20261007_c22_reloads_r2/gpu.log`.
- 300 requêtes EP0 alternant CDC7 et les deux pages diagnostic32 : réponses
  complètes, données CDC exactes, toujours HS.
  `reprise_20261007_c22_control/result.json`.

Deux incidents d'outillage sont distingués des résultats matériels : le
premier essai de rechargement s'arrête avant programmation, faute du
répertoire `bin` dans le PATH SSH ; la relance utilise explicitement ce PATH.
Ensuite, le chargeur ORBITAL lisait seulement 1 000 octets et trouvait les
anciens journaux V1 avant l'identité. Il s'arrête avant J-Link. Le chargeur
lit désormais jusqu'à une ligne d'identité complète, avec limites de temps
et de volume, puis choisit la commande de pause ou de libération du disque.
Une identité inconnue interdit le chargement. Trois tests de régression
passent (`TESTS/test_load_identity.py`) ; le chargement suivant franchit
correctement cette étape. Les outils ORBITAL et ILM partagent ce contrôle.

USBDISK C3 ajoute la commande `d`, qui sélectionne explicitement le disque
DDR de 32 Mio sans retirer ni écrire la SD. Elle permet de vérifier les deux
sens USB sur la carte équipée d'une SD. `m` retrouve la SD. Le transport et
le pilote SD restent ceux de C2. Programme : 20 024 octets, BSS 5 664 ;
commande de compilation et empreintes dans `usbdisk_c3_manifest.json`.

Stockage avec C22 et USBDISK C3 :

- SD reconnue au premier démarrage, **31 116 288 secteurs**, sans le
  sélecteur GPIO 4 du diagnostic R40. Deux lectures de 8 Mio identiques,
  environ 0,90 Mio/s, CRC32 `fd8d135d`, signature 55AA. La commande par défaut
  omet bien le montage ; WRITTEN=0. `reprise_20261007_c22_sd_readonly/`.
- Douze lectures interrompues après 512/1 024/1 536 octets : douze resets BOT
  pris en compte, douze relectures identiques, CRC32 `2f0c41e3`.
  FAILED augmente exactement de douze, comme attendu pour les commandes
  abandonnées ; TIMEOUTS/LOSSES/RESYNCS=0, WRITTEN=0.
  `reprise_20261007_c22_disk_recovery/`.
- Sélection explicite du disque DDR : 8 Mio écrits à **5,56 Mio/s**, relus
  à **7,14 Mio/s**, CRC32 `cef0ebe5` identique côté PC et firmware. Les
  lectures de tailles variées passent et la lecture hors capacité est
  correctement refusée avec résidu 1 024 et sense 052100.
  TIMEOUTS/LOSSES/RESYNCS=0. `reprise_20261007_c22_ddr_disk_r2/`.
  Un premier répertoire nommé `c22_ddr_disk` correspond en réalité à une
  lecture SD supplémentaire : la sélection DDR n'avait pas été exécutée
  à cause d'un échec SSH. Il n'est pas utilisé comme preuve DDR.

Les compteurs FAILED comprennent les commandes SCSI volontairement refusées
et les lectures interrompues ; ils ne doivent pas être présentés comme nuls.
La SD physique reste exclusivement lue dans cette qualification. Son
écriture et son retrait physique ne sont pas validés par ces essais.

ORBITAL R6 est ensuite restauré depuis l'ILM ; le CRC de ses 5 781 728 octets
de ressources est `7bf044fa`. Le téléchargement complet a pris 331,6 s.
ORBITAL R6 : **51 images de référence exactes**, 520.7 s d'endurance, **28 549 images** (deux boucles complètes), **54.83 images/s**, 3264 octets d'écho USB exacts. Zéro underflow, erreur de dessin ou commande rejetée. Dessin maximal 16.348 ms ; composition maximale 1007/2556 cycles par ligne. Le périphérique USB conserve la même adresse et le mode HS. L'utilisateur confirme C22 : « Oui, correcte et fluide ». ORBITAL reste en lecture automatique.

Le transfert volontaire de propriété du disque au lecteur matériel conserve
la limite décrite dans `ARCHI/SD_USB_DISQUE.md` : une commande hôte arrivant
exactement à la restitution peut nécessiter un reset BOT de récupération.
La qualification ci-dessus ne prétend pas supprimer cette fenêtre.


Archivage final : `bitstreams/console_gpu_sdusb_800.fs`, SHA-256, manifeste
des 121 sources et bilan `.validation.json`. L'archive `c22_sources.tar.gz`
contient les sources figées, options, contraintes résolues et audits ; chaque
empreinte du manifeste est recontrôlée. La copie du bitstream sur ax15 a
le même SHA-256. À la clôture de cette qualification, les sources RTL et le SDC correspondent à C22 ;
le CST d'entrée correspond à `usb_phy_ip/gpu_base.cst` avant les adaptations
explicites du script de build (`c22_worktree_match.json`).

Les fichiers de travail sont conservés sans commit/push dans cette reprise.
`git diff --check` ne signale que 26 espaces de fin de ligne hérités dans
`usb_descriptor.v` ; ce fichier n'est pas reformatté après sa validation.
Le contrôle hors de ce fichier passe.

Suite à la revue contradictoire, l'arbre de travail reçoit les corrections
décrites dans [`CORRECTIONS_REVUE_20261008.md`](CORRECTIONS_REVUE_20261008.md).
Les fichiers figés et résultats C22 ci-dessus restent historiques.
