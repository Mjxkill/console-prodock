# Compatibilité Pro Dock / Neo et conservation de la référence

## Règle de travail

La Pro Dock fonctionnelle doit rester reproductible pendant le port Neo.
Le code commun reste unique. Les différences de carte et les expériences
sont déclarées ; un correctif Neo n'est pas implicitement une modification
validée sur Pro Dock. Au début du diagnostic du 21 octobre 2026, la Pro Dock
était éteinte. Après sa remise sous tension, l'utilisateur a demandé son
rechargement complet. La référence exacte G22r0 / Linux NEBULA R17 a été
restaurée et revalidée sur carte ; les résultats sont dans
`TESTS/prodock_restore_20261021/README.md`. Cette restauration ne qualifie pas
les modifications ultérieures des sources communes pour la Pro Dock.

La liste exhaustive est dans [INVENTAIRE_CARTES.md](INVENTAIRE_CARTES.md).
Sa source machine est `tang/boards/ownership.json` : 511 fichiers classés,
247 communs, 161 propres à Pro Dock, 103 à Neo. Cette classification inclut
les constructeurs et les fichiers historiques ; ce n'est pas le nombre de
modules simultanément synthétisés. Chaque build conserve sa liste réelle
dans `sources.json`.

| Domaine | Commun | Pro Dock | Neo |
|---|---|---|---|
| GPU | Raster, géométrie, textures, blitter, couches/sprites/tuiles | Intégration LCD | Intégration HDMI et file de requêtes |
| CPU / mémoire | AE350, arbitres, adaptateur DDR d'origine, contrats AHB | Profil DDR de référence | FIFO CPU en registres substituée dans le snapshot |
| USB | Contrôleur HS, protocoles et blocs de transfert partagés | Contraintes électriques/placement Pro Dock | Brochage/horloges Neo et deux ports manettes |
| Linux | Pilotes GPU/texte/SPI, ABI, terminal, tableau de bord, jeu | `linux/prodock-linux.dts` | `linux/neo-linux.dts`, pilote manettes |
| Construction | Outils de contrôle et référence Gowin | `build_gpu*.py`, contraintes LCD | `build_console_neo.py`, `route_console_neo.py`, transformations `tools/neo/` |

Les noms `prodock-*` des pilotes ne désignent pas forcément des sources
spécifiques. Ils sont communs lorsque les deux profils les compilent.
Les fichiers générés et caches sous les dossiers de build ne sont pas
classés comme sources de développement.

## Référence conservée

- Commit antérieur au port : `b2b1ba84904ca428b9971de23c9957c81b15dc72`,
  NEBULA Linux R17, testé sur Pro Dock avec G22r0.
- FPGA : `tang/impl/gpu_geometry_g22r0`, 128 fichiers figés vérifiés.
- Bitstream : SHA-256
  `fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f`.
- Archive FPGA et sources exactes :
  `bitstreams/prodock_g22r0_reference_20261021.tar.gz`.
- Archive du commit logiciel/RTL, des outils et ressources NEBULA :
  `bitstreams/prodock_r17_sources_b2b1ba8.tar.gz`.
- Empreintes des fichiers et archives protégés :
  `tang/boards/prodock/reference.json`.

Ces archives ne doivent pas être supprimées lors du nettoyage des builds.
L'archive FPGA permet de retrouver le bitstream mesuré sans nouveau routage.
Une recompilation, notamment avec une autre version Gowin, produit un nouveau
candidat à qualifier : elle ne remplace pas ce bitstream historique.

**Limites historiques conservées :** G22r0 fonctionnait lors des essais, mais
son timing comportait un setup de −0,564 ns et neuf violations setup.
Les duplications occasionnelles de caractères CDC sont également consignées
dans `TESTS/NEBULA_20261012.md`. La protection de la référence ne transforme
pas ces constats en PASS.

Le paquet de travail `linux/build` diffère déjà du manifeste R17. L'archive
`prodock_r17_sources_b2b1ba8.tar.gz` conserve le **code du commit**, les ressources
et le manifeste historique. Une sauvegarde binaire complète a ensuite été
retrouvée dans `linux/build/golden_nebula_r17` : ses 14 fichiers ont été vérifiés
contre le manifeste historique, puis archivés dans
`TESTS/prodock_restore_20261021/r17_runtime.tar.gz`. Les empreintes et la
restauration sont consignées dans
[le rapport Pro Dock](../TESTS/prodock_restore_20261021/README.md).
Cette vérification ne concerne pas les autres paquets présents sous
`linux/build`. Un paquet reconstruit reste un candidat à identifier et tester.

## Contrôles exécutables

