# Neo N56r15 : expérience de séquencement POR/HW à 50 ms

Le 25 octobre 2026, l'utilisateur choisit une marge de **50 ms**, en réponse
au délai de 20 ms rencontré dans l'exemple SDK AE350. Ce délai SDK n'est
pas un minimum constructeur établi. Cette expérience teste une hypothèse ;
elle ne constitue pas une explication déjà démontrée de HRESETN maintenu bas.

## Périmètre et comparaison

Le candidat isolé est `tang/impl/console_neo_n56r15_reset50ms/`. Il dérive
de la netlist exacte N56r10 :
`0b5ea22b83faf2bae943f399bdb734dc1e66c8507310dc25e054290e24ad6157`.

Un séquenceur à 50 MHz remplace uniquement la donnée DDR-ready à l'entrée
du premier des deux registres AHB qui pilotent POR_N/HW_RSTN du macro AE350.
Les deux registres, leur reset, leur horloge et leur INIT sont conservés.
Les resets PLL et DDR ne sont pas modifiés. La DDR reste en IP 5.9 à 300 MHz.
Les sources de développement communes et la référence Pro Dock sont intactes.

- Au chargement, le mode par défaut attend 2 500 000 cycles de référence
  après disponibilité DDR/PLL synchronisée : compteur de 22 bits, 50 ms.
- Le mode court ne rajoute pas ce délai. Les deux modes appliquent, lors
  d'une commande, la même impulsion de reset de 1 000 cycles, soit 20 µs,
  après observation de POR/HW appliqué bas. Ce retour n'est pas HRESETN.
- Si AHB s'arrête avant application du reset, la demande reste maintenue
  jusqu'à observation du retour. Une perte de disponibilité échantillonnée
  relance le délai complet ; les pertes très brèves non échantillonnées
  ne sont pas couvertes par cette affirmation.
- L'UART brut BL616 à 2 Mbit/s reçoit `A5 5A 52 31 35 mode complément 0D`,
  avec mode 0 ou 1 et complément XOR FF. Un délai de 2 ms entre octets
  invalide une commande partielle. Le numéro de commande sur quatre bits
  permet de vérifier sa réception dans GAO.

Le futur essai court/long/court réutilise **le même bitstream et son même
routage**. Il compare des resets à chaud. Le chargement initial avec délai
long est un essai distinct ; son résultat ne doit pas être confondu avec
celui d'un reset à chaud. Un succès du nouveau bitstream seul ne suffirait
pas à attribuer l'amélioration au délai, puisqu'il aura été rerouté.

## Observations préparées

22 sondes GAO incluent PLL lock/reset, DDRinit, les deux étapes POR/HW,
HRESETN, reset vidéo, mode, compteur de commandes, maintien du reset et
fin du délai. Deux compteurs indépendants du reset CPU fournissent des
témoins divisés des horloges AHB et RTC. Le chemin cœur 800 MHz n'est pas
chargé par une nouvelle sonde ; son activité n'est donc pas directement
mesurée ici. PRESETN et DDR_RSTN restent aussi hors des sondes de cet essai.

La capture est préparée sur le relâchement de la demande de reset, à 50 MHz,
sur 4 096 points. Il faudra encore vérifier le mapping des sondes après
routage, puis distinguer tampon initial, capture réarmée et capture fraîche.
Une absence de réponse malgré le délai long, AHB et RTC actifs, ne validerait
pas l'hypothèse d'une simple durée insuffisante.

## Vérifications obtenues

| Étape | Résultat |
|---|---|
| Simulation RTL, durée réelle de 50 ms | PASS : commandes valides/invalides/périmées, modes court/long, AHB arrêté, reprises après perte DDR/PLL |
| Synthèse du séquenceur, Gowin 1.9.12.03 | PASS, netlist SHA `e2032617595214b3a2e2a7896e6b8c62c2210dd27a07a40c7da97ceede3a5e70` |
| Simulation de cette netlist avec primitives Gowin | PASS, sorties comparées au RTL pendant la totalité des scénarios ; `mapped_50ms_r2/result.json` |
| Assemblage dans la netlist parent | Réversibilité exacte ; 144 modules parent inchangés, sections protégées intactes, un seul GSR global |
| Campagne commune des deux cartes | 11 groupes PASS, `TESTS/dual_board/20261025_neo_reset50ms/result.json` |
| Première lecture Gowin du candidat complet | FAIL avant placement : déclarations ajoutées après utilisation ; preuves conservées dans `failed_parse_01/` du candidat |
| Correction de format de netlist | Déclarations avant utilisation, une par ligne, bus explicitement dimensionné ; aucune modification du helper synthétisé |
| Nouvelle campagne commune après correction | 11 groupes PASS, `TESTS/dual_board/20261025_neo_reset50ms_decl/result.json` |
| Lecture du candidat corrigé | Netlist principale, GAO et CST acceptés ; placement lancé |
| Timing complet / matériel | À établir ; aucun essai R15 sur carte à cette étape |

