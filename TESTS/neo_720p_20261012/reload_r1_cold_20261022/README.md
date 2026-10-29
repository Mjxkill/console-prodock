# Neo N56r1 : rechargement après coupure, puis isolation de l'écran noir

22 octobre 2026, soirée. Carte Neo locale, programmateur Sipeed série
`2025041420`, bus `3:28`, CPU via ESP-Prog `Dual RS232-HS`.
La Pro Dock distante conserve G22r0 / Linux NEBULA R17 ; aucun accès ni
changement de sa configuration pendant ces essais.

Bitstream N56r1 :
`426389b02a4c1c240a28a711546569315e5c4d9478199f12e1e38f46009d3d2d`.
DDR 5.9 / 300 MHz. La qualification statique reste **FAIL** : setup
−0,440 ns, trois chemins ; les essais ne transforment pas ce résultat en PASS.

## Résultats distincts

| Essai | Résultat | Preuve |
|---|---|---|
| Programmation SRAM après coupure demandée par l'utilisateur | DONE, aucun drapeau d'erreur ; pas de readback FPGA | `program_status.json` |
| Chargement Linux avec `--preserve-uart-route` | Prétests mémoire/TARGET, vérification complète du payload compact et lanceur, CRC et boot UART confirmés ; 108,15 s | `linux/result.json`, `linux/openocd.log`, `linux/console.log` |
| Initialisation Linux | GPU 1280×720, SD et deux manettes initialisés ; cela ne prouve pas le rendu | même dossier |
| Première commande UART | `prodockctl geometry` répond correctement | `gpu/geometry.log` |
| Suite GPU Linux | **FAIL au transport de la commande runtime**, pas un résultat du programme runtime : commande reçue altérée, programme non exécuté | `gpu/runtime.log`, `gpu/result.json` |
| Lancement NEBULA | Pas exécuté : absence de prompt, abandon avant envoi | `demo/serial.log` |
| Observation écran sous Linux | Frames progressent, underflows massifs, fetch_frames/checksum/total_cycles nuls ; commit en attente | `display_observation/` |
| Reprise de flux série Ctrl-Q | Le prompt réapparaît ; compatible avec une suspension XOFF, origine exacte non établie | `uart_xon.log` |
| Envoi lent avec vérification de l'écho | **FAIL** : `o` (0x6f) reçu `n` (0x6e), ligne annulée avant Entrée | `quiesce/result.json` |
| Commandes courtes `mount`, puis `sync` | Échos exacts et retour au prompt ; uniquement systèmes de fichiers RAM, aucune SD montée | `mounts/`, `sync/` |
| Framebuffer RGB565 seul, CPU arrêté après nouveau chargement SRAM | **FAIL** : 1 843 200 octets chargés/vérifiés, commit appliqué, 60 frames mais zéro fetch_frame et +43 460 underflows entre deux échantillons | `rgb_only/` |
| Simulation fonctionnelle du scanout et de la file après routage | **PASS limité à la première ligne** : 80 requêtes ordonnées, 80 réponses et ACK de fin de ligne | `routed_scanout/` |
| Retour à la mire HDMI interne N56r1 | Compteur frames actif, somme vidéo stable `0x1ff8f800`, framebuffer désactivé ; utilisateur : **aucun signal HDMI** | `fallback_bars/` |
| UART directement sondée, CPU arrêté | 128 caractères reçus, **6 altérés**, sans erreur LSR ; défaut indépendant du terminal Linux | `uart_direct/` |
| Reset de la carte par l'utilisateur | L'analyseur en flash affiche une image ; les anciennes ancres N56r1/Linux sont invalidées | `user_reset/` |
| Mire minimale DCE, placement automatique PG0 | **Image confirmée**, toutes marges STA positives | `hdmi_dce_trial/` |
| Même netlist, DCE forcé SG0 | **Aucun signal confirmé**, malgré toutes marges STA positives | `hdmi_sg0_trial/` |
| Rechargement exact de la première mire PG0 | **Retour de l'image confirmé** | `hdmi_auto_return_trial/` |
| Même netlist, DCE forcé PG0 | **Image confirmée**, même procédé de reroutage que SG0 | `hdmi_pg0_trial/` |

## Interprétation et limites

Deux observations doivent rester séparées : l'absence de signal HDMI,
reproduite ci-dessous sans DDR, et le blocage de lecture du framebuffer.
Ce blocage ne nécessite ni Linux, ni le jeu, ni les couches ou sprites :
le RGB565 direct le reproduit après une reconfiguration complète.
La mémoire de cette mire a été vérifiée par accès CPU/JTAG avant activation.
Cela ne prouve pas que le chemin de lecture GPU ou l'arbitrage DDR fonctionne.
Les compteurs nuls sont mis à jour à la fin d'une ligne/image : ils ne prouvent
pas qu'aucune requête DDR n'a été émise. L'instrumentation actuelle ne montre
pas directement l'état interne où la première ligne reste bloquée.

La simulation conserve les cellules et paramètres de la netlist post-PnR
du scanout et de sa file, ainsi que leurs dépendances combinatoires. Elle
emploie les primitives officielles Gowin et trois horloges distinctes.
Les compteurs raster sont placés à la frontière vblank pour démarrer la
première ligne rapidement. Le modèle accepte les requêtes et retourne des
bursts après 16 cycles ; **l'arbitre DDR, le PHY, les délais physiques et la
métastabilité sont hors périmètre**. Aucun SDF n'a été appliqué. Ce PASS ne
résout donc pas l'écart avec la carte.

Le reset `u_gpu/mrst[1]` utilise LW dans R1, mais également dans la référence
Pro Dock. Ce fait seul ne démontre pas une faute. Le candidat Neo isolé
N56r6 ne change qu'une contrainte `LOCAL_CLOCK` sur ce signal pour tester
cette hypothèse ; son résultat de routage et son essai carte restent en attente.
N57 est une autre expérience, avec les nouvelles IP USB et contraintes de
contrôles GPU ; les conclusions doivent rester séparées.

## Isolation HDMI : PG0 / SG0, puis retour PG0

Les mires minimales ne contiennent ni CPU, ni DDR, ni USB, ni SD. Leur PLL,
encodeur TMDS et sérialiseur sont copiés des sources gelées N56r1, identiques
octet pour octet aux modules de l'analyseur L31r8. Raster 1650×750, image
1280×720, synchronisations positives, huit bandes et cadre blanc.