```sh
# Inventaire, empreintes de la référence, différences depuis le commit Pro Dock.
python3 tools/board_contract.py --out TESTS/dual_board/inventory.json

# Vérification de publication : échoue si les entrées ont changé depuis la référence.
python3 tools/board_contract.py --release-check

# Campagne locale complète, sans carte et dans un nouveau dossier.
python3 tools/run_board_regressions.py --out TESTS/dual_board/<nom-unique>
```

L'audit refuse les nouveaux fichiers non classés, les fichiers absents et les
sources remplacées par un lien symbolique. Il vérifie aussi les archives et
les fichiers figés G22r0. La campagne lie ses résultats au catalogue, aux
sources, aux outils, aux bancs de test et aux références Python. Le résultat
et chaque journal sont identifiés par SHA-256. Un résultat incomplet, périmé
ou modifié ne satisfait pas le contrôle préalable à la construction.

La campagne comprend : contrôle des gardes, équivalence AHB sur 250 000
cycles, CDC/arbitrage DDR pour les deux FIFO, USB MSC avec modèle officiel HS,
géométrie/pixels avec pauses et resets, composition de trois scènes NEBULA
800×480 et 1280×720, texte, tableau de bord et logique du jeu sur les deux
profils. Le profil Neo actuel utilise l'adaptateur DDR d'origine : la variante
de test ne substitue que la FIFO en registres, sans réintroduire l'ancien
adaptateur Neo « tagged ».

## Construction et validation

Les constructeurs FPGA Pro Dock et Linux Pro Dock refusent par défaut les
entrées modifiées. Un build expérimental est explicite :

```sh
python3 tools/build_gpu_geometry.py --name prodock_<essai> --candidate
make -C linux BOARD=prodock BUILD_ARGS=--candidate all
```

Les constructeurs Neo et les reroutages vérifient eux aussi la conservation
de la Pro Dock et la campagne locale courante. Chaque nouveau dossier reçoit
`board_contract.json`, distinct des sources synthétisées, qui conserve les
écarts et les preuves locales. **Tous ces nouveaux builds restent candidats**.
La garde ne déclare jamais une validation matérielle et ne met jamais à jour
automatiquement la référence.

Les transformations expérimentales `tools/neo/` travaillent uniquement sur
les copies figées Neo. Leurs tests spécifiques restent obligatoires : la
campagne du code commun ne valide pas à elle seule chaque transformation de
snapshot, ni son mapping ou son routage. Les anciennes copies figées ne sont
pas réécrites pour leur ajouter les nouveaux contrôles.

Pour une modification commune :

1. Décrire son effet sur les deux cartes et classifier les nouveaux fichiers.
2. Rejouer la campagne locale ; conserver toute régression comme échec.
3. Construire les deux candidats concernés ; vérifier mapping, CDC, reset,
   contraintes de broches et timing de chacun.
4. Sur chaque carte disponible, contrôler chargement/rechargement, DDR avec
   CPU et GPU, rendu, USB HS et console Linux. Tester la SD en lecture et les
   manettes lorsqu'ils sont concernés. Conserver SHA et résultats séparés.
5. Si une carte est éteinte, conserver l'étape matérielle en attente. Ne pas
   remplacer sa référence et ne pas promouvoir le changement comme validé.

Le binaire, le build logiciel, la qualification statique et la validation
matérielle sont quatre identités distinctes. Une conclusion de simulation
ou de timing ne vaut jamais preuve de fonctionnement sur la Pro Dock.

## Résultat du 21 octobre 2026

`TESTS/dual_board/20261021_r2/result.json` : **11 groupes PASS**, entrées
inchangées pendant les tests. Les trois scènes comparent **1 152 000 pixels
Pro Dock** et **2 764 800 pixels Neo**, sans différence ni underflow.
Le test géométrique compare **3 145 728 octets** et sept phases de reset.
Le modèle texte vérifie **8 355 840 pixels**. Le jeu passe 3 600 scènes et
78 167 commandes pour chacun des deux profils.