Le modèle de simulation du macro AE350 est vide dans la bibliothèque
installée. Le PASS de simulation valide le séquenceur ajouté, pas le
fonctionnement interne du bloc dur ni la cause du blocage observé sur R10.
Il ne couvre ni métastabilité analogique ni timing du design routé.

## Résultat du routage et premier essai sur Neo

Le routage termine le 25 octobre à 10:50. Le bitstream exact testé est
`ao_0.fs`, SHA-256
`8b005988433a70fdef654f5e2e7f93b3ba484764c1be44bb356bd1418931227b`.
La qualification reste **FAIL** : setup −3,844 ns (31 endpoints), hold
−0,305 ns (7 endpoints GAO), recovery −4,972 ns, removal +0,269 ns.
Le pire recovery relie le reset vidéo à un registre de reset GPU ; il ne
démontre pas une cause interne du blocage AE350 précédent.

L'audit `postroute/result.json` retrouve les huit horloges PRIMARY requises.
Les 142 370 cellules applicatives d'origine sont présentes, avec leurs
paramètres inchangés. La seule connexion d'origine modifiée est le D du
premier registre `init_sync` ; les 315 cellules supplémentaires appartiennent
au séquenceur. Le chemin rapporté `delay_done` → premier FF AHB respecte la
borne CDC de 8 ns avec une marge de +3,265 ns. Cela ne qualifie pas tous les
chemins du design. Les dix audits structurels passent. L'audit strict de
profil DDR refuse la modification explicite du fichier `ae350_soc.v` : ce
FAIL est conservé, avec la preuve séparée de la modification unique du reset.

L'essai SRAM `cold_trial_01/` identifie le programmateur Neo série
`2025041420`, bus 3:28, et l'ESP-Prog distinct sur `3-4.4.2` ; le verrou
Neo est tenu pendant l'opération. Aucun accès Pro Dock, écriture SD/flash,
chargement Linux ni accès DDR n'est demandé.

1. Avant programmation, la lecture brute DMI de DMCONTROL reste BUSY sur R10.
2. Le chargement de R15 termine avec DONE `0x00026220`, sans drapeau d'erreur.
   Il ne s'agit pas d'une relecture complète de la SRAM FPGA.
3. La photo prise avant toute commande d'arrêt CPU montre les bandes ;
   l'utilisateur confirme « il y a la mire !!!!! ».
4. La même lecture brute DMCONTROL aboutit, statut 0 et donnée 0. Seule la
   première réponse concerne ce registre ; les NOP suivants n'émettent pas
   de nouvelles lectures. Aucun reset CPU ni écriture DMI n'avait été demandé.
5. Un essai séparé, `cpu_registers_02/`, examine le hart, l'arrête puis lit
   le PC `0x80000004` et les registres GPU. ID `0x47505531`, mode 0, dimensions
   `0x02d00500`, somme vidéo `0x1ff8f800`. Le compteur d'images avance de 63
   entre les deux relevés séparés par une attente de 1 s plus les lectures
   JTAG ; ce n'est pas une mesure de 63 FPS. Le CPU reste arrêté et R15 chargé.

Le premier essai `cpu_registers_01/` avait déjà lu correctement le GPU, mais
son appel Tcl `reg pc` n'avait pas imprimé la valeur dans le journal. Son
résultat incomplet est conservé ; le second utilise explicitement
`get_reg -force {pc}` et imprime la valeur. Aucun reset/rechargement entre eux.

## Capture GAO et limites d'interprétation

La capture `r15_initial_read_01/` est lue avec la configuration exacte R15.
Après programmation, le pilote `ftdi_sio` avait repris le canal A du
programmateur et empêchait l'énumération D2XX. Seul ce canal JTAG est détaché
temporairement par libusb, après contrôle du numéro de série et du chemin
USB ; il est réattaché à la fin, retour 0. Le canal B reste intact. Aucun
rechargement, réarmement explicite ni forçage de trigger dans cette lecture.