La première mire est synthétisée et routée sans placement imposé au DCE :
Gowin le place sur **PG[0]**. Les variantes suivantes réutilisent exactement
sa netlist de synthèse et ajoutent uniquement `INS_LOC "u_video_fast" SG[0];`
ou `INS_LOC "u_video_fast" PG[0];`. Les deux passent par le même flux `run pnr`.
Le DCE conserve `.CE(1'b1)` ; PLL, fréquences, broches et SDC restent identiques.

| Variante | SHA-256 bitstream | Setup / hold / recovery / removal (ns) | Observation |
|---|---|---|---|
| Auto PG0 | `2043ca8b654108f1dd5abbe93559c564f73ad7eea3cdf47957d8a5c9252070d5` | +5,335 / +0,247 / +0,726 / +0,158 | Visible, puis visible à nouveau après SG0 |
| SG0 explicite | `bf5070142d249704967d23d463a96dd15ff8ff5ce020d950dab62244c946cbcd` | +5,335 / +0,247 / +0,463 / +0,343 | Aucun signal |
| PG0 explicite | `fb7027560c5f4e9551e9d2697cf1c4e6890b98210ddc4d7c07fb10470c31d386` | +5,335 / +0,247 / +0,726 / +0,158 | Visible |
| SG4 explicite | `29b8ca01df0786a5de37554160a7f2f61f035176d64f3359eb53be12ca2cba90` | +5,335 / +0,247 / +0,463 / +0,343 | Visible |

Les rapports indiquent `BANK3_HCLK1` pour les trois mires. L'aller-retour et
le contrôle PG0 explicite isolent un effet de placement/routage associé à
SG0 dans ce design. Ils ne prouvent pas un défaut matériel général de SG0,
ni la cause électrique précise (horloge, phase ou sérialisation). La
documentation locale SUG1018 v1.7E, tableau 2-1, autorise bien PG et SG pour
les DCE du GW5AST-138 : aucune interdiction générale n'est déduite ici.

N56r1, N56r6 et N57 imposent tous SG0 à ce buffer. **N56r7** est une copie
gelée de N56r1 qui remplace cette unique contrainte par PG0. La métadonnée
`timing_closure.json` décrit le nouveau site ; les huit exigences de clocks
PRIMARY, les placements de reset, la netlist, la DDR 5.9/300 MHz, les IP USB
et les SDC restent identiques. Manifeste préparé :
`db370e7750e785abed97128a62d88403f90b91c972a28aaea1746b5f76c42e77`.
Le routage est lancé ; aucune qualification ni validation carte annoncée.

### Suite : SG4 fonctionne également sur la carte

Les variantes SG8 et SG12 de la même mire échouent en recovery à −1,181 ns
et ne sont pas chargées. SG4 donne les mêmes marges publiées que SG0 et
l'utilisateur confirme cette fois une image visible (`hdmi_sg4_trial/`).
L'échec n'est donc pas général à tous les sites SG. Le mécanisme électrique
exact expliquant l'écart SG0/SG4 reste indéterminé.

**N56r8** reprend directement la netlist N56r1 avec seulement
`INS_LOC "u_video_fast" SG[0];` remplacé par `SG[4]`, et la métadonnée du site
correspondante. Aucune modification de RTL, fréquence, DDR, reset ou SDC.
Les huit exigences PRIMARY restent obligatoires. Manifeste préparé :
`157b1a60f3f6520a0ed894491f7a6624df260e2fc9c96f807e9f8aedc8d1d5fa`.
Routage lancé ; `finish_hdmi_sg4_route.py` qualifiera et auditera le résultat
sans accès matériel. N56r7 poursuit son routage indépendant, sans relance.

Le modèle `clock_pressure_sg4/` conserve bien ses huit horloges sur PRIMARY
(`all_eight_primary=true`). Il réutilise la netlist de l'ancien modèle SG8
avec uniquement la contrainte du DCE remplacée par SG4. Ce modèle utilise
des compteurs et des fréquences bus/GPU de substitution : il vérifie
l'allocation, pas les contrôleurs USB/DDR ni le timing de la console.

Le premier contrôle après retour à la mire N56r1 avait échoué en évaluant
les registres CPU. Un second contrôle avec `halt` explicite a confirmé le
parking ; les deux journaux sont conservés. Ces ancres ont ensuite été
invalidées par le reset utilisateur et les chargements des mires minimales.

## Extension de simulation scanout + arbitre

Le banc `../n55_gpu_diagnosis_20261021/routed_scanout_arb_r3/` conserve
20 714 primitives post-routage officielles, incluant cette fois l'arbitre.
Il passe 80 commandes DDR natives aux adresses exactes, 80 retours et l'ACK
de première ligne avec backpressure de 3 cycles sur 11 et réponse après
16 cycles. CPU et moteurs de dessin restent inactifs. Les retours sont
constants `ffff`, sans SDF ni PHY, et ce n'est pas un test d'image complète.
Le blocage matériel de première ligne n'est pas reproduit dans ce scénario.

N57 finit avec setup −0,332 ns et recovery −0,986 ns : **FAIL, non chargé**.
N56r6 termine **FAIL** : setup −1,211 ns (31 chemins), hold +0,124 ns,
recovery +0,511 ns, removal +0,049 ns. Le reset scanout ciblé sort de LW,
mais le reset GPU 4 est promu en LW : audit des resets global FAIL.
Non chargé. Son replay fonctionnel de première ligne passe aussi.

L'ancien essai à huit horloges (`hdmi_clock_pressure_20261017`) montrait
que PG0 pouvait déplacer `clk_d` sur LW. Les huit exigences PRIMARY restent
dans N56r7 : le contrôle automatique ne doit pas masquer cette éventualité.
`finish_hdmi_route.py` attend uniquement ce routage puis exécute qualification
et audit structurel, sans accès carte. Le test matériel préparé
`test_rerouted_rgb.py` n'a pas encore été exécuté ; il exige les preuves et
consomme une seule fois l'ancre de la mire sans CPU.

Une alternative minimale DHCE + CLKDIV /5 (`hdmi_bars_dhce_div5`) a aussi
été compilée pour explorer une distribution sans DCE PG/SG. Elle conserve
74,375 MHz pixel et 371,875 MHz série, mais échoue en recovery à −3,470 ns
(setup +5,335, hold +0,247, removal +0,422). **Non chargée** ; aucune
amélioration matérielle n'est annoncée pour cette expérience.

## Résultats du 23 octobre : console complète N56r8

Les deux routages sont terminés. N56r7 PG0 reste **FAIL, non chargé** :
setup +0,008 ns, hold +0,124 ns, recovery +0,814 ns, removal **−0,135 ns**.
`clk_d` passe sur LW ; l'audit des huit clocks PRIMARY échoue également.
Le succès HDMI de la mire minimale PG0 ne permet donc pas de retenir ce build.

