# Observation locale Neo, sans GAO

R17 est arrêté à la demande de l'utilisateur. Le retour `-15` de son
constructeur est une annulation par SIGTERM, pas un échec naturel du routeur.
Preuve : `../reset_sequence_20261025/r17_cancelled_by_user_01/result.json`.
La carte conserve R15 ; aucune opération matérielle dans cette préparation.

Le candidat prévu N56r18 conserve l'application **mappée R15**, DDR 5.9 à
300 MHz, reset 50 ms, PLL et contraintes physiques. Deux petits modules
de diagnostic sont synthétisés séparément et insérés dans cette copie.
Les nets applicatifs gardent leurs drivers et leurs charges préexistantes ;
les sondes ajoutent des charges, donc le placement et les routes changeront.
La configuration GAO est retirée. Les sources communes restent intactes.

`neo_capture_local` est placé hiérarchiquement dans le moteur pixels. Il
échantillonne les **nets des broches réelles** des FF packet, après résolution
des alias optimisés : D opcode[31:24], Q opcode[31:24], CE, reset actif haut,
start, IDLE, DECODE_WAIT, DECODE, BAD, done. Un échantillon est pris au front
où start est haut, le second au front suivant. Ce dernier observe la valeur
Q résultant du premier front, avant une éventuelle nouvelle écriture.

Le reset du moteur est une donnée de la sonde. Seuls le reset système et un
réarmement explicite effacent la capture ; un reset du moteur ne masque pas
la preuve. Sans start, la sonde reste armée et le logiciel peut demander un
instantané vide. Aucun timeout interne trop court ne précède une commande JTAG.

Chaque échantillon fait 24 bits : D[7:0], Q[15:8], CE[16], RESET[17],
START[18], IDLE[19], DECODE_WAIT[20], DECODE[21], BAD[22], DONE[23].
Le rapport 64 bits contient échantillon au front[23:0], après[47:24],
validités[49:48], complet[50], armé[51], reset vu[52], CE vu[53],
epoch d'armement[54], réservé[55], signature C1[63:56].

Lecture à travers le JTAG AE350 et la fenêtre AHB existante `0xe9005000` :

| Offset | Lecture | Écriture de 1 |
|---|---|---|
| 80 | signature NCP1 | aucune |
| 84 | bits 0 arm busy, 1 snapshot busy, 2 ready, 3 snapshot valid, 4 snapshot epoch, 5 arm epoch, 6 rejet | armer |
| 88 | compteur armements acceptés | demander un instantané |
| 8c | numéro d'instantané terminé | aucune |
| 90 / 94 | rapport bas / haut, figé | aucune |
| 98 | compteur de battements GPU vus par AHB | aucune |

Les requêtes et acquittements passent par deux FF. Le rapport GPU `held`
reste figé jusqu'à la demande suivante ; après ACK synchronisé, le côté AHB
attend deux cycles supplémentaires avant sa copie. Un seul échange est
autorisé. Les clocks peuvent s'arrêter sans bloquer le bus AHB ; le logiciel
doit borner ses attentes. Le délai physique held→shadow reste à contrôler
après routage, même si les groupes d'horloges sont déclarés asynchrones.

Validation prévue avant routage : fautes D/CE/reset/Q injectées, absence de
start, relecture stable, commandes occupées, réarmement, reset en échange,
horloges de phases/fréquences différentes et arrêt/reprise. Puis simulation
des modules synthétisés et de l'intégration mappée, conservation exacte des
modules applicatifs par annulation du patch, campagne des deux profils.
Le timing et le matériel sont des validations distinctes. Aucun bitstream
de ce candidat n'est encore produit ni chargé.

## Résultats locaux et procédure de lecture

`rtl_04/` et `mapped_01/` passent chacun 158 contrôles, incluant le reset
pendant l'arrêt de l'une ou l'autre horloge. Le côté AHB a été corrigé avant
sa première synthèse pour affirmer son reset sans dépendre de son horloge.
Les premières préparations et simulations restent archivées ; elles ne
remplacent pas les dernières preuves. Le banc refuse les valeurs inconnues
et vérifie epochs, compteurs, indicateurs CE/reset et ancienne commande 04.