Le CSV contient 4 096 points, période prévue 20 ns, soit 81,92 µs. Le libellé
µs du CLI est incorrect. Mode 1 et numéro de commande 0 sont constants :
aucune commande de changement de délai n'a encore été envoyée.

Les transitions observées sont : `trial_done`/demande au point 126,
POR/HW au point 127, HRESETN au point 137, reset vidéo au point 138. La grande
majorité du tampon montre donc les resets libérés. Les horloges divisées
ont des demi-périodes de 80 et 640 échantillons, cohérentes avec AHB 80 MHz
et RTC 10 MHz pour une référence de capture 50 MHz. Le 800 MHz du cœur n'est
pas mesuré par ces sondes.

**Anomalie conservée : les deux dernières lignes reviennent aux niveaux
initiaux, dont `trial_done=0`, sans changement de PLL, DDR, mode ou commande.**
Cet ensemble n'est pas expliqué par le fonctionnement RTL prévu du compteur.
Bouclage/ordre du tampon, lecture et intégrité de la capture restent à
discriminer ; on ne déduit pas de ces deux lignes un nouveau reset physique.
Les holds GAO en échec limitent toujours cette preuve. Le résultat positif
de démarrage repose également sur la mire, la réponse DMI et les lectures
AHB indépendantes. La fenêtre ne mesure pas la totalité des 50 ms et l'ordre
absolu d'acquisition du tampon initial n'est pas encore démontré.

Le framebuffer en DDR, Linux et le GPU complet restent **non validés sur
R15**. Le délai de 50 ms est associé à ce premier démarrage réussi, mais le
routage a également changé. La comparaison court/long sur le même bitstream
reste à effectuer ; même son résultat décrira un reset à chaud, distinct du
chargement FPGA initial.

## Essais DDR et commandes GPU, sans nouveau bitstream

Les dossiers ci-dessous concernent toujours le SHA R15 ci-dessus, CPU arrêté
dans la ROM à `0x80000004`, sous verrou Neo, sans Linux ni écriture SD/flash.
Ils ne qualifient ni la DDR complète ni le timing. Les écritures de test
portent uniquement sur la DDR volatile et les registres GPU.

| Preuve | Résultat mesuré |
|---|---|
| `framebuffer_trial_01/` mémoire | 16 signatures différentes de 2 Kio, toutes présentes simultanément, deux relectures exactes chacune ; adresses réparties entre 0 et `0x3ffff800`, voisins séparés de 2 Kio inclus |
| Même essai, image | 1 843 200 octets RGB565 chargés à `0x01700000`, vérification CPU intégrale exacte |
| Même essai, lecteur vidéo | +62 images balayées et +62 images lues, mais +3 806 underflows et somme DDR incorrecte ; lecteurs actifs, requêtes/réponses équilibrées aux deux captures |
| `resolution_matrix_01/` | Modes 1280×720 / 640×360 doublé / plein / demi : aucune des 32 sommes attendues correcte ; maximum 207 cycles mémoire par ligne en plein, 139 en demi |
| `gpu_copy_trial_01/` | TARGET puis CLEAR terminent ; les 4 Kio visés restent identiques à la graine, donc aucun COPY n'est envoyé |
| `command_observer_01/` | 13 configurations terminent ; en-têtes exacts dans la capture géométrie, en-tête pixels nul dans toutes les lectures répétées ; rejets internes V1 sur les commandes transmises aux pixels |
| `legacy_memory_01/` | Remplissage de 32 octets par le moteur historique exact, avec les 96 octets voisins inchangés |
| `warm_long_01/` | Reset chaud long reçu : compteurs GPU remis à zéro, CPU et mire accessibles ; TARGET/INVALIDATE retrouvent aussitôt en-tête pixels nul et deux rejets |

La demi-résolution conserve le stride de 2 560 octets et affiche le coin
640×360 doublé de la même image. Le lecteur relit chaque ligne de sortie ;
le volume DDR est divisé par deux, pas par quatre. Les underflows par image
varient entre essais, sans amélioration systématique en demi-résolution.
La durée mesurée d'une lecture de ligne est largement inférieure à la durée
d'une ligne vidéo, mais ce maximum ne couvre pas nécessairement toute attente
ou requête perdue. Il ne suffit pas à exclure tout défaut d'arbitrage/CDC.

**Correction du premier constat de remplissage :** le banc initial contrôlait
les erreurs transport et raster, mais pas le compteur V1 à `0xe9001034`.
Il serait faux de conclure « aucun compteur d'erreur ». La lecture suivante,
avant toute nouvelle commande, retrouve deux rejets V1 pour TARGET et CLEAR.
Le succès d'une fence signifie terminaison, pas succès de la commande.
La comparaison des octets avait bien conservé l'essai comme FAIL.