Le refus d'un build Pro Dock non marqué candidat a été vérifié : aucun
dossier de build ni processus Gowin n'a été créé. Les **57 entrées** changées
depuis le commit de référence restent listées dans
`TESTS/dual_board/inventory_20261021.json` ; elles incluent les outils/tests,
et ne représentent pas 57 changements du RTL. La référence Pro Dock G22r0/R17
a depuis été restaurée et testée : 384 000 pixels, trois scènes NEBULA,
10 000 images à 44,24 FPS sans erreur GPU et lectures SD répétées identiques.
Les essais Pro Dock des nouveaux candidats restent en attente.
La comparaison matérielle N56 / N56r1 / N56 / N56r1
reproduit l'échec de capture de commandes sur N56 et sa disparition sur N56r1.
Cette dernière variante change seulement trois contraintes de contrôle local,
avec nouveau placement/routage, et reste FAIL en timing (setup −0,440 ns).
Les prétests mémoire, les 80 configurations et cinq rendus pixel comparés
octet par octet passent sur N56r1. La Neo reste en diagnostic, CPU arrêté ;
le mesh 3D présente encore deux rejets internes et des pixels incorrects.
Linux et l'affichage ne sont pas encore qualifiés.
Les observations internes et leurs limites sont consignées dans
`TESTS/neo_720p_20261012/n55_gpu_diagnosis_20261021/README.md`.
Ce build n'est pas promu comme version fonctionnelle.

## Complément du 22 octobre 2026

Le chargement Linux sur N56r1 vérifie le payload compact et son lanceur.
L'UART ne confirme pas le démarrage, donc le résultat du chargeur demeure
FAIL. Les lectures JTAG du journal noyau prouvent néanmoins que Linux a
démarré et initialisé le GPU 720p/texte, la SD et les deux ports manettes.
NEBULA et la sortie HDMI ne sont pas encore qualifiés sur cette version.

Le retour UART Sipeed reste absent, y compris pour un témoin envoyé
directement par UART2. Une coupure complète a été demandée ; avant cette
intervention le CPU Linux a été laissé arrêté, avec son identité vérifiée.
Voir `TESTS/neo_720p_20261012/n56r1_linux_20261022/before_power_cycle/`.
Ce CPU n'est plus dans le parking des anciens prétests : ne pas réutiliser
leur ancre de récupération après ce démarrage Linux.

L'option `--preserve-uart-route` du chargeur propre à Neo permet le prochain
essai sans entrer dans le menu BL616. Elle ne change aucun garde FPGA,
mémoire ou qualification. Les 26 tests de récupération/diagnostic passent,
ainsi que les 11 groupes de la nouvelle campagne locale
`TESTS/dual_board/20261022_uart_route/result.json`. La validation matérielle
de cette option reste en attente. La Pro Dock conserve G22r0 / NEBULA R17.

### Essais du 22 octobre au soir, après coupure complète

Le rechargement N56r1 puis Linux avec `--preserve-uart-route` confirme cette
fois le boot par UART, avec CRC et payload vérifiés. La liaison reçoit encore
des caractères erronés, y compris lors d'un envoi lent ; NEBULA n'a pas été
lancé. L'écran noir est ensuite reproduit avec Linux arrêté, CPU garé et
framebuffer RGB565 seul, sans couches ni sprites : le balayage avance mais
aucune image mémoire n'aboutit. La mémoire de la mire est vérifiée par JTAG.

La mire interne de N56r1 conserve une somme vidéo `0x1ff8f800`, mais
l'utilisateur confirme **aucun signal HDMI**. Après son reset de carte,
l'analyseur en flash affiche une image ; les ancres N56r1 sont invalidées.
Une mire minimale sans CPU ni DDR isole ensuite la différence suivante :
**DCE PG0 visible → SG0 sans signal → retour PG0 visible**, puis PG0 imposé
explicitement également visible. Les trois variantes passent le timing
statique ; l'absence d'image ne nécessite donc pas la DDR. Ce résultat ne
démontre pas un erratum matériel général de SG0.

N56r7 route la même netlist de N56r1 avec seulement le placement HDMI
SG0 remplacé par PG0 et sa métadonnée mise à jour. La DDR 5.9/300 MHz,
les SDC, les resets et les huit exigences de clocks PRIMARY sont conservés.
La carte porte ensuite la mire minimale **SG4**, également confirmée visible,
**sans CPU ni DDR**. N56r8 route la même netlist N56r1 avec uniquement
SG0 remplacé par SG4 et sa métadonnée ; les huit exigences PRIMARY restent
obligatoires. Le succès SG4 exclut une panne générale de tous les sites SG,
sans identifier encore le mécanisme électrique de l'échec SG0.
La Pro Dock demeure inchangée. Le framebuffer et la console Neo restent
non qualifiés ; la simulation de première ligne avec l'arbitre routé passe,
sans reproduire le blocage de lecture sur carte. N56r6 finit FAIL en setup
et routage des resets, non chargé ; N57 finit FAIL en setup et recovery,
non chargé. Le contrôle N56r7 doit vérifier que PG0 conserve les huit
horloges PRIMARY ; cela n'est pas déduit du succès de la mire minimale.
Détails et résultats contradictoires conservés dans
`TESTS/neo_720p_20261012/reload_r1_cold_20261022/README.md`.

