# Neo : diagnostic R3 et rapprochement de la référence Pro Dock

État au 22 octobre 2026. La Pro Dock G22r0 / Linux NEBULA R17 restaurée
reste intacte ; son essai matériel est consigné séparément dans
`TESTS/prodock_restore_20261021/`. Aucun résultat Neo ci-dessous ne qualifie
une modification pour la Pro Dock.

## État courant après les essais R3

R3 a été remplacé par **N56r1** pour tester le démarrage du Linux 720p avec
le chemin 2D déjà comparé pixel par pixel. Les résultats sont dans
`../n56r1_linux_20261022/`. Le transfert et la vérification du payload compact
de 3 465 332 octets passent. Le chargeur indique `passed=false` car aucune
bannière UART ne revient ; cette qualification n'est pas réécrite.

La lecture JTAG du journal noyau prouve néanmoins le démarrage de Linux,
l'initialisation GPU 720p/texte, deux ports manettes et la détection SDXC.
Le compteur de temps noyau progresse et le CPU est observé dans la boucle
d'attente Linux. Cela ne valide ni NEBULA, ni les pixels HDMI, ni l'USB HS.

Le témoin de 17 octets écrit directement dans UART2 ne revient pas davantage
par le relais Sipeed. Le menu propre au programmateur répond. Le précédent
consigné dans le projet analyseur (`TESTS/TESTS_USB_ANALYSE_2026-09-29.md`,
passerelle UART G54) indique un relais muet après l'entrée au menu, rétabli par
une coupure complète. Sa commande `reboot` lance une autre application sans
JTAG : elle **n'a pas été utilisée**.

Une coupure physique de la Neo a été demandée. Avant celle-ci, le CPU a été
identifié à nouveau et laissé **arrêté à 0xc0192806** ; preuves dans
`../n56r1_linux_20261022/before_power_cycle/`. Aucun accès carte concurrent
n'est prévu pendant cette intervention. Le chargeur Neo reçoit une option
explicite `--preserve-uart-route` pour le prochain essai après coupure : elle
évite les séquences d'entrée dans le menu sans changer les contrôles FPGA,
mémoire, payload ou validation du démarrage. Ce correctif n'est pas encore
validé matériellement ; sa campagne locale est consignée séparément.

La campagne `TESTS/dual_board/20261022_uart_route/result.json` passe les
11 groupes sans changement d'entrées pendant l'exécution. Les 26 tests
Python de récupération/diagnostic passent également. Ce résultat local
ne qualifie pas le relais physique ni un nouveau bitstream.

Les extractions `kernel_strings.txt` sont une aide de lecture du buffer brut,
pas un décodage des descripteurs `printk_info.text_len`. Les deux caractères
supplémentaires visibles à la fin de nombreuses chaînes correspondent au
suffixe laissé après retrait du préfixe de niveau par `printk_sprint()`
(`linux/build-neo/src/linux-6.12.112/kernel/printk/printk.c`, lignes 2164–2186).
Le buffer n'est pas terminé à la longueur utile ; ces suffixes ne sont donc
pas, à eux seuls, une preuve de corruption DDR.

## Image R3 précédemment chargée et limites

Neo N56r3, SHA-256
`77a76cdc6d16aaa34a939296cc74ed7f6e29980682ac2756b6b2658ae443fbe2`.
CPU arrêté dans le parking, scanout désactivé, Linux non démarré.
Ni flash ni SD écrite. L'ancre de récupération est `board/`.
Cette ancre historique ne décrit plus le CPU courant après l'essai Linux R1.

Le chargement utilise le mode de diagnostic préliminaire existant, limité
au CPU arrêté. La qualification statique reste **FAIL** : deux chemins
setup d'observation négatifs et reset pixel encore distribué sur LW.
Le succès du chargement et du prétest DDR n'est pas une qualification GPU.

## Résultat matériel reproductible

`mesh_inside/result.json` : les onze fences terminent, zéro erreur de
transport/perte, mais deux rejets internes et deux erreurs géométriques.
Zéro vertex, triangle ou pixel calculé. Les surfaces couleur/profondeur
restent à leur valeur d'effacement ; 6 313 / 6 400 octets diffèrent de la
référence. La fenêtre texture/mesh de 1 Mio est identique à la référence.
Les trois fenêtres de 1 Mio, y compris leurs gardes, ont été comparées.

`mesh_commands_r1/result.json` isole chaque commande. Les vertices et la
face sont revérifiés avant le rejeu, qui réutilise les fenêtres déjà
initialisées ; ce second test n'affirme pas une nouvelle comparaison de
toutes les gardes.