Les captures cohérentes de l'observateur donnent `mrst=3` et les douze sorties
`engine_resetn=0xfff`, 16 puis 120 mots reçus, égaux aux compteurs hôte, et
14 snapshots terminés. Ce sont les niveaux observés aux points de sonde,
pas une mesure analogique sur chaque entrée de registre. Les en-têtes bruts
géométrie/pixels sont synchronisés bit par bit ; ils sont lus GPU inactif et
trois fois identiques, sans être présentés comme un bus CDC atomique.

Le reset chaud utilise la trame exacte `a5 5a 52 31 35 01 fe 0d` sur le relais
UART 2 Mbit/s. Le compteur de commandes passe de 16 à 0 et le compteur V1 de
11 à 0, puis deux commandes reproduisent les rejets. Aucun rechargement FPGA
n'a été nécessaire. Cela montre la persistance du défaut après reset chaud
long ; cela ne compare pas encore démarrage froid court et long.

## Hypothèses limitées et consigne de diagnostic

`pixel_capture_route_comparison.json` décrit une différence de ressource :
le CE `u_accel/u_v1/u_pixels/n37565_3` des 256 FF `packet` est absent du
tableau des réseaux globaux de R1/R8/R10 et apparaît en LW sur R15. Les
primitives et leur fonction restent identiques. **Cette corrélation ne
démontre ni défaut LW ni cause temporelle.** Le registre intermédiaire
`shader_command` n'est pas observé directement par l'instrumentation actuelle.
Un en-tête nul à la destination ne suffit donc pas à identifier son CE comme
cause plutôt que ses données d'entrée ou une autre condition de capture.

Après la remarque de l'utilisateur sur la répétition des essais de routage,
l'essai de routage local proposé est suspendu. **Aucun R16 n'a été préparé,
routé ou chargé.** R15 conserve la mire et le CPU arrêté. La campagne locale
`TESTS/dual_board/20261025_r15_pixel_capture/` passe ses 11 groupes ; elle ne
prouve pas le fonctionnement matériel du snapshot R15.

La reprise documentaire est archivée dans `primitive_doc_review/` : UG303
1.0E (CFU/FF), SUG283 3.6E, UG306 1.0.7E et SUG550 2.4E de l'installation,
avec empreintes. UG303 §3.4.2 décrit DFFRE comme registre à front montant et
reset synchrone actif haut ; le modèle officiel `simlib/gw5a/prim_sim.v`
rend le reset prioritaire sur CE. Le reset est inversé depuis `engine_resetn[4]`
pour le moteur pixels et depuis `[2]` pour la géométrie. Aucune règle lue à
ce stade ne justifie de déclarer LW défectueux. L'étape suivante est la
confrontation cycle par cycle de la commande réelle avec la netlist figée,
avant toute nouvelle modification matérielle.

`command_mapped_02/` rejoue ensuite **22 configurations** (dont des cas
invalides), avant/après reset chaud, dans les 12 modules exacts extraits de
la netlist R15 et les primitives officielles Gowin. Les 16 transferts vers
les pixels capturent l'en-tête exact, les fences et rejets attendus sont
corrects, aucune commande DDR n'est émise. Le bench contrôle la valeur
présente sur les véritables broches D des FF au front d'activation ; il ne
se contente pas d'observer le résultat final. **PASS fonctionnel uniquement**,
sans annotation SDF ni reproduction du défaut matériel : ce résultat ne
fournit pas une cause et ne transforme pas le diagnostic en problème de timing.

Le premier essai `command_mapped_01/` avait échoué dans le banc : les bits
29/30 de l'alias RTL `shader_command` restent Z dans la netlist optimisée,
alors que leurs destinations sont reliées au signal `shader_command_31`.
La seconde version lit les broches D réelles. Aucun module ou primitive
simulée n'a été changé ; les deux versions du banc et leurs FAIL/PASS sont
conservés. Le petit correctif ultérieur du commentaire Python ne modifie
pas le bench exécuté, archivé avec `controller.py` et ses empreintes.

La prochaine observation matérielle utile doit départager **données du
registre intermédiaire, activation de capture et reset à destination**.
L'instrumentation actuellement chargée n'expose pas ces trois valeurs à
ce front. On ne présente donc pas une nouvelle contrainte LW comme correctif
démontré. Le développement du jeu reste un chantier parallèle indépendant.