`integration_01/` exerce 22 commandes avant/après reset dans les 13 modules
mappés concernés. Les 16 commandes transmises aux pixels sont capturées
avec leur opcode exact ; les autres ne fabriquent pas une capture. Aucune
requête DDR n'est émise par ce test de configuration. La netlist complète
est liée au résultat par SHA-256.

Après reset, attendre la signature NCP1 et ready avant toute opération :
les deux premiers fronts AHB correspondent à la garde de sortie de reset
de l'observateur, et une lecture immédiate de la nouvelle fenêtre peut
retourner zéro. La procédure JTAG doit borner cette attente. Armer, vérifier
la fin de busy et l'incrément du compteur d'armement, puis envoyer TARGET.
Après terminaison, demander un instantané, attendre son acquittement et
l'incrément du numéro de snapshot, puis lire les deux mots figés. Contrôler
signature, epoch et validités avec `decode_capture.py` ; snapshot_valid seul
ne signifie pas qu'un événement a été capturé.

La sonde ne couvre que les huit bits d'opcode. Un résultat cohérent ne
qualifie ni les 24 bits bas de l'en-tête ni le payload ni l'ensemble du GPU.
Une capture modifie les charges et le routage : le défaut R15 doit être
reproduit sur ce candidat avant d'en tirer une conclusion matérielle.

## Première lecture Gowin et candidat en placement

`console_neo_n56r18_local_capture` est refusé par le lecteur de netlist
PA2060, avant placement : neuf raccordements de bus ajoutés omettaient les
plages explicites. Le format est corrigé dans une copie distincte
`console_neo_n56r18r1_local_capture`, en conservant l'échec initial. Les
plages correspondent exactement aux déclarations, et leur suppression
restitue octet pour octet la netlist précédente. Il n'y a pas de changement
logique, de nouvelle synthèse, ni de modification des contraintes.

`integration_format_02/` repasse les 22 commandes sur la copie corrigée ;
les 22 rapports de l'observateur sont identiques à ceux du premier test.
Le contrôle initial du formateur comparait aussi des bus homonymes d'autres
modules et a été corrigé pour examiner le module concerné ; l'essai
`integration_format_01` avait démarré avant que cette préparation aboutisse
et n'avait donc pas de netlist à lire. Ces erreurs d'outillage ne sont pas
présentées comme des échecs du GPU.

La lecture Gowin de R18r1 réussit, les contraintes sont acceptées et le
placement démarre (PID3056247). Les deux helpers synthétisés totalisent
344 FF et 568 LUT, sans BSRAM ni DSP ; ce décompte précède l'optimisation
physique complète. Aucune carte n'est chargée automatiquement. L'état,
les empreintes et les validations encore requises sont dans `handoff.json`.

## R18r1 terminé et chargé le 26 octobre

Le routage se termine à 10:06:31, retour 0, avec le FS
`tang/impl/console_neo_n56r18r1_local_capture/impl/pnr/console_neo.fs`, SHA-256
`f713c85b2dbd8c3d2010e1f34c1af2c88a6cb9f1880ee91c8e706c5f2abf46e1`.
Le timing global reste **FAIL** : setup −2,715 ns (63 endpoints), hold
+0,124 ns (aucun endpoint en violation), recovery −0,537 ns, removal
+0,331 ns. Ce candidat n'est pas une version qualifiée du GPU.

`postroute_01/result.json` et `capture_paths_01.json` vérifient la netlist
physique : seules les 32 sorties des anciens registres HRDATA sont renommées
avant le multiplexeur de la nouvelle fenêtre ; les autres cellules et
paramètres applicatifs sont conservés. Les 914 nouvelles cellules sont
limitées aux deux observateurs. Les 344 FF d'observation utilisent leurs
domaines prévus, dont les 48 FF des deux échantillons.

Les 58 bits non constants du rapport traversent held→shadow en au plus
1,739 ns, clock-to-Q inclus ; les six autres bits sont constants nuls.
Le contrôle conservateur des cônes D/CE des échantillons, avec délais SDF
et skew entre FF depuis la même origine GPU, donne une borne setup de
+5,519 ns. Ce calcul local ne remplace pas la STA globale. Les violations
recovery du reset asynchrone sont conservées ; le protocole attend ready,
le battement GPU et un armement explicite longtemps après le démarrage.