N56r8 SG4 conserve les huit PRIMARY et tous les audits structurels passent.
Setup **−0,144 ns**, hold +0,124 ns, recovery +0,511 ns, removal +0,049 ns.
Les deux violations setup (−0,144 / −0,048 ns) vont de `u_pixels/packet`
vers `u_gpu_debug/observe_words_s1`. Le statut reste **FAIL** ; le mode
diagnostic accepte ce SHA exact sans masquer le résultat de qualification.
Bitstream : `51841fe4ae76a7eb635a0398534f35b6c7030fa8b768d88b892fede3b1601c35`.

`r8_rgb_only/result.json` reproduit le blocage du framebuffer :
1 843 200 octets chargés puis vérifiés en DDR à `0x01700000`, commit appliqué,
61 frames raster entre deux échantillons, **zéro fetch_frame**, **+43 485
underflows**. Aucun Linux ni moteur de dessin actif, CPU arrêté dans le ROM.
Le changement HDMI ne résout pas le défaut de lecture vidéo.

Le même bitstream est ensuite rechargé pour revenir à sa mire interne.
`r8_fallback_bars/` confirme 60 frames de progression, aucune sous-alimentation
et la somme interne `0x1ff8f800`. L'utilisateur confirme **« Les bandes sont
visibles »**. La sortie HDMI est donc observée fonctionnelle dans cette
console complète avec SG4, et pas seulement dans le design minimal.
Ce résultat ne qualifie ni le framebuffer, ni le GPU, ni Linux sur N56r8.

## Instrumentation préparée pour localiser la lecture bloquée

`scan_observer_candidate/` contient une copie N56r8 avec trois fichiers
modifiés (top Neo, sorties de diagnostic du scanout et lecteur RGB) et un
observateur passif ajouté. Aucun fichier commun actif ni fichier de la
référence Pro Dock n'est modifié. L'audit des 21 fichiers du profil DDR passe,
avec IP 5.9 / 300 MHz, CST SG4 et SDC identiques à N56r8.

Le diagnostic GPU `0xe9005000` reste présent. Le nouveau slave `0xe9006000`
réutilise le mécanisme de snapshot cohérent existant : écrire 1 à `+0x04`,
attendre `status == 6`, puis lire les huit mots à `+0x20..+0x3c`.
Tous sont capturés sur le même front de `gpu_clk`, retenus jusqu'à la
prochaine demande. Les anciens champs auxiliaires `+0x10/+0x14` et les
observations brutes de cette seconde instance ne sont pas interprétables
comme statistiques scanout.

| Mot du snapshot | Contenu |
|---|---|
| 0 | Ligne `[31:22]`, flags `[21:0]` : fetch_valid, returned_valid, sprites, layers, halfres, RGB, prefetch, cache_busy, done_pending, reader_done, reader_start, rgb_done, rgb_start, rgb_phase, dispatch_line, line_pending, acknowledge, réservé, request_sync[1:0], mrst[1:0] |
| 1 | Adresse octet de la ligne capturée |
| 2 | État RGB `[23:21]`, issued `[20:14]`, position `[13:7]`, last `[6:0]` |
| 3 | Requêtes acceptées par la file vidéo |
| 4 | Requêtes acceptées à l'entrée de l'arbitre |
| 5 | Retours DDR portant le tag scanout |
| 6 | Dernière adresse en mots acceptée à l'entrée de l'arbitre |
| 7 | Signature `SCN` `[31:8]`, valid/ready file puis arbitre, retour valide et reset libéré `[5:0]` |

**L'acceptation à l'entrée de l'arbitre n'est pas une acceptation native
par l'IP DDR** : l'arbitre possède encore deux places internes. Ces compteurs
doivent séparer une demande jamais partie, une file bloquée, des retours
manquants et une terminaison de ligne perdue. Ils ne mesurent pas encore
directement la commande native à l'intérieur de l'arbitre.

`scan_observer_sim/result.json` : **PASS RTL**, 1280×720, RGB565 et palette,
comparaison des pixels/sommes, changement de page en vblank, file Neo,
arbitrage CPU concurrent, DDR avec backpressure puis arrêt prolongé.
En fonctionnement : 172 880 / 172 880 / 172 880 (file/arbitre/retours).
Pendant l'arrêt injecté : 403 284 / 403 282 / 403 280, ligne en attente,
lecteur RGB en PIPE ; reprise et stabilité du snapshot vérifiées.
2 607 448 lectures CPU terminées dans le modèle. Ni PHY, ni SDF : le défaut
physique observé sur la carte n'est pas encore reproduit ni expliqué.

Scripts : `prepare_scan_observer.py`, `test_scan_observer.py`,
`build_scan_observer.py`. Le constructeur exige le test réussi, vérifie les
empreintes, crée seulement `console_neo_n56r9_scan_observer`, puis lance la
qualification automatique après routage. Aucun accès carte automatique.
L'ajout de charges d'observation et le nouveau placement peuvent modifier
le symptôme : vérifier sa reproduction avant toute conclusion causale.

La campagne `TESTS/dual_board/20261023_scan_observer/result.json` passe les
**11 groupes** des profils actifs. Elle ne remplace pas la simulation propre
à la copie instrumentée ni les futurs essais matériels de N56r9.
La synthèse N56r9 a terminé, mais le placement initial a été refusé :
`u_scan_queue/push_s2` et `u_gpu_debug/mem_up[1]` n'existent plus sous ces
noms dans la nouvelle netlist. Cet échec est conservé dans le build original.

`route_scan_observer.py` prépare `console_neo_n56r9_route1` en réutilisant
exactement cette synthèse (SHA `0b5ea22b83faf2bae943f399bdb734dc1e66c8507310dc25e054290e24ad6157`).
Deux substitutions de cibles dans le CST, sans suppression de contrainte :

- `u_scan_queue/push_s2` devient `u_scan_queue/scan_debug_live_228_s`,
  même LUT2 `INIT=4'h4`, mêmes entrées `full` et `up[1]`, donc même READY
  `!full && up[1]` ; même rectangle de placement R[78:86]C[136:150].
- `u_gpu_debug/mem_up[1]` devient `scan_debug_live[224]`, issu de
  `u_scan_observe/up_1_s0`. La synthèse a mutualisé les synchroniseurs
  équivalents des observateurs : deux DFFCE sur `gpu_clk`, initialisés à 0,
  clear asynchrone provenant de `!vid_hrstn`. La contrainte LOCAL_CLOCK est
  conservée sur ce signal. Le fanout et la distribution physique changent.