## R16 : observation des captures, sans correctif de routage supposé

Après l'autorisation « et bien vas-y », le candidat
`tang/impl/console_neo_n56r16_gao_pixels` est préparé. Il ne reprend pas
l'expérience suspendue consistant à contraindre le CE sur une route locale.
Il garde **exactement la netlist applicative R15**, SHA-256
`0921fe3fd32fca042f973b2e24f3a6b906f9c8b2e9d83feb8b2d76f7d1a2c46d`,
les CST/SDC, DDR 5.9/300 MHz, PLL et reset de 50 ms. Le seul ajout au
snapshot de sources est `pixel_capture.gao`. Les sources communes et les
références Pro Dock sont intactes.

Les **113 signaux distincts**, échantillonnés sur `gpu_clk` à 75 MHz,
comprennent les en-têtes géométrie, les véritables entrées D des registres
pixels, leurs sorties Q, le CE, le reset et les états du transfert. Les bits
D 29/30/31 partagent la même source mappée : les alias flottants du premier
banc ne sont pas sondés. Le déclenchement initial est `shader_start=1`, avec
512 échantillons et une position demandée de 32. L'envoi d'un premier TARGET
doit avoir lieu seulement après lecture de compteurs de commandes nuls.
Cette commande de configuration n'émet pas de requête DDR.

`prepare_pixel_probe.py` vérifie les empreintes avant lancement. Les
11 groupes de `TESTS/dual_board/20261025_r16_observation/` passent.
Le processus Gowin 1.9.12.03 est lancé le 25 octobre à 15:49, PID 2637597,
avec la licence publique isolée de R15. Les entrées et les sondes sont
acceptées, le placement est en cours à ce point du journal. **R16 n'est
pas encore chargé** ; la Neo reste sur R15 et sa mire interne.

`pixel_trace_check_01/` valide le décodage sur 373 cycles de simulation de
la netlist exacte, avec 16 captures avant/après reset. Les contrôles
détectent aussi les défauts injectés dans les traces : capture manquée, CE
absent, reset inattendu, valeur inconnue et désaccord entre colonnes
dupliquées. L'en-tête à bits D communs est reconstruit correctement. Les
fichiers simulés et les FAIL antérieurs sont conservés.

Le wrapper généré relie les 113 données au même port et à la même horloge ;
la mémoire est large de 114 bits car le déclencheur est aussi stocké.
**Les internes GAO sont chiffrés** : l'égalité de latence entre sondes n'est
pas indépendamment vérifiée. Le décodeur présente donc `Q[n+1]=D[n]` comme
un contrôle conditionnel à des échantillons alignés avant front. Il ne
transforme pas une discordance en preuve de défaut CE, reset, LW ou timing.
Les lignes finales ne sont pas supprimées pour masquer une anomalie.

L'audit post-routage préparé dans `audit_pixel_probe.py` doit comparer les
cellules applicatives, paramètres, contraintes actives, horloges et timing.
Son résultat est encore en attente. L'insertion GAO peut modifier les routes
et les charges : il faudra d'abord reproduire le rejet TARGET sur le
bitstream instrumenté, puis confronter les observations. Aucun chargement
automatique n'est associé au routage.

Le placement termine ensuite et le routage commence. Un observateur logiciel
attend `route_result.json`, vérifie la fin normale puis exécute cet audit
en lecture seule. Il n'enchaîne pas de chargement matériel. Le processus
Gowin exact reste actif après 18 minutes ; aucun autre build n'est lancé.

Les scripts `load_pixel_probe.py` et `read_pixel_probe.py` préparent la suite
bornée : empreintes explicites du bitstream/audit, verrou Neo, vérification
du parking CPU et de l'état R15 avant reconfiguration, puis un seul TARGET.
En cas d'échec d'exécution après tentative de chargement, le retour prévu
est le **même R15**, sans recours à une ancienne ancre R8/R10. La lecture
GAO se fait ensuite séparément, sans réarmement, avec un délai maximal de
45 s et restitution du canal JTAG au pilote noyau. Ces scripts ne sont pas
encore exécutés sur carte. `pixel_probe_commands_check_01/` passe six essais
Tcl hors matériel : acceptation, rejet V1 observé, identifiant incorrect,
compteurs déjà utilisés, erreur préalable et absence de terminaison.

### Attente après l'analyse temporelle, 25 octobre vers 17:27