`board_trial_01` s'arrête avant tout accès JTAG et avant programmation :
libusb_init est bloqué par le bac à sable. `board_trial_02`, autorisé hors
du bac à sable, vérifie les deux appareils Neo, le CPU garé et l'état R15,
charge R18r1 en SRAM puis envoie une configuration TARGET. Aucun code CPU
n'est exécuté par le script et aucune écriture DDR, SD ou flash n'est demandée.
La caméra montre les bandes de la mire ; la somme interne est exacte.

### Résultat matériel reproductible

La première capture puis les huit captures de `repeat_capture_01` donnent
le même résultat pour TARGET (0x16) et INVALIDATE (0x1e) :

| Signal au front déclencheur | Mesure |
|---|---|
| Opcode aux entrées D réelles | 0x16 ou 0x1e, conforme à la commande |
| START / IDLE | 1 / 1 |
| Reset actif haut | 0 |
| CE de capture packet | 0 |
| Opcode Q au front suivant | 0 |
| Erreur de transport / perte de file | aucun incrément |
| Rejet V1 | +1 par commande |

Les armements et snapshots avancent, leurs epochs alternent, les rapports
figés sont lus trois fois identiques et le battement GPU progresse.
La règle de la bascule est cohérente avec CE=0 : Q conserve zéro. Le défaut
initial R15 est donc reproduit sur le candidat instrumenté. Le rapport
SDF/VO décrit pourtant ce CE comme la sortie de LUT2 INIT=8, soit
`shader_start & state[0]`. La discordance mesurée est localisée à ce
chemin d'activation ; elle ne prouve pas encore un erratum général de LW,
la cause électrique interne ou la correction de tous les défauts vidéo.

La carte reste sur **R18r1**, CPU arrêté, mire interne, GPU done=9 et
rejected V1=9, observer arm_count=9 et sequence=9. Pas de Linux.
Ne pas réutiliser l'ancien garde R15 done=2 pour une prochaine expérience.
La Pro Dock reste indépendante sur G22r0 avec LUMA OP2 ; elle n'a pas été touchée.

## R19 : comparaison limitée au routage du CE observé

Le candidat `console_neo_n56r19_capture_ce_local` conserve la netlist R18r1
byte-identique (SHA `dfac41d80eecaa0b6a3c152d36d8fcdb902060cecbd450647ede445d1c8004b6`),
les sondes, DDR 5.9/300 MHz, PLL, reset 50 ms, SDC et options PnR.
La seule nouvelle contrainte physique est :

```
CLOCK_LOC "u_accel/u_v1/u_pixels/n37565_3" LOCAL_CLOCK;
```

SUG1018-1.7E §2.7, pages imprimées 14–15, décrit explicitement LOCAL_CLOCK
comme l'utilisation du routage local non-clock. Le PDF de l'installation
est identifié par SHA dans `experiment.json`, sa transcription est
`physical_constraints.txt`. Ce document ne dit pas que LW est défectueux.
L'expérience teste une hypothèse née des captures, sans modification RTL.
Le placement entier peut néanmoins changer : vérifier le routage effectif
du CE, les délais des sondes, puis rejouer exactement les captures avant
de conclure. Aucun chargement automatique n'est prévu.

La nouvelle campagne `TESTS/dual_board/20261026_neo_capture_ce_r19` passe
les 11 groupes ; elle est distincte de cette comparaison physique et
des prochains essais matériels. Les accélérations FPGA proposées pour
augmenter les FPS attendent, à la demande de l'utilisateur, que la Neo
fonctionne. Aucun changement de la référence Pro Dock n'est autorisé par
ce diagnostic.

## R19 terminé, chargé et observé le 26 octobre

Le routage termine en 27 minutes, retour 0. Le bitstream chargé en SRAM est
`console_neo_n56r19_capture_ce_local/impl/pnr/console_neo.fs`, SHA-256
`1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c`.
Le timing global reste **FAIL** : setup −2,888 ns, hold +0,124 ns,
recovery −0,239 ns et removal +0,274 ns.

