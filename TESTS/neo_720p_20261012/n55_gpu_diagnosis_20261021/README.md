# N55r2 — diagnostic de la réception des commandes GPU, 21 octobre 2026

## Conditions et limites

Neo locale uniquement, N55r2 déjà chargée, SHA du bitstream enregistré par le
chargeur : `eceafd6ae5ebe85746db1be5be28a5c64d73278a6264ae629dd39eecf873ba1e`.
Ancre : `../board_n55r2_reload_20261021`. CPU vérifié dans la boucle de parking
à `0x80000004`, privilège M, instructions de parking vérifiées. Scanout arrêté.
Les nouvelles sondes prennent le verrou `TESTS/neo_board.lock` et n'envoient que
des commandes de configuration : aucun DMA, aucun démarrage CPU, aucune écriture
SD/flash, aucun rechargement FPGA. Aucun accès à la Pro Dock éteinte.

La qualification temporelle de N55r2 passe, mais ce n'est pas une qualification
fonctionnelle. Les essais ci-dessous observent les registres MMIO et les fences ;
ils ne donnent pas encore les valeurs internes réellement capturées par le GPU.

## Observations sur carte

`config/result.json` et `config/openocd.log` :

- 80 commandes : 29 TARGET, 11 configurations matériau/texture/plan/invalidation/
  matrice/lumière, quatre répétitions du TARGET initial, 36 tailles de TARGET
  allant de 1×1 à 32×32.
- 71 commandes valides et neuf volontairement invalides selon l'ABI.
- Chaque commande termine ; 640 mots hôte sont comptés, sans perte ou erreur
  de transport enregistrée. Fence de 1 à 81.
- Le compteur de rejet V1 augmente pour **les 80 commandes**, donc aussi pour
  les 71 valides. Le compteur d'erreurs géométrie reste nul, même pour la matrice
  invalide. Le compteur de cycles géométrie augmente de deux par commande
  (ce compteur exclut les attentes du shader).
- Le snapshot debug reste à `status=5` : source prête, busy=1, valid=0,
  séquence=0. Aucun nouveau snapshot cohérent n'est utilisé pour ces résultats.

`counter_witness/result.json` et son journal vérifient une autre explication :
le compteur « rejet » aurait pu être une mauvaise lecture du fence, puisque
leurs valeurs étaient jusqu'alors égales. Trois configurations affine legacy
(opcode 12, sans DMA), alternées avec trois INVALIDATE, donnent :

| Commande | Fence | Rejet V1 | Erreur géométrie |
|---|---:|---:|---:|
| Affine legacy, trois répétitions | +1 chacune | 0 | 0 |
| INVALIDATE, trois répétitions | +1 chacune | +1 chacune | 0 |

État final : fence=87, rejet=84, cycles géométrie=168 ; compteur de mots hôte=696.
Ce témoin écarte l'alias direct « lecture du rejet = lecture du fence ». Il ne
prouve pas à lui seul l'absence de tout défaut de lecture MMIO.

## Ce que cela localise

Le défaut observé dépasse le validateur des adresses TARGET. Il affecte aussi
des commandes qui ne demandent aucune lecture ni écriture DDR, y compris
INVALIDATE et des configurations géométriques.

Un paquet non capturé, resté nul, ou altéré entre le blitter et la géométrie
expliquerait ces résultats : un opcode inférieur à 31 est transmis au moteur
pixel, qui rejette un opcode nul. **Cette valeur interne n'est pas encore
mesurée** : cela reste une hypothèse, pas la cause établie. Un défaut du décodage
ou d'autres registres demeure possible.

Le RTL de `gpu_geometry.v`, `gpu_accel.v` et `blitter.v` est identique entre les
copies N38r0 et N55r2 ; les empreintes sont dans `source_comparison.json`.
N38 acceptait les configurations de référence sur carte. N55 ne change que
le masque et le sélecteur de perspective dans `gpu_v1.v` (28 lignes de diff),
mais le compilateur et le routage ont également changé. On ne peut donc pas
attribuer le défaut au seul changement de RTL.

Les différences avec la référence Pro Dock G22r0 sont conservées dans les
fichiers `*.prodock_n55.diff`. Elles sont plus larges que les deux modifications
N54/N55 ; aucune de ces différences ne doit être promue automatiquement sur
la Pro Dock.