Le journal R16 atteint « 95% Timing analysis completed » vers 16:16, mais
aucun FS/TR/VO/SDF final ni `route_result.json` n'est encore produit à 17:27.
Le seul processus identifié, PID 2637597, tourne depuis 1 h 37, avec 99,9 %
CPU, 2,8 Gio résidents et sans swap. Son répertoire courant est exactement
le candidat R16. Le cache `console_neo.pr` de 193 Mio existe depuis 16:15.
Ces constats ne permettent pas de distinguer calcul très long et boucle
logicielle ; « analyse terminée » dans le journal ne donne pas encore les
marges de timing et n'est pas un PASS.

Une tentative de lecture de pile GDB, limitée à ce PID et sans modification
du programme, est refusée par le système avant attachement. Les politiques
observées sont `ptrace_scope=1`, `perf_event_paranoid=4` ; elles ne sont pas
modifiées. Le premier observateur d'audit expire après une heure. Une nouvelle
attente bornée à quatre heures est lancée et consignée dans
`r16_wait_after_timing_02.json`, toujours sans chargement carte ni nouveau
build. Le cache et le calcul original sont conservés.

SUG100 4.4.6E documente la reprise incrémentale `.pr`, mais celle-ci refait
un flot de placement/routage : aucun export indépendant préservant sûrement
le routage exact n'est établi ici. Aucune reprise n'est lancée sur cette
seule hypothèse. R15 reste la dernière version chargée sur Neo ; le rejet
GPU n'a pas encore été observé avec les nouvelles sondes.

### Localisation du calcul Gowin par lecture de pile

À la relance « toujours pas de R16 ? », le journal et les sorties sont encore
inchangés à 17:55. `inspect_r16_process.py` vérifie le PID 2637597, son
starttick **41181845**, son exécutable, sa commande et son répertoire R16.
Le contrôle préalable ne s'attache pas au processus. L'exécution autorisée
via `sudo -n` réussit ensuite : deux attachements GDB bornés, sans commande
d'écriture ni appel de fonction dans le processus observé. GDB désactive
l'auto-chargement de scripts et debuginfod, se détache après chaque lecture,
et le processus reprend en état R. Aucun réglage noyau n'est changé.

Les traces sont conservées dans `r16_process_stack_01/`, avec script figé,
empreintes et états avant/après. Les frames nommées donnent :

- `X8ASSIGN::X8assiInfo::getOneNode` puis `srcAdjustOneTime` ;
- `X8ASSIGN::Node::getType` puis `desAdjustOneTime`.

Le déroulage de pile devient incomplet plus haut (`??`) : ces lignes ne
sont pas traitées comme une chaîne d'appels entièrement fiable. Elles
localisent néanmoins les deux échantillons dans les ajustements de
connexions X8 de Gowin, et ne justifient plus de supposer une simple attente
d'écriture des rapports. Elles ne prouvent pas à elles seules une boucle
infinie, son déclencheur, ni un défaut GPU/DDR.

`libgowin.so` du runtime isolé résout vers la bibliothèque officielle
`/home/michael/gowin/IDE/lib/libgowin.so`, SHA-256
`7e7920244fbfa518c228e51a2e8143c67d8c19cfba535d1c4d3700b780f10b4d`.
La lecture statique des symboles/appels, enregistrée dans `x8_callers.json`,
montre notamment `assignX8sToNets`, `conNetBaseDes` et `timingOptForDes`.
Ce dernier appel est conditionné par `globalMem::getTimingFlag` ; SUG1220
2.0E documente l'option `-timing_driven`. **Il reste à établir si cette
branche précise est celle de l'attente observée**, car les routines basses
sont partagées. Aucun drapeau, registre du processus, bibliothèque, RTL,
CST ou SDC n'est modifié sur cette seule piste.

La formulation antérieure « routage terminé » décrivait seulement la fin
des phases affichées 0–3 : une étape interne d'affectation reste active
après le message à 95 %. Le `.pr` est conservé, mais ce n'est toujours pas
un bitstream final utilisable. Aucun autre routage n'est lancé à ce stade.

### Résultat final R16 : échec de routage de l'instrumentation

Le processus original se termine le 25 octobre à **21:18:19**, code 1.
Le rapport donne **5 h 28 min 36 s** de compilation, dont **5 h 2 min 11 s**
pour sa dernière phase de routage. La ligne finale est :

```text
ERROR (PR0009) : Failed to route with '4' unrouted nets for GAO design
```