### 23 octobre : HDMI confirmé sur N56r8 complet

N56r7 PG0 finit FAIL : `clk_d` déplacé sur LW et removal −0,135 ns ; non
chargé. N56r8 SG4 conserve les huit PRIMARY et passe les audits structurels,
mais reste FAIL avec deux chemins de diagnostic en setup négatif, au pire
−0,144 ns. Son essai matériel utilise le SHA exact en mode diagnostic.
Le framebuffer isolé échoue encore : mémoire vérifiée, commit appliqué,
zéro image lue et +43 485 underflows sur environ une seconde.
Après rechargement du même bitstream, **la mire interne est visible**,
confirmée par l'utilisateur. Le problème HDMI et le blocage de lecture
vidéo sont ainsi séparés sur la console complète. La carte reste sur
N56r8, framebuffer désactivé, CPU arrêté dans le parking ROM, sans Linux.
Ni flash ni SD écrite ; aucune modification de la Pro Dock.

L'observateur de lecture N56r9 est ajouté uniquement dans une copie gelée
Neo : trois fichiers modifiés et un module de compteurs passifs, sans
modification des sources communes actives. Son test RTL 720p passe avec
trafic CPU concurrent et arrêt/reprise volontaire des retours DDR.
La synthèse réussit ; deux noms de contraintes devenus obsolètes bloquent
le placement initial. `console_neo_n56r9_route1` reprend sa netlist exacte,
avec les deux cibles remappées après vérification des fonctions. Le CST
est accepté. Les 11 groupes locaux repassent dans
`TESTS/dual_board/20261023_scan_route1/`. Le routage termine ensuite avec
setup **−4,103 ns**, 194 endpoints en violation ; hold +0,124 ns,
recovery +0,317 ns et removal +0,314 ns. Les huit PRIMARY sont conservés,
mais le build reste **FAIL, non chargé**.

L'audit strict des 713 registres des observateurs relève 374 changements
de nom de reset. Une preuve séparée établit qu'ils utilisent tous une
copie d'inverseur du même `!vid_hrstn`, avec mêmes fonctions, horloges et
INIT des registres. Le rapport initial FAIL est conservé ; cette équivalence
logique ne valide ni la distribution physique du reset ni le timing.

Le pire chemin du blitter fait un détour par une LUT maintenue à R45C45
par une contrainte héritée, alors que la logique voisine est à R7–R9,
C156–C170 : deux liaisons totalisent 12,074 ns. N56r9_route2 reprend
**la même netlist**, déplace cette contrainte vers R[1:25]C[140:175] et
ajoute 28 contraintes régionales proposées par l'outil d'optimisation.
Seul le CST de la copie gelée Neo change. DDR, SDC, fréquences, SG4 et
contraintes LOCAL_CLOCK sont conservés. Les 11 groupes repassent dans
`TESTS/dual_board/20261023_scan_route2/` et le nouveau routage est lancé.
Son timing et son essai carte restent en attente ; aucune cause du blocage
du framebuffer N56r8 n'est encore établie.
La Neo reste sur la mire interne N56r8 confirmée visible ; Pro Dock inchangée.

### Essai de N56r9_route2 demandé malgré le timing

Route2 termine avec setup −1,848 ns (172 violations), hold +0,124 ns,
recovery −1,418 ns et removal +0,179 ns. À la demande explicite
« teste le quand même », le SHA
`150bd72724ef7ec79c511afe2cc1c01f5976113ec00c39e8fc15e1f272731a01`
est chargé sur Neo en mode diagnostic, CPU arrêté, sans Linux. La
qualification reste FAIL ; l'exception de recovery est limitée à ce SHA
et aux valeurs mesurées, sans modifier les gardes des autres versions.

Le framebuffer est écrit et vérifié en DDR, mais le lecteur reste en IDLE,
avec zéro requête acceptée et zéro retour. L'observateur lit `mrst=01` :
premier étage libéré, second à zéro. Cinq captures supplémentaires et deux
rechargements du même SHA retrouvent cet état, soit trois chargements
successifs. Le passage logiciel vers la mire échoue avec commit en attente ;
les rechargements rétablissent la mire interne (mode=0, somme vérifiée,
confirmation visuelle encore en attente). Aucun manque de débit DDR n'est
démontré ; la distribution/libération de ce reset devient la piste ciblée.

La sortie du second DFFCE est routée sur LW. N56r9_route3_scan_reset est
préparé avec une seule contrainte LOCAL_CLOCK ajoutée sur ce signal ;
même netlist, DDR 5.9/300 MHz, SDC et SG4. La Pro Dock utilise aussi LW
pour son propre scanout : ceci ne démontre pas une défaillance générale
des ressources LW. Le résultat du prochain routage et de son essai reste
à établir. Les sources communes et références Pro Dock restent inchangées.