Les cibles physiques des scripts figés diffèrent : Pro Dock G22r0 utilise
`GW5AST-138B / GW5AST-LV138FPG676AC1/I0`, Neo N55/N56 utilise
`GW5AST-138C / GW5AST-LV138PG484AC1/I0`. Leurs contraintes déclarent toutes deux
bus 80 MHz, cœur 800 MHz, DDR 300 MHz et interface DDR 75 MHz. L'appartenance à
la même famille ne rend donc pas leurs implémentations physiques identiques ;
cette différence ne constitue pas une preuve d'erratum du composant.

## Simulations des configurations après synthèse

`n55_mapped_config_r1/result.json` : les moteurs géométrie/pixels synthétisés
N55 passent les 80 configurations (40 cas après chacun des deux resets).
La netlist utilisée depuis N55_selector est identique bit à bit à la netlist
racine N55r2 : SHA-256
`cfe520568bf96dc1f696e7db48d7d89002da3e7d61131d94600437bef8c8fbfe`.

`n56_mapped_config/result.json` : le même contrôle passe sur les moteurs N56,
avec vérification des 64 bits d'observation de l'en-tête et interdiction des
quatre classes de requêtes mémoire. Les primitives proviennent du modèle
officiel de Gowin. Ce test vérifie aussi la capture malgré les modifications
du bus de commande pendant que les moteurs sont occupés.

Ces deux premiers tests isolent les moteurs. Le contrôle complémentaire
`n55_full_mapped/result.json` couvre ensuite le chemin GPU complet et passe :
80 commandes injectées par AHB, réception de 640 mots à travers la FIFO à
deux horloges, décodage du blitter, géométrie et pixels, fences et compteurs
attendus, snapshot debug achevé. Toute requête DDR déclenche un échec du banc.

Ce dernier banc extrait sans modification les modules mappés `gpu_accel`,
`neo_gpu_debug` et leurs dépendances transitives. Il conserve leurs connexions
mutuelles d'origine, car Gowin partage certains cônes de décodage entre ces
modules. Le modèle officiel des primitives est utilisé. Seuls le maître AHB,
les horloges/reset et l'extrémité DDR sont stimulés par le banc : DDR prête mais
sans aucun retour, données et tags de réponse laissés X. Les horloges sont
80/75 MHz avec un déphasage initial de 0,371 ns.

Ces simulations sont fonctionnelles après synthèse, sans SDF ni modèle de
métastabilité. Elles ne reproduisent pas la panne matérielle N55. Le CPU,
`video_bus_stage`, la DDR et les délais physiques de routage ne sont pas inclus
dans ce dernier banc. Un PASS n'établit pas l'équivalence après routage.

Le même banc complet passe également sur N56 après synthèse :
`n56_full_mapped/result.json` (80 commandes, snapshot achevé, zéro DMA).

`n55_full_routed_r2/result.json` ajoute le contrôle fonctionnel **après PnR**
sur le `.vo` exact de N55r2 : les 80 commandes passent, 640 mots reçus,
fences/rejets/erreurs attendus, snapshot achevé et aucune requête DDR.
L'extraction conserve textuellement les 86 894 primitives `u_accel` et
`u_gpu_debug` et leurs `defparam`. La fermeture transitive des pilotes s'arrête
aux seules frontières AHB/horloges/reset/DDR déjà décrites ; elle n'a nécessité
aucune cellule d'un autre bloc. Aucun modèle GPU n'est substitué. Ce résultat
vérifie les équations présentes dans le modèle fourni après PnR ; **sans SDF,
il ne vérifie ni les retards physiques ni l'exécution réelle du bitstream**.