Le marqueur à 95 % ne signifiait donc pas que toutes les connexions étaient
routées. Les échantillons de pile précédents sont compatibles avec cette
recherche X8 prolongée ; ils ne démontrent pas une boucle infinie. La sonde
de progression supplémentaire n'a pas été attachée : son contrôle préalable
a constaté la disparition du PID. L'échec appartient au processus original ;
aucun nouvel essai, arrêt du compilateur ou changement d'option n'est effectué.

`r16_route_failure_01/result.json` conserve l'erreur, les empreintes et les
contrôles après terminaison. La netlist d'entrée et les CST/SDC sont toujours
identiques à R15 ; le manifeste des sources et le wrapper public des 113
sondes sont conformes. Les **142 685 cellules applicatives** et leurs
paramètres dans le VO émis sont identiques à R15. Ce VO ne valide pas les
connexions physiques manquantes et n'expose pas l'intérieur chiffré de GAO.

Les rapports TXT/HTML ne donnent pas les noms des quatre connexions. Le
cache `.pr`, chiffré, date de 16:15, avant l'échec ; sa présence ne prouve
pas qu'il contient l'état final de ces connexions. Il n'y a **ni FS, ni TR,
ni SDF final**. L'audit prévu après succès n'est pas exécuté et aucun
chargement R16 n'a lieu. Le statut est **ROUTING_FAILED**, sans qualification
temporelle ou matérielle. L'attente automatique a quitté sur cette erreur.

Neo conserve R15 (SHA `8b005988433a70fdef654f5e2e7f93b3ba484764c1be44bb356bd1418931227b`),
dernier état observé : mire interne, CPU arrêté. Aucun nouvel accès matériel
n'est fait dans ce diagnostic du compilateur. La Pro Dock n'est pas touchée.
L'identification des connexions non routées reste ouverte ; cet échec de
construction ne constitue pas une cause du défaut GPU observé sur R15.

### R17 : observation ciblée de l'opcode, 25 octobre à 22:58

L'étape suivante est **un seul candidat d'observation**,
`console_neo_n56r17_gao_opcode`, préparé par `prepare_opcode_probe.py`.
La netlist applicative reste exactement celle de R15. DDR 5.9/300 MHz,
PLL, reset 50 ms, CST/SDC et options de placement/routage sont conservés.
Par rapport à R16, seuls la liste des signaux échantillonnés et l'identifiant
GAO changent. Horloge GPU 75 MHz, profondeur 512, déclencheur `shader_start`,
position 32 et capture initiale sont identiques.

Le nombre de sondes passe de **113 à 32** : octet `[31:24]` de l'en-tête
géométrie, entrée D réelle et sortie Q pixels, puis dix contrôles de capture
et d'état. Les trois bits D 29/30/31 partagent réellement un fil : l'alias
est conservé, ce qui donne 22 fils de données distincts + 10 contrôles.
Le but est de distinguer commande absente en amont, entrée D incorrecte,
capture désactivée/reset actif et sortie Q incorrecte. Les 24 bits bas et
le payload ne sont pas capturés ; les en-têtes complets restent lus par AHB.
La réduction des sondes diminue le nombre de connexions ajoutées ; elle
ne prétend pas identifier ni corriger les quatre connexions R16 inconnues.

Le décodeur réduit a été confronté à la trace de simulation mappée R15
déjà vérifiée : **373 échantillons, 16 captures avant/après reset**. Les dix
contrôles comprennent capture manquée, CE absent, reset inattendu, valeur
inconnue, absence de capture, alias de D, doublon incohérent et mauvais jeu
de sondes. Une corruption d'un bit bas est volontairement invisible à la
capture réduite : cette limite est testée et conservée explicitement.
Preuves : `opcode_trace_check_01/` ; ce n'est pas une nouvelle simulation
temporelle ni une validation matérielle.

Les **11 groupes locaux des deux cartes passent** dans
`TESTS/dual_board/20261025_r17_observation/`. Le wrapper GAO généré confirme
32 sondes, 33 bits mémorisés avec copie du déclencheur et l'horloge attendue.
Le constructeur démarre le processus **2794912** à 22:58:30 ; la génération
GAO et la lecture des contraintes aboutissent, le placement commence.
Timing, succès du routage et essais matériels restent en attente.

`watch_opcode_route.py` attend au plus six heures le résultat de ce seul
processus et lance uniquement l'audit de ses sorties en cas de succès.
Il ne lance aucun autre routage et ne charge aucune carte. Les scripts
`load_opcode_probe.py` et `read_opcode_probe.py` conservent le verrou Neo,
les empreintes explicites et le repli R15 ; ils sont préparés, pas exécutés.
Leur commande TARGET et leurs gardes Tcl sont identiques à la version
testée précédemment. L'origine des adaptations est dans
`opcode_tools_derivation.json`, le contrôle du wrapper et les empreintes
finales dans `opcode_tools_preflight.json`.