`r19_postroute_01/result.json` compare les cellules, connexions et paramètres
avec R18r1 : aucune cellule ajoutée, retirée ou modifiée. Le CE observé
n'utilise plus LW. Les routes physiques d'autres signaux ont néanmoins
changé, dont `u_accel/u_v1/n59467_5` désormais sur LW ; la comparaison ne
permet pas d'attribuer tout comportement différent au seul CE.
`r19_capture_paths_01.json` retrouve les 344 FF des observateurs, dont les
48 FF d'échantillonnage, avec une borne locale setup de +5,185 ns et un
trajet held→shadow maximal de 2,415 ns. Ce contrôle ne qualifie pas le
timing global.

### Capture de commandes : différence mesurée sur carte

`r19_board_trial_01/result.json` conserve les neuf captures de TARGET et
INVALIDATE : **CE=1, opcode Q correct au front suivant, aucun rejet V1**.
Sur R18r1, les neuf mêmes commandes donnaient CE=0, Q=0 et un rejet chacune.
L'essai R19 montre donc la disparition du défaut de capture observé, sans
prouver un erratum général de LW ni le fonctionnement complet du GPU.
Il n'inclut pas encore une endurance ni plusieurs rechargements R19.

### CLEAR : blocage distinct conservé, sans remise à zéro

`r19_memory_01/` prépare puis vérifie par le CPU trois régions DDR, chacune
entourée de gardes de 32 octets : couleur 4 KiB à `0x12000000`, profondeur
4 KiB à `0x12010000`, source COPY 16 KiB à `0x12020000`. TARGET passe
(done=10, aucun rejet), mais CLEAR couleur+profondeur 128×16 ne termine pas.
Le test reste **FAIL** ; COPY et les comparaisons de rendu prévues n'ont
pas été exécutés. Le message OpenOCD d'absence de working area est suivi
de la vérification mémoire réussie ; il n'est pas identifié comme cause
du blocage GPU.

`r19_clear_observe_01/result.json` lit cet état conservé sans reset, nouvelle
commande, écriture DDR ni reprise du CPU. Trois snapshots cohérents donnent :

- 88 mots envoyés et reçus, pointeurs du blitter wp=rp=88 ; file vide ;
- aucun compteur d'erreur ou de perte, done=10 et busy=1 ;
- resets moteur/enfants relâchés ; blitter en M_SETUP, ext_active=1 ;
- commande active CLEAR (0x1c), attente de fin du moteur étendu ;
- scanout désactivé, aucune requête scanout, arbitre prêt côté scanout.

Les trois lectures des en-têtes bruts géométrie/pixels donnent `0x1c000000`.
Ces registres utilisent une synchronisation par bit, non un snapshot atomique :
leur stabilité dans cet état bloqué complète les mesures, sans remplacer
une capture synchrone. Le nouvel observateur NCP n'a pas été réarmé avant
CLEAR : son dernier rapport (arm_count=sequence=9) reste celui d'INVALIDATE
et ne décrit pas la transaction CLEAR.

Les **24 768 octets** des trois régions, gardes comprises, sont relus
exactement identiques aux données CPU initiales. Aucun demi-mot couleur
ou profondeur n'a été changé. Le CPU accède donc encore à ces régions
pendant le blocage ; cela ne prouve pas que la voie GPU→DDR fonctionne,
ni que le GPU n'a écrit nulle part ailleurs.

Les sondes présentes ne publient ni l'état interne des pixels ni le couple
VALID/READY du port GPU. Le point précis d'arrêt entre décodage de CLEAR,
émission de la requête et acquittement mémoire reste à établir. Ne pas
conclure à un manque de débit DDR ou contraindre d'autres réseaux sur cette
seule observation. Aucun nouveau routage n'a été lancé après ce constat.

État laissé : **Neo R19, CPU arrêté à 0x80000004, mire interne, framebuffer
désactivé, CLEAR toujours occupé, done=10**. Les snapshots GPU sont désormais
au numéro 3 ; l'observateur NCP reste à 9. La Pro Dock n'a pas été touchée.
Linux, rendu GPU complet, framebuffer HDMI, USB/SD et jeu restent non
qualifiés sur R19 ; les améliorations FPGA destinées aux FPS attendent.