Les dossiers `n55_full_routed` et `n55_full_routed_r1` conservent deux erreurs
de préparation du banc (collision du nom `clk`, puis noms de signaux de
surveillance non adaptés à l'aplatissement). Ils n'ont pas exécuté de
simulation fonctionnelle. La version `_r2` corrige uniquement ces raccordements
du banc ; les instances et paramètres extraits du `.vo` restent inchangés.

`n55_full_routed_empty_interword_r1/result.json` passe également : le banc
ajoute 12 périodes hclk avant chacun des 640 mots et exige à chaque fois
`rd_bin == wr_bin_r` ainsi qu'un registre de tête invalide. Les 80 commandes,
compteurs et snapshot passent toujours. Cela couvre les reprises après FIFO
vide entre les mots, plus proches du rythme JTAG. Le premier dossier sans
suffixe `_r1` conserve une erreur de nom du signal de surveillance dans le
banc, avant toute simulation ; `_r1` utilise les nœuds aplatis vérifiés.

## Expérience suivante préparée

`prepare_observer.py` vérifie les empreintes N55r2 et produit une copie figée
dans `candidate/source`. Cinq fichiers seulement diffèrent, tous dans cette
copie. `candidate/observation.diff` est la modification revue.

Le GPU reçoit uniquement de nouvelles **sorties** d'observation ; aucun de ses
registres, expressions de contrôle ou affectations fonctionnelles n'est modifié.
Le port debug ajoute trois lectures :

| Adresse | Contenu |
|---|---|
| `0xe9005018` | `gpu_geometry.captured_command[31:0]` |
| `0xe900501c` | `gpu_v1.packet[31:0]` |
| `0xe9005040` | requête/ACK et étapes de synchronisation, reset-ready, busy/valid, `ext_command[31:24]` |

Le registre de statut existant conserve son ABI (`status==6` pour un snapshot
achevé). Les champs supplémentaires traversent chacun deux FF `hclk`, sans
dépendre du handshake défaillant. **Ce ne sont pas des captures atomiques** :
ils ne seront interprétés qu'au repos, après plusieurs lectures identiques.
Ils ne pilotent ni le GPU, ni le handshake d'origine. Les trajets bus80↔DDR UI
restent soumis à la borne existante de 8 ns ; aucune nouvelle exception SDC.

`observer_sim/result.json` : quatre tests passent :

1. Debug à 80/75 MHz, avec reset et arrêt de l'horloge source.
2. Debug avec dérive et autre phase (demi-périodes 6,29/6,61 ns).
3. Debug à 125/124,5 MHz, autre phase.
4. Les 80 configurations précédentes dans le vrai RTL GPU : résultats attendus,
   en-têtes observés exacts, fences/compteurs exacts, snapshot existant préservé,
   aucune requête DDR.

Les tests du port debug vérifient aussi la disponibilité des nouvelles lectures
pendant qu'un snapshot attend une horloge arrêtée. Ce sont des simulations RTL,
sans SDF ni modèle de métastabilité. Elles ne reproduisent pas encore la panne
physique de N55r2.

`build_observer.py --name console_neo_n56_observe --check-only` vérifie :
la garde commune de non-régression Pro Dock/Neo, les 21 fichiers du profil DDR,
les cinq seuls fichiers modifiés, les sources des simulations et les manifestes.
Sans `--check-only`, il crée un nouveau build isolé avec les contraintes exactes
N55r2, la liste de synthèse N55_selector, Gowin courant et `replicate_resources=0`.
Il ne charge aucune carte. Les marges de la nouvelle compilation devront être
contrôlées avant l'essai matériel.

La compilation isolée `console_neo_n56_observe` a ensuite été démarrée par la
session principale, après la campagne commune `TESTS/dual_board/20261021_r2`
(11 tests sur 11). Elle reste distincte des sources communes et ne sera pas
chargée avant qualification et revue des résultats.

## Sonde de l'observateur, préparée sans exécution

`probe_observer.py --build tang/impl/console_neo_n56_observe --failed-load
<ancre de chargement N56> --out <nouveau dossier>` :

- Refuse une qualification FPGA autre que PASS, un bitstream/report/netlist
  changé, une ancre d'une autre version ou des sources modifiées. Ne propose
  aucune dérogation de timing ou de routage.
- Vérifie le parking CPU, l'arrêt du scanout, les identifiants GPU/NGDB et un
  témoin lecture/écriture/restauration du registre d'adresse de police.
- Écrit uniquement une page DDR de 4 Kio à `0x12000000`, puis la relit et la
  vérifie avant et après les commandes. Ce test n'est pas une endurance DDR.
- Envoie 13 configurations connues, dont deux témoins affine legacy, et lit
  chaque jeu de données brutes trois fois, avec 2 ms d'espacement, GPU au repos.
- Demande trois snapshots successifs quand le port le permet, enregistre les
  requêtes, ACK et compteurs de séquence. Un snapshot bloqué reste un résultat
  diagnostic ; il ne masque pas les en-têtes bruts disponibles indépendamment.
- Limite le processus OpenOCD à 60 s et détient le verrou de la carte. Aucun
  dessin, aucune reprise du CPU, aucune programmation FPGA/SD/flash.

Les contrôles locaux de génération ont vérifié les 104 mots/13 commandes,
l'absence d'instruction de reprise/programmation, le refus des chemins Tcl
non sûrs et le signalement de lectures répétées instables. Cette sonde n'a pas
encore été exécutée sur carte au moment de sa préparation.

## Résultat N56 et essai diagnostic demandé explicitement

N56 termine mais sa qualification est **FAIL** : setup −0,276 ns sur 22
endpoints, hold +0,124 ns, recovery +0,511 ns, removal +0,145 ns. Tous les audits
structurels passent. Les contraintes et fréquences restent celles de N55r2.
Le trajet nouveau `packet[25] → observe_words_s1[57]` manque la borne CDC de
8 ns de 0,253 ns. Les pires autres trajets touchent le CE des données du pont
CPU, le CE de l'index géométrique, le DMA legacy et le lecteur de tuiles.
Les deux avertissements PR1014 (`clk_d`, `ae350_tck_d`) existent déjà dans N55r2.
`gpu_clk` et `vid_hclk` restent déclarées PRIMARY dans le rapport physique.

Le chargement a d'abord été suspendu. L'utilisateur a ensuite demandé
explicitement **« test le N56 »**. L'exception setup déjà existante du chargeur
a été utilisée pour ce bitstream exact, sans relâcher les autres contrôles :
`ecef1e120d9940bab6b28bac12557e87f0790e8610cf6788326220bd38db0f3a`.
La sonde locale accepte exceptionnellement ce seul SHA avec
`--diagnostic-bitstream` ; sans cet argument, N56 FAIL reste refusé. La
qualification reste FAIL dans les preuves. Aucun outil partagé n'a changé.

`board_n56_diagnostic/` : programmation SRAM confirmée, ILM et deux pages DDR
vérifiées deux fois ; TARGET termine mais est rejeté (compteur V1 0 → 1).
`observer_n56_diagnostic/` est un échec libusb du bac à sable avant accès à la
carte, conservé comme échec technique. Le nouvel essai avec l'accès autorisé
est `observer_n56_diagnostic_r1/result.json` :

- Capture complète, témoin MMIO lecture/écriture/restauration exact ; page DDR
  de 4 Kio exacte avant et après les 13 configurations.
- 13 fences terminent. Les deux configurations affine legacy passent ; les
  11 configurations V1 sont rejetées, sans erreur de transport enregistrée.
- **L'opcode `ext_command` suit exactement les commandes**, mais les deux
  en-têtes observés (géométrie et pixels) restent à zéro. Tous les triplets
  de lectures espacées de 2 ms sont identiques.
- `mem_up=01` reste stable, `ready_s=00`, statut debug=0. Le test n'envoie donc
  aucune requête de snapshot, car le domaine source n'annonce jamais prêt.
  Ce résultat diffère du statut 5 de N55 : l'init du debug est aussi affectée.
- CPU confirmé arrêté à `0x80000004`, GPU au repos, fence=14, rejet V1=12,
  cycles géométrie=24. Aucun DMA de dessin, Linux, scanout, SD ou flash.

Le point de perte de l'en-tête est maintenant observé : l'opcode arrive au
blitter, mais la capture géométrique observée reste nulle. Cela ne qualifie pas
le GPU et ne constitue pas encore une preuve de la cause physique, notamment
avec le setup N56 en échec. Deux autres faits rapprochent l'enquête d'une
expérience discriminante : dans N55, le CE de `captured_command` et le CE
ACK/held du debug utilisent LW ; N56 conserve ces deux fonctions sur LW et
route aussi `mem_up[1]` sur LW. Le modèle `.vo` passe avec les primitives
officielles ; une expérience sur ces routages reste nécessaire avant toute
conclusion sur le silicium ou l'outil.

## N56r1 : comparaison de routage lancée

`build_local_controls.py --name console_neo_n56r1` est lancé après revue de
`n56r1_local_controls/control_proof.json`. Gowin a accepté les contraintes et
commencé le placement. La synthèse est sautée : le fichier `.vg` est celui de
N56, ainsi que les sources RTL, la DDR 5.9, les fréquences et le SDC. Les trois
seuls ajouts au CST sont les contraintes `LOCAL_CLOCK` détaillées dans
`n56r1_local_controls/constraints.diff`. Les contraintes `INS_LOC` restent
identiques ; les positions physiques et le routage seront recalculés.

Build : `tang/impl/console_neo_n56r1`, journal `build.log`. Le résultat du
routage, la prise en compte effective des trois contraintes et le timing sont
encore en attente. Aucun chargement N56r1 n'a eu lieu. La Neo reste arrêtée sur
le N56 diagnostic ; la Pro Dock n'a pas été sollicitée.

## N56r1 terminé : capture réparée dans une comparaison reproductible

Bitstream N56r1 :
`426389b02a4c1c240a28a711546569315e5c4d9478199f12e1e38f46009d3d2d`.
La qualification reste **FAIL** : setup −0,440 ns / trois endpoints,
hold +0,124 ns, recovery +0,511 ns, removal +0,049 ns, pulse +2,034 ns.
Tous les audits structurels passent. Les trois chemins setup restants sont
`packet[17] → observe_words_s1[49]`, `st[1] → m_hrdata[3]/CE` et
`v1_select → état pixel[13]`.

`tang/impl/console_neo_n56r1/local_controls_audit.json` vérifie que les trois
pilotes, INIT, connexions et charges sont identiques au parent. Les trois
réseaux ne figurent plus dans le tableau complet des ressources globales.
Cela utilise les rapports Gowin, sans décodage indépendant du bitstream.

Les essais ci-dessous restent des diagnostics avec exception setup ciblée sur
le SHA exact, qualification FAIL conservée. Aucun contrôle hold/reset,
structurel, de source ou d'identité n'a été supprimé. Aucun outil partagé de
qualification n'a changé. La sonde locale distingue les deux noms/SHA N56 et
N56r1 et vérifie en plus les empreintes de l'audit des contrôles N56r1.

`aba_result.json` conserve les preuves de la séquence :

| Image / essai | TARGET | En-têtes géométrie/pixels | Captures debug |
|---|---|---|---|
| N56 / initial | rejeté | nuls | pas prêt, `mem_up=01` |
| N56r1 / B1 | accepté | exacts | séquences 1, 2, 3 terminées |
| N56 / A2 | rejeté | nuls | pas prêt, `mem_up=01` |
| N56r1 / B2 | accepté | exacts | séquences 1, 2, 3 terminées |

À chaque essai, les 13 commandes terminent, les triplets de lectures au repos
sont identiques et la page DDR témoin de 4 Kio reste exacte. Sur N56r1, les
13 attentes sont satisfaites, y compris les deux commandes invalides rejetées
par les bons compteurs ; `mem_up=11`, `ready_s=11`. L'ancre matérielle courante
est `board_n56r1_aba_b2/`, prétest complet réussi, CPU arrêté.

**Interprétation :** la panne de capture suit ces deux bitstreams de façon
reproductible. Les trois contraintes sont la seule différence d'entrée, mais
Gowin a recalculé tout le placement/routage. Cela ne suffit pas à désigner un
seul des trois réseaux, à conclure que tous les LW sont défectueux, ni à
prouver un erratum silicium. Le RTL, la netlist de synthèse, la DDR 5.9/300 MHz
et le SDC sont identiques.

`config_n56r1_b2/result.json` : **80/80 configurations conformes**, 640 mots
envoyés, aucune variation des compteurs de commandes mal formées/perdues.

Les cinq diagnostics `pixels_n56r1_{solid,alpha,depth,textured,perspective}`
passent chacun : trois fenêtres DDR de 16 Kio comparées octet par octet,
zéro différence, compteurs exacts, CPU arrêté. Ils couvrent le dessin plein,
la transparence, le test de profondeur, le texturage et la perspective.
Les gardes vérifiées se limitent aux fenêtres de 16 Kio, pas aux fenêtres
complètes de 1 Mio. Le test mesh `pixels_n56r1_geometry_inside` **échoue** :
11 fences terminées, neuf sommets, un triangle et 3 200 pixels traités comme
attendu, mais deux rejets V1 au lieu de zéro. Les trois fenêtres complètes de
1 Mio sont relues : 6 380 octets couleur et 6 400 octets profondeur diffèrent ;
texture/mesh restent exacts. Aucun échec de transport ni perte de commande.
Linux et le scanout restent arrêtés ; aucun résultat d'affichage n'est inféré.

`mesh_trace_n56r1/` rejoue le même Tcl borné, sans modifier ses initialisations,
commandes ni comparaisons, en ajoutant seulement des lectures de compteurs et
d'en-têtes après chaque fence. Les commandes 0 à 9 passent ; le matériau
arrive avec l'en-tête correct `0x19000000`. Les deux rejets apparaissent pendant
DRAW (commande 10), dont l'en-tête capturé est bien `0x22000000`. Au retour,
l'en-tête pixel est **zéro**. Le RTL finit DRAW par `shader_command<=material`
dans RESTORE, après avoir aussi utilisé ce registre dans MAT_SEND.

Cela cible la conservation du matériau dans le moteur géométrique. Son CE
`u_accel/u_v1/n56864_3` reste en LW, avec 253 charges CE dans le netlist routé.
C'est une nouvelle hypothèse précise, pas une preuve que tous les LW sont
défectueux. N56r2 ne change pas ce contrôle : son objectif est uniquement la
fermeture des trois chemins setup. Une comparaison séparée de ce quatrième
contrôle est préparée avant toute conclusion sur le rendu 3D.
Le second dessin produit les mêmes trois images, octet pour octet, que le
premier : les 6 380 / 6 400 différences sont reproductibles. La capture des
11 lignes `MESH_TRACE` et de la fin du test est dans `command_trace.log` ; ce
fichier commence durant la troisième initialisation et n'est pas présenté
comme le journal OpenOCD complet. Le Tcl et les images initiales sont conservés.

Le rapport G22r0 conservé côté Pro Dock apporte une différence d'allocation
concrète : ses huit LW servent à `usb_app_reset`, `vid_hrstn`, `u_gpu/mrst[1]`,
`u_accel/mrst[1]`, `u_accel/engine_resetn[0:2]` et au reset de l'IP DDR.
Les CE de capture suspects de cette Neo ne sont donc pas sur LW dans ce
rapport de référence. Les netlists et intégrations des deux cartes restent
différentes ; cette observation ne démontre pas à elle seule la cause du
comportement, ni un défaut universel des LW.

## N56r2 : fermeture timing en cours

Après revue de `n56r2_placement/README.md`, le constructeur
`build_timing_placement.py --build-reviewed
e9b1715b50309be524aa2d603057eb1be3ad9cb5abba8b16a763ecaf66ad4e23`
a démarré `tang/impl/console_neo_n56r2`. Quatre `INS_LOC` régionaux ciblent les
trois chemins négatifs, en déplaçant ensemble les deux étages du synchroniseur
d'observation. Les trois `LOCAL_CLOCK` restent en place ; RTL, SDC, DDR,
fréquences et netlist ne changent pas. La compilation est en cours, sans
présumer de sa marge ni de son résultat matériel.

## Pro Dock rallumée pendant les essais

L'utilisateur signale la Pro Dock rallumée. L'hôte ax15 répond ; le programmateur
FTDI série `2023112818` et le J-Link série `000506005083` sont visibles. La
première inspection est uniquement en lecture : aucun chargement, arrêt CPU
ou changement du système Pro Dock. Cette présence USB n'identifie pas à elle
seule le bitstream actif et ne constitue pas une validation fonctionnelle.

## Contrôles de non-régression et résultat N56r2

À la demande « tu fais la non reg en même temps ? », la garde commune a été
revérifiée : les entrées sont toujours celles de la campagne
`TESTS/dual_board/20261021_r2/result.json`, 11 groupes réussis, SHA
`8fd58313b0eade895d55e4343cc14698256c61c36c3dfa660bd2b4b4329b6dcd`.
Les expériences N56r1/r2 changent leurs copies de CST Neo ; elles n'ont pas
modifié le RTL commun depuis cette campagne. Ce résultat reste local et
n'est pas une nouvelle validation matérielle Pro Dock.

N56r2 est terminé et **écarté du chargement** : setup −1,405 ns sur neuf
endpoints, recovery −0,278 ns, hold +0,130 ns, removal +0,123 ns. Les audits
structurels passent, mais le déplacement proposé ne ferme pas le timing et
introduit une violation recovery. Aucune exception recovery n'est appliquée.
La Neo reste sur N56r1, CPU arrêté ; aucun démarrage Linux ni accès SD/flash.

La Pro Dock est identifiée à distance ; le SOFT-USB 359f est absent. Les tests
Linux/NEBULA par CDC ne sont donc pas encore exécutables. L'identification du
FPGA en place est poursuivie par une lecture de statut non destructive avant
de décider comment retrouver l'environnement de test. Les limites exactes
de l'inventaire sont dans `prodock_readonly_20261021.md`.