Le script contrôle les cellules, INIT, connexions de reset et quatre charges
de l'ancien observateur, ainsi que les deux autres pilotes de CE maintenus
locaux. Cette preuve ciblée ne constitue pas une équivalence de la netlist
entière. Aucun RTL, SDC, fichier DDR, fréquence ou placement HDMI ne change
par rapport à N56r9. Résultats dans `constraint_mapping.json` et `route.json`.
La nouvelle campagne `TESTS/dual_board/20261023_scan_route1/result.json`
passe les **11 groupes**. Gowin accepte le CST corrigé et le placement est
démarré. Timing et essai carte restent en attente ; aucun accès matériel.

Lors du suivi intermédiaire, le placement était terminé et le routage avait
atteint sa phase 0 (60 % affiché, sans signification de temps restant).
Le résultat terminé est consigné ci-dessous.
`audit_scan_observer.py --wait` attend la qualification, puis vérifie les
127 DFF de l'observateur et 586 DFF du slave de capture, leurs fonctions,
horloges, resets, INIT et signaux de contrôle. Il conserve tout échec et
n'effectue aucun accès carte. Les nouveaux contrôles de l'observateur et
les CE du scanout ne doivent pas migrer silencieusement sur LW.

`probe_scan_observer.py` est préparé, **pas exécuté sur carte**. Il exige le
SHA exact, les qualifications et un audit d'observateur récent. Il vérifie
le programmateur Neo et le parking CPU avant le chargement SRAM, sous verrou,
puis vérifie la même image DDR que R8 et lit les snapshots avant/après commit.
Sa seule dérogation explicite possible reste le setup, avec statut FAIL
conservé ; hold, recovery, removal et audits restent obligatoires.
Le décodage des compteurs/états a été contrôlé sur le blocage injecté en
simulation (RGB PIPE, issued=4, position=0, last=79, ligne en attente).
Ce test consommera l'ancre R8 une seule fois et laissera le CPU arrêté.

## N56r9_route1 terminé : échec de timing, non chargé

Le routage termine le 23 octobre à 10:37:57. Bitstream SHA-256 :
`03e50cd91886dd50e782d8c5ab53e2a0dd6ca00583cb13ede74c9ad0d3937bff`.
Setup **−4,103 ns**, **194 endpoints en violation**, hold +0,124 ns,
recovery +0,317 ns, removal +0,314 ns. Les huit clocks PRIMARY sont
conservées ; les contrôles explicitement locaux restent locaux. Les audits
structurels standards passent, mais la qualification reste **FAIL**.
Ce build n'a pas été chargé sur carte.

`scan_observer_audit.json` conserve son échec strict : 374 différences
de reset sur 713 registres contrôlés. `prove_observer_reset_alias.py`
produit une preuve distincte dans `scan_observer_reset_alias_proof.json` :
les 2 CLEAR et 372 RESET utilisent une copie d'inverseur du même signal
`!vid_hrstn`. Primitive, D, CLK, CE, Q et INIT restent identiques.
Cette preuve ne dispense pas de STA ni de vérification physique du reset.
Le test matériel préparé refuse encore l'audit strict FAIL ; il ne faut
pas l'exécuter sur route1 en contournant cette garde.

Le pire chemin mesuré va de `u_accel/u_blitter/wp_0_s0` à `wp_7_s0`.
La LUT `u_accel/gpu_debug_state_102_s0` est contrainte dans
R[45:65]C[45:65], tandis que la file de commandes est placée vers
R7–R9, C156–C170. Les deux nets autour de cette LUT coûtent 5,605 et
6,469 ns, soit **12,074 ns** ; l'ensemble des nets du chemin coûte
14,191 ns. D'autres familles de chemins ont également un setup négatif.
Corriger cette seule région ne garantit donc pas la fermeture du timing.
Ce constat concerne le build instrumenté, pas une preuve de la cause du
blocage de lecture observé sur N56r8.

## N56r9_route2 : placement préparé par l'outil maison, routage lancé

`n56r9_route2_prepared/timing_analysis.json` lie l'analyse au rapport Gowin
exact. `optimizer.cst` / `optimizer.json` contiennent les 28 contraintes
régionales proposées par `optimizer/placement.py` sur les 20 premiers
chemins setup. L'outil ne remplace pas une contrainte existante : le
constructeur `route_scan_observer_placement.py` déplace explicitement
l'ancre problématique, en plus des 28 ajouts, vers R[1:25]C[140:175].
Le détail final est dans `review.json` puis le `constraints.diff` du build.

Le constructeur vérifie l'existence et le type des 29 cellules dans la
synthèse, leurs INIT effectifs, l'identité de la netlist, du SDC et du
profil DDR. Les DFFRE sans INIT explicite sont comparées au défaut 0
documenté par la bibliothèque de simulation du compilateur installé.
Le premier contrôle refusait ces INIT implicites ; sa correction interprète
ce défaut vérifié, sans modifier les registres ni la netlist. Cette revue
de placement n'est pas une équivalence logique de l'ensemble du design.

Seul le CST du snapshot change : **aucune modification RTL, DDR 5.9/300 MHz,
SDC, reset, broche ou allocation des horloges**. Même netlist SHA
`0b5ea22b83faf2bae943f399bdb734dc1e66c8507310dc25e054290e24ad6157`.
La simulation de l'observateur reste liée à ces sources ; une nouvelle
campagne locale `TESTS/dual_board/20261023_scan_route2/result.json` passe
les **11 groupes**, SHA
`366fbaef3fa99ba5cd06426ef3d9628fad78f56bedc6b54d18479e59c8970d90`.

Le routage `tang/impl/console_neo_n56r9_route2` est lancé avec qualification
automatique setup/hold/recovery/removal et contrôle des clocks en fin de
build. `audit_scan_observer_route2.py --wait` attend ce résultat puis
applique l'audit strict existant au nouveau build. Aucune dérogation
automatique pour un changement de reset ; aucun accès carte automatique.
Timing, mapping final et essai matériel de route2 restent en attente.

### Suivi du routage et préparation du test matériel

Le placement de route2 est terminé et la phase 0 de routage a passé le
jalon 60 % de Gowin. Aucun rapport de timing final n'est encore produit.
Ce pourcentage n'est pas une estimation du temps restant. Le premier
routage instrumenté avait pris environ 109 minutes ; cela ne prédit pas
la durée du deuxième.