Neo reste R15, dernier état observé : mire interne et CPU arrêté. Aucun
nouvel accès carte ni modification Pro Dock n'est effectué dans cette étape.

Le script `assemble_trial.py` conserve les empreintes et vérifie que
l'annulation des deux modifications d'intégration restitue exactement
le texte parent complet. Les CST/SDC hérités restent inchangés. Le contrôle
des délais réels des nouvelles traversées et de GAO reste à faire.

## R17 : inspection du calcul dans la nuit du 25 au 26 octobre

À 00:28, le processus R17 tourne encore depuis environ 1 h 30, avec un cœur
occupé. Le journal reste à « 95 % — Timing analysis completed » depuis
23:24. Aucun FS, TR ou SDF final n'est présent à ce relevé. Ce pourcentage
ne permet pas d'annoncer un délai de fin.

Les inspections bornées identifient le PID, son heure de démarrage, son
répertoire et les SHA du programme et de la bibliothèque avant attachement.
Elles lisent seulement la pile et quelques objets du routeur, sans appel de
fonction dans le processus, écriture, breakpoint ou opération FPGA. Chaque
attachement se termine par un détachement vérifié et le calcul reprend.

Un cadre X8 `adjustByFreeSearch` vérifié par les prologues et les registres
sauvegardés donne un compteur de 193 traitements, une limite de 2 000 et une
liste de travail de 226 entrées ; la cible du moment porte l'index interne
63, en R3C97. Ce ne sont ni 226 nets non routés ni 193 succès. L'index n'a
pas été associé à un signal RTL. Le relevé suivant ne retrouve plus ce
cadre ; une lecture complémentaire trouve des adresses de retour compatibles
avec `conDesInOrder`, toujours dans la recherche de connexions X8. Le
déroulement générique de pile reste incomplet : ces données ne démontrent
ni convergence, ni boucle infinie, ni cause matérielle sur la carte.

Le premier décodeur de progression refusait la branche `adjustBlockNode` ;
cet échec est conservé dans `r17_process_progress_01`. La version suivante
reconnaît son prologue après examen du désassemblage de la même bibliothèque.
Les traces, empreintes et limites sont regroupées dans
`r17_process_observations_20261026.json`. Aucun nouveau routage n'est lancé
et R15 reste sur la Neo.

### Arrêt demandé et changement d'instrumentation

Le 26 octobre, l'utilisateur demande explicitement l'arrêt de R17. Le
processus 2794912 est identifié par PID, startticks, répertoire, commande et
SHA de l'exécutable, puis arrêté via son pidfd avec SIGTERM. Sa disparition
est confirmée. Le constructeur et le surveillant terminent avec `-15` ;
leur statut générique `ROUTING_FAILED` correspond ici à cette annulation,
pas à un échec naturel du routeur. Aucun FS/TR/SDF final n'était produit.
Preuve : `r17_cancelled_by_user_01/result.json`.

L'utilisateur approuve ensuite une observation locale par registres lus
sur AHB, sans GAO. Le développement isolé et ses limites sont décrits dans
`../local_capture_20261026/README.md`. R15 demeure chargé sur Neo.

## Outils et échecs conservés

La première tentative de synthèse a rencontré une licence locale expirée.
L'essai utilise ensuite le serveur flottant publié par Sipeed, dans un
répertoire de configuration propre au candidat :
[documentation Sipeed](https://wiki.sipeed.com/hardware/en/tang/tang-console/mega-console.html),
[guide Gowin SUG501E](https://cdn.gowinsemi.com.cn/SUG501E.pdf).
Les exécutables copiés sont identiques octet par octet ; la configuration
de l'installation et celle des autres projets ne sont pas modifiées.

La première compilation de simulation mappée manquait une primitive UDP
`mux2` dans l'extraction de bibliothèque : son journal reste dans
`mapped_50ms/`. La seconde utilise les UDP officielles et passe. Aucun de
ces deux échecs n'est masqué comme un résultat positif de circuit.

Les journaux `simulation.log`/`obj_dir` correspondent à l'ancien prototype
20 ms. Les preuves du candidat retenu sont `simulation_50ms.log`,
`obj_50ms/` et `mapped_50ms_r2/`.