## Isolation CLEAR et observation R20r1

`r19_clear_isolate_01/` recharge **le même bitstream R19**, sans compilation,
après conservation des captures précédentes. Les données sont initialisées
et vérifiées par le CPU avant les commandes. Le résultat est :

| Commande | Termine | Mémoire relue |
|---|---|---|
| TARGET 128×16 | oui | inchangée |
| Blitter historique, remplissage 32 octets | oui | 32 octets exacts, voisins préservés |
| CLEAR avec flags=0 | oui | inchangée |
| CLEAR de rectangle vide | oui | inchangée |
| CLEAR couleur de 16×1 pixels | **non** | aucun des 32 octets attendus n'est changé |

Les quatre commandes V1 ont chacune une capture explicite NCP : CE=1 et
opcode Q correct, aucun compteur de rejet/perte ne progresse. Le défaut
nécessite donc ici une commande d'écriture effective du moteur étendu,
et non une grande surface, une lecture de texture ou une concurrence avec
le scanout. L'ancien blitter emprunte le même arbitre/contrôleur DDR, mais
pas le même étage de requête que le moteur V1 : son succès ne qualifie pas
cet étage. Il n'est pas encore possible de dire si la requête native est
absente ou si son acquittement est perdu.

Le témoin historique écrit à `0x00800020`, tandis que CLEAR vise
`0x12000000` : ce n'est pas encore une comparaison des deux moteurs à
la même adresse. La région haute est vérifiée par le CPU, mais une
différence de calcul ou de transport d'adresse GPU reste à examiner.
Le nouvel observateur publie précisément l'adresse du slot V1 ; selon
son résultat, un témoin des deux moteurs à la même adresse pourra
compléter l'isolation sans changer de bitstream.

La carte reste sur R19 après cet essai, CPU arrêté, mire interne,
**busy=1, done=4, rejected=0, NCP arm/seq=4, snapshot GPU=5**. L'ancre
done=10 de l'essai précédent n'est plus courante.

Le candidat **R20** réaffecte 128 entrées DATA des registres de snapshot
cohérent déjà présents. Aucun registre, LUT ou nouvelle fonction applicative
n'est ajouté dans la netlist d'entrée ; seuls des fils et ports de diagnostic
changent. La source RTL, DDR 5.9/300 MHz, le reset 50 ms, les PLL, CST/SDC
et options PnR restent ceux de R19. Le manifeste `observation.json` décrit
les écarts entre le RTL archivé et la netlist de diagnostic qui fait autorité.

- Mot 2 : signature `0x4d20`, VALID natif, sélection V1, requête en attente,
  READY de l'arbitre, acquittement enregistré, D/reset de la requête,
  CE de sa charge utile, autres demandeurs et fin V1.
- Mots 4/5 : les 58 bits de la FSM pixels, D/CE/reset de la vraie bascule
  `native_valid`, flags de CLEAR et résultat du validateur.
- Mot 6 : signature `0xa` et adresse en mots de la requête mémorisée.
- Les autres mots conservent done, resets, pointeurs/opcode du blitter
  et en-tête de commande. Les compteurs d'erreur restent lisibles par les CSR.

Gowin refuse les deux `assign` vectoriels du premier R20 avec PA2097,
**avant placement**. Ce résultat reste archivé dans le build R20. R20r1
les développe en 80 alias scalaires, sans changement d'ordre ni de source
des bits ; l'opération inverse restitue exactement R20. Gowin lit alors
la netlist et les contraintes et démarre le placement.

R20 et R20r1 passent chacun les 22 configurations sur primitives officielles.
Les deux simulations CLEAR vérifient chacune **49 152 demi-mots**, **532
bursts** et **465 cycles de pause**, y compris masques partiels, couleur/Z,
rectangle vide, flags nuls et reset. Les FSM et les D/CE/reset observés sont
comparés aux vraies broches des primitives. L'étage d'attente mémoire de ce
banc est un modèle RTL ; le test ne qualifie pas l'arbitre routé ni le PHY DDR.
Les 11 groupes complets repassent dans
`TESTS/dual_board/20261026_r20r1_scalar_observer/`.