`probe_scan_observer.py` cible désormais **route2 uniquement** et n'a
toujours pas été exécuté sur carte. Le test conserve les gardes de SHA,
qualification, audit strict, identité Neo, verrou et parking CPU. La
capture lit deux fois les huit mots, puis revérifie status et séquence ;
un changement provoque un échec. Les mots bruts, noms d'états RGB,
handshakes et différences de compteurs modulo 2^32 seront enregistrés.
Le compteur arbitre reste un compteur d'entrée de file, pas de commandes
natives DDR.

`test_scan_probe.py` / `scan_probe_checks/result.json` : **11 cas PASS,
sans matériel**. Le décodeur retrouve sur le journal de simulation réel
la ligne 1, RGB PIPE, issued=4, position=0, last=79, deux demandes en
file et deux autres acceptées par l'arbitre sans retour. Le test vérifie
aussi le wrap des compteurs et les bits de handshake. Des lectures
OpenOCD simulées en Tcl confirment le succès d'une capture stable et le
refus d'une capture modifiée, d'une séquence périmée, d'un status modifié
et d'une mauvaise signature/identité. Ces contrôles ne valident ni le
JTAG physique, ni le nouveau routage, ni le framebuffer sur carte.

## N56r9_route2 terminé et essai demandé malgré le timing

Route2 termine le 23 octobre à 22:55:11, après environ 40 minutes.
SHA : `150bd72724ef7ec79c511afe2cc1c01f5976113ec00c39e8fc15e1f272731a01`.
Setup **−1,848 ns**, 172 endpoints en violation, hold +0,124 ns,
recovery **−1,418 ns**, removal +0,179 ns ; statut **FAIL** conservé.
Tous les audits structurels standards passent. Le reset asynchrone de
l'observateur présente la même duplication d'inverseur qu'en route1 :
`prove_route2_observer_reset_alias.py` établit son équivalence logique
dans un rapport distinct, sans effacer l'échec de l'audit strict.
Le recovery négatif le plus sévère va de `u_soc/vid_hrstn_r_s0` vers
`u_gpu/prst_1_s0`; le domaine mémoire a aussi une violation de recovery.

À la demande explicite **« teste le quand même »**, le test est autorisé
uniquement pour ce SHA, CPU arrêté, sans Linux. L'option dédiée
`--allow-route2-recovery-diagnostic` limite l'exception aux quatre slacks
exacts de route2. Les vérifications hold, removal, pulse, sources, DDR,
mapping et identité de carte restent exigées. Un contrôle confirme que
l'appel sans cette option refuse encore le recovery négatif.

`r9_route2_rgb_observer/result.json` : **essai terminé, framebuffer FAIL**.
Chargement SRAM sur le programmateur Neo série 2025041420, bus 3:28,
DONE `0x00026220`, sans erreur de programmation signalée ; pas de preuve
de relecture SRAM. Les **1 843 200 octets du framebuffer sont écrits puis
vérifiés en DDR**. Le commit initial est appliqué, le raster avance de
62 images, mais aucune image mémoire n'aboutit et les underflows augmentent
de 44 304 sur l'intervalle mesuré.

Les captures DISABLED, RGB0 et RGB1 sont toutes cohérentes et identiques :

- `mrst[0]=1`, **`mrst[1]=0`** ; lecteur RGB en IDLE, issued=0, position=0.
- Aucune requête acceptée par la file ni par l'arbitre, aucun retour vidéo.
- Les deux READY sont actifs, `fetch_valid=0`, le reset de l'observateur
  lui-même est libéré.

Ce résultat oriente le diagnostic vers la libération/distribution du reset
du lecteur vidéo, avant toute demande DDR. Il ne démontre pas un manque de
débit DDR et ne prouve pas encore la cause physique du reset bloqué.
Le fichier de rendu relu correctement ne qualifie pas toute la mémoire ni
tous ses usages concurrents.

`followup_scan_observer.py` ajoute cinq captures identiques, puis tente de
revenir à la mire par un commit logiciel. **Cette transition échoue** :
mode shadow=0, commit busy=1, framebuffer encore actif ; erreur conservée
dans `r9_route2_followup/observe.log` et `result.json`.

`repeat_route2_reset.py` consomme ensuite cet état une seule fois et
recharge deux fois le même SHA, sans payload DDR. Les deux rechargements
retrouvent `mrst=01` dès le démarrage et après une seconde. La mire interne
est sélectionnée, mode=0, commit=0, somme `0x1ff8f800`. Avec le premier
chargement, cela fait **trois chargements successifs avec le même état de
reset observé**. Résultats dans `r9_route2_reset_reloads/`.

### Prochain essai : routage local du reset observé

La netlist identifie exactement deux DFFCE, CE=1, INIT=0, même `gpu_clk`,
même CLEAR issu de `!vid_hrstn`. La première reçoit D=1 ; la seconde reçoit
le Q de la première. La sortie de la seconde, `scan_debug_live_178[1]`,
alimente le reset du lecteur et est distribuée sur **LW**. Son fanout
direct comprend 21 charges, aucune entrée d'horloge.

`route_observed_scan_reset.py` prépare N56r9_route3_scan_reset à partir
de la netlist exacte de route2. Seul ajout au CST :
`CLOCK_LOC "scan_debug_live_178[1]" LOCAL_CLOCK;`.
Le constructeur vérifie les deux DFF, leurs INIT/connexions, l'alias du
signal, le profil DDR et les observations matérielles. Aucun RTL, SDC,
réglage de fréquence ou placement HDMI ne change. Un reroutage complet
reste nécessaire, et peut modifier d'autres trajets physiques.
**L'hypothèse LW reste à tester** : la Pro Dock fonctionnelle utilise elle
aussi une ressource LW pour son reset de scanout, et le build observé ici
reste hors timing. Aucun erratum général du FPGA n'est établi.

La campagne `TESTS/dual_board/20261023_scan_reset_observed/result.json`
passe les **11 groupes**, SHA
`022856db4e953a8cef8cd46f69b820d3db77ed1732ccb6544bcda22ec05162b8`.
Le premier lancement a été arrêté par la comparaison du manifeste : les
tuples des charges devenaient des listes en JSON. Le contrôle séparé
`n56r9_route3_prepared/launch_guard_serialization.json` confirme que les
entrées étaient identiques après normalisation JSON. Le constructeur
produit désormais directement des listes ; la revue a été refaite.
Ni HDL, ni contrainte expérimentale modifiés par cette correction d'outil.