Les 11 groupes de `TESTS/dual_board/20261023_scan_reset_observed/` passent.
Le routage `console_neo_n56r9_route3_scan_reset` est lancé, CST accepté,
placement en cours ; timing et matériel encore en attente.

État Neo courant : N56r9_route2, CPU arrêté dans le parking ROM, mire
interne sélectionnée, sans Linux ; voir
`TESTS/neo_720p_20261012/reload_r1_cold_20261022/r9_route2_reset_reloads/`.
L'ancienne ancre R8 est consommée ; ne pas la réutiliser.

### 24 octobre : résultats route3 / route4 / route5

N56r9_route3 termine sans changement de netlist, mais reste non chargé :
setup −1,656 ns, hold de données +0,124 ns, recovery +0,437 ns,
removal HDMI −0,150 ns sur trois endpoints. Le reset scanout est devenu
local, avec ses deux étages et leurs charges inchangés ; un autre signal
géométrique de 204 CE a cependant été promu sur LW. La qualification
statique et la comparaison globale restent FAIL. Cela n'établit pas
encore la cause physique du reset bloqué observé sur route2.

Deux copies Neo, `console_neo_n56r9_route4_c150` et
`console_neo_n56r9_route5_c155`, sont maintenant lancées en parallèle :
regroupement de 62 cellules de chemins mesurés, CE géométrique local,
trois FF reset HDMI en colonne 150 ou 155. Les candidats conservent
HDL, netlist, SDC, DDR 5.9/300 MHz, broches et SG4 ; seuls les CST et
la métadonnée de placement des snapshots changent. Les 11 groupes locaux
passent dans `TESTS/dual_board/20261024_scan_timing_candidates/`.
Une restriction du bac à sable sur le host ID de licence a interrompu
les premières invocations avant placement ; elles sont archivées et
la reprise autorisée utilise les mêmes entrées figées. Les deux routages
sont désormais terminés : route4 échoue avec setup −4,847 ns et recovery
−1,251 ns ; route5 échoue en setup à −5,840 ns, avec hold +0,124 ns,
recovery +0,310 ns et removal +0,095 ns. Tous leurs audits de synthèse
passent. Deux CE de 256 registres des moteurs pixel/copie sont néanmoins
nouvellement routés sur LW. La comparaison de leurs drivers, charges et
paramètres ne trouve pas de changement logique ; cela ne prouve pas leur
bon fonctionnement physique. Le reset scanout est local et ses deux
étages sont inchangés. Un diagnostic route5 CPU arrêté est préparé pour
observer ce reset puis, s'il est libéré, le framebuffer RGB565 seul.
Le FAIL de timing est conservé ; aucun démarrage Linux ni promotion de
cette variante. Son essai SRAM échoue ensuite avant l'examen CPU : DMI ne
répond pas et l'utilisateur ne voit pas de mire. Le reset scanout n'a donc
pas pu être mesuré sur route5. Le rechargement du SHA N56r8 précédemment
visible rétablit l'accès CPU, le balayage et la somme mire. L’utilisateur confirme ensuite :
« Oui, la mire est revenue ». Voir
`r8_restored_after_route5/` dans le dossier de diagnostic du 22 octobre.
R6 reprend route3 avec seulement trois FF reset HDMI déplacés en C155,
sans les regroupements supplémentaires R4/R5. Les 11 groupes locaux
repassent dans `TESTS/dual_board/20261024_route6_hdmi_only/`.
R6 termine FAIL : setup −2,599 ns (81 endpoints), hold de données +0,124 ns,
recovery +0,337 ns, removal −0,153 ns sur les trois resets OSER10. Il ne
change pas les allocations globales de route3, mais n'est pas chargé.
La carte conserve N56r8 et sa mire confirmée visible.

Le canal 1 HDMI manque 0,153 ns en removal, avec +1,045 ns de marge en
recovery. R7 est préparé avec les trois FF reset HDMI en C140 pour tester
un trajet plus long ; les deux limites temporelles restent obligatoires.
Cette expérience conserve netlist, DDR, broches et SDC. Elle ne corrige
pas par elle-même le setup du blitter/DMA et ne prouve pas la cause du
blocage scanout. Les 11 groupes repassent dans
`TESTS/dual_board/20261024_route7_hdmi_delay/`. R7 est en placement, sans
chargement automatique. Les références Pro Dock restent inchangées.

### Nuit du 24 au 25 octobre : N56r10 chargé et observations GAO