| Commande | Résultat |
| --- | --- |
| TARGET, clip, clear, texture | Acceptées, en-têtes géométrie/pixel attendus |
| CAMERA (opcode 32) | Rejet géométrique +1, en-tête 0x20000000 correct |
| Trois lignes de matrice, lumière, matériau | Acceptées |
| DRAW (opcode 34) | Rejet géométrique +1 ; compteur de vertices traités inchangé |

`camera_configs_r1/result.json` : quatre TARGET acceptés, mais les
seize CAMERA valides sont toutes rejetées. Les tailles sont 160×100,
1×1 et 32×32 ; les focales 1/32/80/160, avec deux centres et répétition.
La caméra volontairement invalide (`near=0`) est correctement rejetée.
Le transport termine sans erreur. Le script historique de configuration
retourne 0 quand la capture est complète, même si les attentes diffèrent :
le verdict pertinent ici est **all_expectations_match=false**, pas le code
de sortie du processus.

Les mêmes 21 commandes passent dans la simulation de la netlist routée
R3 avec primitives officielles, sans SDF :
`../n55_gpu_diagnosis_20261021/n56r3_camera_routed/result.json`.
Ce test exclut la DDR physique et les délais. Il ne contredit pas le
défaut observé sur la carte.

## Hypothèse vérifiable et essai suivant

Le signal d'activation CAMERA `u_accel/u_v1/n57378_3` est distribué sur
LW. Son cône logique est identique entre R1 et R3. Il commande 198 CE de
DFF et six entrées CE de DSP ; aucune entrée d'horloge. Une absence de
capture expliquerait une focale invalide au calcul des ratios, mais les
registres internes ne sont pas exposés : cette cause n'est pas encore
prouvée. Le reset pixel LW constitue aussi une différence physique.

La variante R4, avec sept contraintes de placement, n'a pas été chargée :
setup −0,489 ns, recovery −1,946 ns. Son résultat est conservé dans
`../n55_gpu_diagnosis_20261021/n56r4_placement/result.md`.

R5 repart exactement de R3 et ajoute deux contraintes LOCAL_CLOCK pour
CAMERA et FACE. Aucun placement R4, changement RTL, DDR, SDC ou fréquence.
Manifestes et preuves sont dans
`../n55_gpu_diagnosis_20261021/n56r5_geometry_controls/`.
Il reste à contrôler le routage effectif, tous les timings et les essais
matériels ; aucun succès n'est présumé.

Résultat R5 : setup −0,234 ns (deux chemins d'observation), hold +0,124 ns,
recovery +0,167 ns, removal +0,145 ns. Les activations CAMERA/FACE quittent LW,
mais trois resets utilisent encore LW malgré les contraintes présentes.
Qualification **FAIL**, aucun chargement matériel. Les primitives et charges
des commandes ciblées restent identiques ; voir
`tang/impl/console_neo_n56r5/geometry_controls_audit.json` depuis la racine.

## USB HS

`usb_before_r1/` mesure R1, `usb_on_r3/` mesure R3. Dans les deux cas,
status UMSC vaut 2. La trace passive acquitte ses commandes, mais observe
environ une indication RXERROR tous les cinq cycles, sans token ni SOF
sur la fenêtre mesurée. Ces compteurs ne prouvent ni la fréquence réelle
ni une négociation HS. Ils ne sont pas un diagnostic analogique du câble.

L'audit des sources révèle les anciennes IP Sipeed/Gowin 2024 dans Neo,
alors que G22r0 utilise Controller 3.3 et SoftPHY 3.5 Advance/V_120.
Le générateur local `usb_ip_candidate/generate_usb_neo.py` a produit les
deux IP officielles pour GW5AST-138C / PBGA484A, avec les macros de G22r0
inchangées. Résultat `usb_ip_candidate/generated/result.json` :
**GENERATED_NOT_INTEGRATED**.

- Contrôleur : `f11307d3e31560be2b04dff32b020c969f0ada2610ef232ab648fef2f198ee2a`.
- PHY : `5a1eb8388ad4afe13825dd5f650a3a82628f919e337c93426b9d60e41846abaa`.

La synthèse isolée N57 remplace uniquement ces deux fichiers dans une
copie du snapshot N56, sans routage ni accès carte. Les noms synthétisés
des contrôles GPU doivent être résolus à nouveau avant tout routage ;
les numéros de nets N56 ne constituent pas un contrat de nommage.
L'énumération à 480 Mbit/s et les transferts restent à vérifier sur carte.

## Essais empêchés par l'environnement

Les dossiers `mesh_commands/`, `camera_configs/` et `usb_before/`
conservent les échecs initiaux `libusb_init` dans le bac à sable. Aucun
de ces essais n'a accédé à la carte. Les mesures matérielles effectives
portent les suffixes indiqués ci-dessus ; ces échecs d'environnement ne
sont pas assimilés à des défauts du FPGA.