**N56r9_route3_scan_reset est maintenant lancé** : Gowin accepte le CST
et commence le placement. Qualification statique et audit strict de
l'observateur sont automatiques en fin de build. Aucun essai matériel de
route3 n'a encore eu lieu ; la Neo conserve route2 en mire interne.

Deux outils préparent la revue du résultat sans modifier ce routage :
`audit_route3_scan_reset.py` compare les deux étages, leurs charges, leurs
paramètres et toutes les allocations globales avec route2 ; toute différence
supplémentaire reste un échec à examiner. `probe_route3_scan_reset.py`
prépare un essai SRAM depuis l'ancre des deux rechargements route2. Il
vérifie d'abord la libération du reset et ne charge le framebuffer que si
les deux étages sont observés à 1. Il ne contient aucune exception de
recovery, hold ou removal ; aucun de ces outils n'a encore validé route3
ni accédé à la carte. Leur syntaxe Python est vérifiée.
`route3_trial_rejection_checks_v2.json` vérifie en outre, sans matériel,
le rejet d'un mauvais SHA et du recovery négatif connu de route2.

`follow_route3_review.py` est lancé pendant le routage existant. Il attend
la fin des contrôles automatiques, puis exécute la comparaison des resets
et produit un tableau Workbench route1/route2/route3 avec l'échec matériel
route2 associé par SHA. Il n'arrête ni ne relance de compilation et
n'accède jamais à une carte. Ses résultats seront dans `route3_followup/` ;
un résultat temporel ou structurel en échec restera affiché comme tel.

La campagne locale `TESTS/dual_board/20261023_scan_route3_review/` passe
les **11 groupes**, avec entrées inchangées pendant les tests. Elle ne
remplace ni la revue des nouveaux outils, ni les résultats de routage,
ni un essai matériel de route3.

### 24 octobre : route3 terminé, deux placements suivants lancés

Route3 termine à 00:30:21 après environ 67 minutes. Bitstream SHA
`42c4edc4a079c1ed3f9759a860ccbf30bb8d4ecfa041e2699870fcc8072e2f4a`.
La qualification reste **FAIL, non chargé** : setup −1,656 ns avec
148 endpoints, hold de données +0,124 ns, recovery +0,437 ns et removal
−0,150 ns. Les trois endpoints comptés dans la rubrique hold globale
du rapport correspondent ici aux trois violations removal des resets
OSER10 HDMI, et non à trois violations hold de données.

La comparaison confirme les deux DFFCE, leurs INIT et leurs charges
inchangés ; le second étage est maintenant local. Elle refuse cependant
une autre promotion automatique : `u_accel/u_v1/n57378_3` passe sur LW.
Ce signal de capture géométrique a 204 entrées CE : 198 scalaires et
six entrées de CE vectoriels de DSP. Aucun de ces constats statiques
ne prouve encore la libération du scanout sur carte. Le rapport strict
de l'observateur conserve ses 374 alias de reset et signale également
les violations HDMI. Tous les échecs restent archivés dans le build.
Le suivi automatique a terminé ; son tableau de comparaison est
`route3_followup/workbench/index.html`.

`route_scan_timing_candidates.py` prépare deux candidats depuis cette
netlist exacte. Les 61 placements régionaux proposés par Workbench
rapprochent les chemins setup mesurés ; une LUT de l'arbitre vidéo
(`u_gpu_arb/n50_s2`) est rapprochée de la file et de l'observateur.
Le nouveau CE géométrique reçoit une contrainte LOCAL_CLOCK. Les trois
FF de sortie reset HDMI sont déplacés vers C150 dans
`console_neo_n56r9_route4_c150`, et vers C155 dans
`console_neo_n56r9_route5_c155`. Ce déplacement teste les marges min/max ;
il ne garantit pas leur signe avant un routage complet. Les candidats
diffèrent entre eux uniquement par ces trois placements et la métadonnée
de colonne correspondante.

Les HDL, la netlist, le SDC, DDR 5.9/300 MHz, les broches et SG4 restent
identiques. Seuls le CST et `timing_closure.json` des copies figées Neo
changent. Le constructeur vérifie les cibles dans la synthèse et la
netlist routée, le profil DDR, les empreintes et les écarts exacts.
La première vérification a détecté les six CE de DSP sous forme vectorielle ;
elle contrôle désormais explicitement les 198+2+4 pins observés.

Les 11 groupes de `TESTS/dual_board/20261024_scan_timing_candidates/`
passent, SHA du résultat
`fd312117037d3e78395393ca01841628ff50bf4fe64753f1b741411af09bff8a`.
Les deux premières invocations Gowin ont été refusées avant placement :
le bac à sable bloquait AF_NETLINK utilisé par la vérification du host ID
de licence. Journaux conservés sous `license_sandbox_*`. La reprise
autorisée hors bac à sable, via `retry_scan_timing_license.py`, vérifie
les mêmes sources et le même Tcl avant de relancer uniquement ces dossiers.
**Les deux Gowin sont maintenant terminés.** Les contrôles temporels et structurels sont exécutés,
y compris la détection de nouvelles promotions CE du GPU. Aucun
chargement matériel n'est automatique.

## Résultats route4 / route5 — 24 octobre

Les deux routages sont terminés, sans être qualifiés :

| Build | Setup | Hold données | Recovery | Removal | Endpoints setup |
|---|---:|---:|---:|---:|---:|
| route4 C150 | −4,847 ns | +0,124 ns | −1,251 ns | +0,100 ns | 602 |
| route5 C155 | −5,840 ns | +0,124 ns | +0,310 ns | +0,095 ns | 154 |

Tous les audits de synthèse de ces deux variantes passent. L'observateur
strict conserve son FAIL pour 374 alias de reset ; pour route5, la preuve
séparée vérifie de nouveau la copie de l'inverseur `!vid_hrstn`, sans
changement des autres pins ni INIT. Deux commandes de 256 CE des moteurs
pixel/copie sont nouvellement promues sur LW. Leur fonction, leurs charges
et leurs paramètres restent identiques à route2 ; aucun pin horloge n'est
alimenté. La distribution physique n'est pas pour autant validée.

Le pire chemin route5 est un retour du blitter vers `busy_sync_0`, avec un
détour de 6,670 ns. Les autres échecs incluent les calculs de tuiles, le
blitter et l'arbitrage. Ce regroupement de placement ne clôt donc pas le
timing. Les FF `u_gpu/mrst_{0,1}` ont une recovery publiée de +2,292 ns.
L'absence de chemin observateur en échec dans le rapport n'est pas une
preuve de couverture STA exhaustive.