À la demande « alors charge la N56r10 », le bitstream exact de
`console_neo_n56r10_gao_startup` est chargé en SRAM sur la Neo : SHA-256
`7ca33ea0a54a4ba557319489239e330f6fbfca69840982894ca447a705b05f28`.
Le programmateur signale DONE sans drapeau d'erreur ; aucune relecture
complète de la SRAM n'est revendiquée. La caméra montre l'écran noir et la
LED utilisateur allumée. Le TAP AE350 répond, mais la tentative DMI expire.
La carte conserve N56r10, sans Linux, sans écriture SD ou flash. Les ancres
matérielles antérieures N56r8 ne doivent plus être réutilisées.

La qualification reste FAIL : setup −0,849 ns, hold GAO −0,384 ns,
recovery −0,364 ns ; un reset reste sur une ressource globale interdite
par l'audit. Trois lectures GAO ont été obtenues après correction de
problèmes du banc logiciel : socket Unix trop long, conflit zlib/FreeType
et sélection ambiguë du câble. L'identification D2XX et le TAP FPGA
confirment le programmateur Neo exact avant capture.

Les deux dernières lectures rapportent DDR initialisée et POR/HW_RSTN du
CPU libérés, mais HRESETN/EXTS_HRSTN et reset vidéo maintenus bas. Leurs
horloges échantillonnées diffèrent : elles ne sont pas présentées comme
des relectures d'une mémoire initiale immuable. Le hold GAO en échec limite
la portée de ces observations. Les 149 connexions du macro AE350 et les
paramètres/connexions de sa PLL sont identiques à N56r8 ; cela ne prouve
pas l'identité des routes ou du séquencement physique.

N56r14 reprend les entrées figées R10 et ajoute une contrainte BUFG dans
un CST propre au domaine GAO. Le backend officiel, exécuté dans `gw_sh`
licencié, accepte les deux CST et termine avec un code de retour nul.
La comparaison finale établit cependant une **absence d'effet physique** :
`ao_0.bin` est identique octet pour octet à R10 (SHA-256
`d6890a96535160d4ace5d27f2bb2fa8ec8c1ec59580ce5e13a30bb46d73f7534`).
Le FS, le VO et le SDF ne diffèrent que par leur date ; le TR ajoute
seulement les nouveaux chemins et la date. Les marges restent identiques :
setup −0,849 ns, hold −0,384 ns, recovery −0,364 ns, removal +0,196 ns.
Les huit horloges PRIMARY sont conservées ; l'audit du reset global reste
FAIL. R14 n'est pas chargé, la Neo conserve R10. L'acceptation du CST
n'a donc pas démontré une amélioration de l'instrumentation ni une cause
au reset AE350 maintenu actif. La comparaison est archivée dans
`TESTS/neo_720p_20261012/reload_r1_cold_20261022/gao_r14_postroute_review/`.
La campagne commune `TESTS/dual_board/20261024_luma_living_gao/` passe
11 groupes, distincts du timing et des essais matériels.

Preuves, limites et captures :
[rapport GAO](../TESTS/neo_720p_20261012/reload_r1_cold_20261022/GAO_READOUT_20261024.md).
Les références FPGA Pro Dock restent intactes ; le jeu y est testé
séparément avec le noyau candidat décrit ci-dessous.

### Complément diagnostic Neo du 25 octobre

N56r10 reste chargé. Des lectures brutes du TAP AE350, sans cible CPU
OpenOCD ni commande d'arrêt/reset, donnent IDCODE `0x1000563d` et DTMCS
`0x7071` de façon stable à 100/1 000/100 kHz. Une lecture DMI de DMSTATUS,
puis une lecture séparée de DMCONTROL, restent BUSY. L'effacement du seul
statut mémorisé par DMIRESET est constaté, puis BUSY revient au NOP suivant,
deux fois pour chaque registre : une ancienne erreur mémorisée n'explique
donc pas seule l'échec. Les données de ces réponses BUSY ne sont pas des
valeurs de registres. Aucun reset CPU, accès DDR ou rechargement FPGA.

Une quatrième lecture GAO retrouve POR/HW et DDRinit hauts, HRESETN et le
reset vidéo bas. L'ordre d'acquisition du tampon « initial » reste inconnu ;
ce n'est pas une capture temporelle des commandes JTAG. La cause interne
horloge/reset/initialisation du bloc dur reste à établir. Aucun nouveau
routage n'a été lancé dans cette étape. Les 11 groupes locaux passent,
entrées inchangées, dans `TESTS/dual_board/20261025_neo_reset_sequence/`.
Preuves : [diagnostic du transport JTAG](../TESTS/neo_720p_20261012/debug_transport_20261025/README.md).