Le routage R20r1 est lancé avec le PID 3277536. Il faut encore vérifier
les sorties physiques, les délais des chemins d'observation et reproduire
le même blocage sur carte avant d'interpréter le nouveau snapshot. Un
changement de routage dû aux charges d'observation pourrait modifier le
phénomène ; aucun correctif fonctionnel n'est revendiqué par ce candidat.

### Vérification des équations du chemin de requête

`handshake_truth_proof.json` compare les LUT de la netlist R19 aux équations
RTL attendues, par tables de vérité exhaustives. L'émission `native_issue`
est équivalente pour les 4 194 304 combinaisons de ses 22 entrées ; le
maintien de `native_valid` pour 2 048 combinaisons ; la requête mémorisée
`v1_pending` pour 512 ; l'acquittement `v1_accepted` pour quatre. Le signal
`native_issue` n'est abstrait dans le deuxième contrôle qu'après sa preuve
séparée. Aucune hypothèse one-hot ne restreint les entrées.

Cette preuve suppose le reset inactif et le comportement D/CE documenté
des bascules. Elle ne couvre ni les délais, ni la distribution physique
des signaux, ni les données/adresses de la requête complète. Elle écarte une
différence booléenne dans ces quatre fonctions ; elle ne qualifie pas le GPU.
Les deux tentatives symboliques antérieures, interrompues sans conclusion,
sont conservées dans `handshake_boolean_attempt_01/` et `_02/`. La preuve
achevée est celle de `check_handshake_truth.py`.

## Fin de R20r1 et contrôle à adresse identique

Le routage R20r1 se termine en échec après **1 h 40 min 22 s**, dont
1 h 29 min 48 s de routage : `PR0004`, **120 réseaux non routés**.
Les rapports textuels donnent ce total sans nommer les réseaux concernés.
Leur seule présence ne permet donc pas d'attribuer l'échec aux fils ajoutés
par l'observateur. Aucun bitstream R20r1 n'est produit ni chargé ; aucun
résultat de timing final ou d'observation matérielle n'est disponible.
Le suivi automatique s'arrête avant l'audit et sans accès carte.

Le contrôle `r19_same_address_01/` recharge ensuite exactement R19
(`1056917b…09917c`) en SRAM, sous verrou Neo, après vérification de la
carte et de son état arrêté. Il compare les deux moteurs à **0x00800020**,
sur les mêmes **32 octets** :

| Opération | Résultat |
|---|---|
| TARGET, couleur à 0x00800020, Z à 0x00810000 | accepté, done=1 |
| Ancien FILL, 32 octets de valeur 0xa6 | termine, done=2, données exactes |
| CLEAR sans flags | termine, done=3, mémoire inchangée |
| CLEAR de rectangle vide | termine, done=4, mémoire inchangée |
| CLEAR couleur, 16 pixels RGB565 de valeur 0x5aa5 | **bloqué**, busy=1, done=4 |

Après le dernier CLEAR, les 32 octets contiennent encore exactement les
`0xa6` du témoin historique. Les autres octets des 4 160 octets couleur,
la région Z et les gardes restent inchangés. Aucun compteur d'erreur ne
progresse ; les quatre captures d'opcode montrent CE=1 et Q correct.
Le blocage est donc reproduit aussi en zone basse, à l'adresse exacte où
l'autre moteur vient d'écrire. La différence entre les deux adresses de
l'essai antérieur n'est pas nécessaire pour reproduire ce blocage.
Cela ne prouve pas encore quelle adresse le moteur V1 présente réellement
au port natif, ni si sa requête est émise ou acquittée.

État courant après ce contrôle : **R19, CPU arrêté, mire interne,
framebuffer désactivé, busy=1, done=4, rejets=0, NCP arm/seq=4,
snapshot GPU=5** ; TARGET couleur=0x00800020 et Z=0x00810000.
Le bitstream, les sources communes, la Pro Dock, la SD et la flash ne sont
pas modifiés. Aucun nouveau routage n'est lancé. Les 11 régressions
communes sont encore courantes, vérifiées par le contrôle de construction.
L'observation des signaux VALID/pending/READY/acquittement reste à rendre
routable avant de poursuivre la mesure interne.