`review_route5_reset_trial.py` vérifie l'identité de la netlist et des
sources, les sept différences de distribution globales/locales (dont un
contrôle inchangé utilisé comme témoin), toutes leurs charges, et le SHA
exact route5. `probe_route5_scan_reset.py` prépare un essai CPU arrêté,
sans Linux, SD ni flash : lecture du reset avant toute écriture d'image,
puis RGB565 seulement si les deux étages sont libérés. Ses contrôles
rejettent un autre SHA et tout hold/recovery/removal négatif. Le FAIL
setup demeure et cet essai ne qualifie pas le GPU complet.

## Essai route5 et restauration R8 — 24 octobre

`r9_route5_rgb_trial/` : le garde préalable confirme route2 dans le parking
et son snapshot `mrst=01`. Le chargement SRAM route5 termine avec DONE,
sans erreur de programmation signalée (aucun readback SRAM). Ensuite le
TAP AE350 est identifié, mais les transactions DMI ne terminent pas ;
OpenOCD expire après 30 s avant `CPU_HALTED`. Il n'y a donc **aucune mesure
du reset scanout sur route5**, ni écriture du framebuffer. L'utilisateur
signale l'absence de mire. Cette observation ne permet pas d'accuser la
DDR ni de conclure que le reset local corrige ou non le défaut précédent.

`restore_r8_after_route5.py` vérifie le garde initial, le script exact,
l'échec avant toute exécution et l'identité du programmateur. Il remet
le SHA R8 déjà confirmé visible. `r8_restored_after_route5/` passe : CPU
accessible et arrêté, mode=0, commit=0, somme mire `0x1ff8f800`, compteur
images de 8 à 68 pendant l'observation. Confirmation visuelle reçue : « Oui, la mire est revenue ». La flash et la SD n'ont pas été écrites.

Les 11 groupes locaux passent dans
`TESTS/dual_board/20261024_route5_reset_review/`. Les erreurs de STA et
matérielles des candidats restent conservées, sans réduction des tests.

`route6_hdmi_reset_only.py` prépare une copie de route3 : exactement les
trois FF de reset HDMI sont déplacés C160 vers C155, avec leur métadonnée.
Les 62 regroupements supplémentaires et la nouvelle contrainte CE de
R4/R5 ne sont pas repris. La même netlist, les broches, DDR5.9/300 MHz,
SDC, SG4 et reset scanout local sont conservés. Ce retour à un changement
plus restreint ne garantit pas la stabilité du nouveau routage ; résultats
statique et matériel restent distincts. Aucun chargement automatique.
Les 11 groupes repassent dans `TESTS/dual_board/20261024_route6_hdmi_only/`.
R6 est lancé hors bac à sable : CST accepté, placement en cours,
PID Gowin initial 1877388. Aucun autre processus de compilation n'a été arrêté.

## R6 terminé — reset HDMI encore hors fenêtre

R6 termine le 24 octobre à 10:31:47. SHA bitstream
`56f1e975be7ddfe7880130898b0fb248caec7114aec5d1b540e496fd8ae7391e`.
Setup −2,599 ns (81 endpoints), hold de données +0,124 ns, recovery
+0,337 ns, removal −0,153 ns. Les trois endpoints comptés en hold par
Gowin correspondent ici aux trois RESET OSER10 en removal. Aucun changement
d'allocation globale par rapport à route3 ; les contrôles locaux demandés
sont conservés. R6 **non chargé**, qualification FAIL.

Canal 1 : front descendant PCLK et front descendant FCLK coïncident dans
la relation de clocks. En analyse min, le reset arrive à 8,947 ns pour une
exigence à 9,100 ns : manque 0,153 ns. Le trajet Q→RESET fait 0,596 ns.
En recovery max, le même trajet fait 1,358 ns et laisse +1,045 ns avant
le front montant FCLK suivant. Le min doit être allongé sans dépasser le
max ; aucune exception SDC n'est ajoutée.

R7 est préparé depuis route3 avec uniquement les trois FF HDMI déplacés
C160→C140, au lieu de C155. Le déplacement vise un délai intermédiaire ;
ce n'est pas une prédiction garantie du routeur. Netlist, DDR, SDC, SG4,
contrôles locaux et options identiques. Les violations setup du blitter
et de son chemin DMA restent à corriger séparément. Les 11 groupes de
`TESTS/dual_board/20261024_route7_hdmi_delay/` passent. R7 est maintenant
lancé hors bac à sable, CST accepté et placement actif (PID initial
1945919). Aucun chargement automatique ; N56r8 reste sur la mire visible.

## R7 terminé et R8 minimal en cours, 24 octobre

R7 (`console_neo_n56r9_route7_hdmi_c140`) termine avec le bitstream SHA
`941305b0e2df43cfc8eb9acd06ff220a807ad9af068f964e6e964459d62eda79` :
setup −3,447 ns, hold données +0,124 ns, recovery −0,759 ns et removal
+0,277 ns. Le déplacement a supprimé les violations de removal HDMI mais
créé des violations de recovery ; les latences des horloges ont aussi changé.
La pire recovery n'est pas HDMI : elle relie `vid_hrstn` à `engine_resetn`.
Le build reste FAIL, non chargé. L'analyse détaillée est dans
`route7_path_review_20261024_final/`.

R8 (`console_neo_n56r9_route8_hdmi_c150`) reprend la base route3 et change
seulement les trois placements des bascules HDMI C160→C150 plus la
métadonnée associée. Les 62 regroupements de R4/R5 ne sont pas repris.
Netlist, SDC, DDR5.9/300, horloges demandées, broches et options sont conservés.
Le préparateur vérifié est `route8_hdmi_reset_only.py`, et le diff exact est
dans `route8_prepared.json`. Gowin est lancé, PID initial 2004396 ; aucun
chargement automatique. Le prochain contrôle doit couvrir tous les checks
setup/hold/recovery/removal et les contrôles structurels, pas seulement HDMI.

## État matériel courant

### Résultat route8 C150 et route9 DMA en cours

`console_neo_n56r9_route8_hdmi_c150` termine avec setup −3,494 ns,
hold +0,124 ns, recovery −1,337 ns et removal +0,347 ns : **FAIL, non
chargé**. Les trois canaux HDMI passent recovery/removal, avec une marge
recovery minimale de +0,063 ns. Les violations restantes concernent
notamment le DMA et la distribution du reset `vid_hrstn` vers les deux
étages `mrst` et les observateurs. Le [rapport de chemins](route8_path_review/README.md)
conserve les SHA et distingue les décomptes Gowin des chemins imprimés.
La preuve combinatoire des 374 alias de reset ne supprime ni le FAIL de
l'audit strict ni les violations temporelles.