L'utilisateur retient ensuite une marge de reset de **50 ms**. Le candidat
isolé `console_neo_n56r15_reset50ms` ajoute un séquenceur avant les deux
registres AHB existants de POR/HW, avec choix court/long par UART dans le
même bitstream. DDR 5.9/300 MHz et resets PLL restent inchangés. Les
144 autres modules de la netlist parent sont identiques ; aucun correctif
expérimental n'est reporté dans les sources communes de développement.

La simulation RTL et celle du helper synthétisé avec les primitives Gowin
passent, y compris le délai réel et l'arrêt/reprise des horloges. Les 11
groupes de `TESTS/dual_board/20261025_neo_reset50ms_decl/` passent également.
La première lecture de netlist échoue avant placement sur des déclarations
ajoutées trop tard pour le lecteur Gowin ; l'échec est archivé. Après
correction de format, les netlists et le CST sont acceptés, et le placement
est lancé. Timing et matériel restent à établir. N56r10 reste sur la Neo.
Voir [l'expérience de reset 50 ms](../TESTS/neo_720p_20261012/reset_sequence_20261025/README.md).

**Résultat ultérieur du même essai :** R15 termine le routage (setup
−3,844 ns, hold −0,305 ns, recovery −4,972 ns), puis son SHA exact
`8b005988433a70fdef654f5e2e7f93b3ba484764c1be44bb356bd1418931227b`
est chargé sur la Neo en diagnostic. La mire est visible, photographiée et
confirmée par l'utilisateur. La lecture DMI auparavant BUSY aboutit ; un
essai séparé arrête le CPU à `0x80000004` et lit le GPU avec son compteur
d'images actif et sa somme de mire correcte. R15 reste chargé, CPU arrêté,
sans Linux ni écriture DDR/SD/flash demandée par les essais.

GAO observe POR/HW puis HRESETN libérés, ainsi que les témoins AHB/RTC.
Les deux dernières lignes du tampon présentent une anomalie non expliquée,
consignée avec les violations hold de l'instrument ; elles ne sont pas
interprétées comme un reset physique certain. Le démarrage retrouvé ne
qualifie ni le timing complet ni le framebuffer DDR. L'effet propre du
délai de 50 ms reste à isoler du nouveau routage. Pro Dock inchangée par
ce diagnostic ; le jeu y poursuit ses essais séparément.

Les essais suivants sur **le même R15** vérifient 16 signatures DDR de 2 Kio
et l'image RGB565 complète par accès CPU. Le lecteur vidéo progresse mais
ses sommes sont incorrectes et ses underflows persistent en pleine et
demi-résolution. Un remplissage GPU historique de 32 octets est exact. En
revanche, les commandes V1 arrivent avec le bon en-tête dans la géométrie,
puis la capture pixels reste nulle et le compteur interne signale des rejets.
Le défaut persiste après un reset chaud long, sans rechargement FPGA.
La carte revient à la mire interne, CPU arrêté, sans Linux ni écriture SD/flash.
Ces essais ont écrit en DDR volatile ; ils ne qualifient pas le GPU complet.

Une corrélation entre ce défaut et un CE promu sur LW est consignée, sans
preuve de causalité. À la demande de l'utilisateur, le reroutage envisagé
est suspendu avant préparation : aucun R16 n'est lancé. Le diagnostic
reprend par la documentation des primitives et le transfert des commandes
dans la netlist exacte. Les 11 groupes locaux de
`TESTS/dual_board/20261025_r15_pixel_capture/` passent indépendamment.
Voir le même [rapport R15](../TESTS/neo_720p_20261012/reset_sequence_20261025/README.md)
pour les preuves, le compteur V1 omis du premier contrôle de fence et les
limites des observations. Aucun de ces essais ne modifie la Pro Dock.

À l'autorisation suivante, un **R16 d'observation** est préparé puis lancé :
`console_neo_n56r16_gao_pixels`. Il conserve la netlist R15, CST/SDC, DDR,
PLL et délai de reset ; seul le fichier GAO sélectionné change, avec 113
sondes sur l'horloge GPU. Ce n'est pas le correctif de routage CE suspendu.
Les 11 groupes locaux passent dans `TESTS/dual_board/20261025_r16_observation/`.
Le décodeur est vérifié sur la simulation de la netlist exacte et sur des
défauts injectés dans les traces. Le placement est en cours, audits finaux
et essais carte en attente. R15 reste chargé sur la Neo ; Pro Dock intacte.
L'instrumentation peut changer les routes physiques : aucune cause du
défaut GPU n'est attribuée avant reproduction et observation concordante.

**Résultat final R16, 25 octobre à 21:18 :** le processus termine avec
`PR0009`, quatre connexions non routées dans le design GAO, après 5 h 28 min.
Aucun FS/TR/SDF final n'est disponible ; R16 n'est pas chargé et reste
**ROUTING_FAILED**. La comparaison des 142 685 cellules applicatives du VO,
de leurs paramètres et des entrées R15/R16 confirme l'absence de modification
fonctionnelle dans ce candidat d'observation. Les noms des quatre connexions
ne sont pas fournis dans les rapports publics. R15 reste sur Neo ; l'échec
de routage GAO n'explique pas encore le rejet GPU de R15. Les preuves sont
dans `reset_sequence_20261025/r16_route_failure_01/`, sous le rapport lié
ci-dessus. Aucun nouveau routage n'est lancé à ce constat.

À la demande suivante de poursuivre, **R17 d'observation ciblée** est lancé
à 22:58. Il réduit GAO de 113 à 32 sondes pour suivre l'opcode et les
contrôles de capture. Netlist R15, DDR, PLL, reset 50 ms, CST/SDC et options
PnR sont inchangés ; seuls les signaux observés et l'identifiant GAO changent
par rapport à R16. Le wrapper généré est vérifié. Les 11 groupes locaux
passent dans `TESTS/dual_board/20261025_r17_observation/` ; le décodeur réduit
retrouve les 16 captures de référence et vérifie dix cas, y compris ses
limites de visibilité. Placement en cours, timing et matériel en attente.
R15 reste sur Neo ; aucun accès Pro Dock dans ce diagnostic.

## Développement parallèle du jeu LUMA

`games/luma_adventure/` est un nouveau candidat logiciel destiné aux deux
cartes, avec un frontend PC pour les essais. Ses pilotes GPU et son ABI
restent ceux du projet commun ; le nom Pro Dock de ces interfaces ne
rend pas ce jeu spécifique à cette carte. Ce développement ne remplace
ni le FPGA G22r0 ni le paquet Linux NEBULA R17 protégés.

Les sources du jeu, ses contenus et ses ressources sont encore en cours
de développement, hors des paquets Linux publiés. Leur intégration à
l'inventaire des entrées de production reste à faire avant publication.
Les tests du moteur et du rendu logiciel restent distincts de la suite
locale des deux profils et des essais matériels. Un test sur la Pro Dock
ne qualifie pas la Neo.

L'agent chargé du jeu est seul propriétaire des essais Pro Dock de ce
chantier. Il utilise le Linux R17 existant, des copies de fichiers dans
`/tmp`, un verrou de diagnostic et des transferts contrôlés par CRC. Les
sauvegardes de ces essais sont temporaires ; elles ne constituent pas une
installation persistante sur SD. Les générations d'images et de musique
passent par ComfyUI sur gx10-2, avec YuE2 pour la musique. La disponibilité
d'un fichier audio ne qualifie pas une sortie audio matérielle : aucun
backend sonore Pro Dock ou Neo n'est encore intégré pour ce jeu.

### 24 octobre : vallée 3D et noyau candidat distinct

Le nouveau jeu `games/luma3d/` utilise la géométrie matérielle G3D1 déjà
présente dans G22r0. L'ABI Linux commune s'étend avec les commandes 31–34
et un ioctl de détection/compteurs, sans modifier les structures ABI1
existantes. Les adresses de modèles restent limitées à la fenêtre GPU
utilisateur ; aucune extension à toute la DDR n'est autorisée.

La campagne `TESTS/dual_board/20261024_luma3d_first_valley/` passe ses
11 groupes. Les tests supplémentaires des commandes G3D1 sont dans
`TESTS/luma_g3d1_linux_20261024_r3/`. Les preuves du moteur/rendu du jeu
restent identifiées séparément dans son propre manifeste.

Le paquet expérimental `games/luma3d/build-kernel/prodock_g3d1_20261024_r1/`
part d'un overlay R17 + G3D1 seulement, avec initramfs, DTB et OpenSBI R17
conservés. Il ne reprend pas implicitement les différences Neo du noyau
de travail. Le boot Pro Dock et le raster passent, puis un oracle G3D1
vérifie 294 pixels, les transformations, la profondeur et le culling.
Le premier chargement a été refusé par la dépendance au programmateur
FPGA absent ; ce FAIL est conservé. Le chargeur isolé de reprise vérifie
explicitement le couple CDC/J-Link et le parking M-mode avant toute
écriture DDR. Voir `games/luma3d/tests/hardware/`.

G22r0 n'a pas été rechargé ou modifié ; SD et flash sont intactes. Le Linux
candidat actif n'est pas une promotion de la référence R17. La validation
matérielle du nouveau jeu et celle du profil Neo sont des étapes distinctes.