`console_neo_n56r9_route9_dma_c150` reprend les entrées route8 et ajoute
huit contraintes régionales du cône DMA, analysé dans
`route9_dma_prepared/`. Son routage est en cours ; aucun résultat ni
chargement matériel n'est déduit de sa progression. La proposition
indépendante [de deux LUT du chemin position](dma_tail_from_r8_proposal/README.md)
reste séparée de cette expérience. Aucun RTL partagé, fréquence DDR ou
fichier Pro Dock n'est modifié par ces essais de placement.

### Carte laissée en fonctionnement

**Mise à jour après essai route9 demandé par l’utilisateur :** R9 échoue
deux fois avant l’examen CPU (DMI timeout), à 1 MHz puis à 100 kHz avec
deux secondes après programmation. Aucun snapshot de reset ni écriture
framebuffer n’a donc été exécuté. Le premier repli N56r8 a nécessité une
nouvelle observation à 100 kHz ; elle passe. Le second repli passe
directement à 100 kHz : CPU garé, +62 images, checksum mire `0x1ff8f800`.
L’utilisateur confirme de nouveau « Oui, la mire est revenue ».
Dernière ancre : `r9_route9_rgb_trial_100k/result.json`, `restored.log`
et `visual_confirmation_fallback.json`. Les ancres antérieures ont été
consommées. Les échecs et le repli intermédiaire sont conservés dans
`r9_route9_rgb_trial/` et `r9_route9_fallback_recheck/`.

**N56r8 HDMI SG4**, SHA
`51841fe4ae76a7eb635a0398534f35b6c7030fa8b768d88b892fede3b1601c35`,
CPU arrêté dans le parking ROM, mire interne sélectionnée et somme vérifiée.
Ancienne ancre, désormais consommée : `r8_restored_after_route5/result.json` et `after.log`.
L’utilisateur confirme : « Oui, la mire est revenue ». Framebuffer
et GPU complet restent non qualifiés, timing R8 toujours FAIL en setup.
Les ancres précédentes route2 et route5 sont consommées ; ne pas les
réutiliser. Aucun Linux démarré, flash/SD inchangées, Pro Dock inchangée.

### Comparaison DDR PHY / broches / calibration après l'échec route9

L'[analyse des chemins DDR](route9_ddr_io_compare/README.md) compare N56r8,
route2 et route9, sans accès carte. Les 72 broches et 201 primitives PHY
sont identiques en connexion/paramètres. Les arcs SDF directs
PHY↔broches DQ/DQS, commande/adresse, DM et CK sont identiques ; RESET_n
et les liaisons internes de fabric diffèrent. Un arc parallèle vers A14
passe de 2,974 ns sur route2 à 5,239 ns sur route9, à environ 75 MHz : ce
délai n'est pas un slack ni une preuve de panne.

Les dérivations DQ vers la logique d'initialisation sont suivies jusqu'à
leur première bascule. Maximum PAD→FF.D : 3,058 / 3,063 / 3,084 ns.
La calibration utilise donc aussi une branche différente de la capture
primaire IDES, mais son état réel reste inconnu sur route9. Les analyses
structurelles et les sommes de délais ne permettent pas de conclure que
DDRinit est resté à zéro. Les qualifications FAIL restent inchangées ;
N56r8 avec mire demeure la dernière configuration chargée.

### Diagnostic causal demandé : figer les images avant de modifier le placement

L'utilisateur demande de sortir de la boucle « nouveau placement / nouveau
timing / même panne ». Les violations statiques restent enregistrées, mais
aucune causalité avec le timeout DMI n'est établie. Aucun nouveau routage
n'est lancé pour expliquer le démarrage R9.

Deux symptômes restent distincts :

- N56r8/R2 : CPU accessible et accès DDR de diagnostic réussis ; lecteur
  vidéo défaillant. Sur R2, l'observateur rapporte `mrst0=1`, `mrst1=0`,
  lecteur IDLE et aucune requête acceptée. Cela ne démontre pas un manque
  de bande passante DDR.
- R9 : programmation DONE puis transactions DMI bloquées ; DDRinit n'a
  encore été observé ni à zéro ni à un. Un échec de calibration reste une
  hypothèse, pas un résultat.

Le prochain essai préparé réutilise exactement N56r8 puis R9 puis N56r8.
Il observe V13 (`led_n=~ddr_init`) indépendamment du CPU, sans recompilation,
sans framebuffer et sans démarrage Linux. Une disponibilité pour observer
la LED est demandée à l'utilisateur ; aucun chargement Neo supplémentaire
n'est effectué avant cette observation coordonnée.

Si DDRinit reste bas, la recherche remonte vers PLL/DLL, reset de l'IP et
étapes de calibration. S'il est haut, la recherche suit sa synchronisation
et la libération POR/HW du CPU. Une lecture DMI bornée après l'observation
LED doit distinguer une panne reproduite d'un démarrage exceptionnel.
La restauration N56r8 conserve un contrôle du témoin et de la mire.

### Résultat du contrôle LED/caméra du 24 octobre

L'essai préparé ci-dessus est maintenant exécuté, sans changement de
bitstream. **La LED utilisateur reste allumée sous R9 : DDRinit est donc
annoncé à un**, alors que le DMI expire encore après le chargement. Le TAP
AE350 répond, mais aucune confirmation CPU_HALTED n'est obtenue sous R9.
Le repli N56r8 retrouve le CPU, +62 images, le checksum `1ff8f800` et la
mire visible. La caméra locale Nuroum conserve les trois vues.

L'utilisateur identifie la LED sur N56r8 puis confirme qu'elle reste
allumée en continu sous R9. Le dernier contrôle N56r8 est réalisé directement
par caméra, à sa demande. Les provenances sont séparées dans le
[rapport de l'essai](r9_led_compare_trial/README.md) et son complément caméra ;
le résultat brut du script limité aux réponses utilisateur reste inchangé.

L'hypothèse d'une calibration qui ne termine jamais ne décrit pas cet
essai R9. L'intégrité DDR reste non qualifiée ; lock AE350, horloges et
réception du reset CPU restent à mesurer. Aucune cause physique précise
n'est encore démontrée. La précédente ancre `r9_route9_rgb_trial_100k`
est consommée pour cet essai. Nouvelle preuve de l'état final :
`r9_led_compare_trial/result.json`, `restored.log` et
`camera_observations.json`. Neo laissée sur N56r8, CPU arrêté et mire interne
visible ; aucune modification Pro Dock, SD ou flash.
