# Console commune Pro Dock / Tang Mega Neo Console 138K

Port commencé le 12 octobre 2026 depuis `b2b1ba8` (NEBULA Linux R17).
Le rapport d'essais est dans `TESTS/NEO_720P_20261012.md` ; ses résultats sur
carte doivent être distingués des simulations décrites ici.

La politique de conservation Pro Dock et les contrôles obligatoires des deux
profils sont décrits dans [COMPATIBILITE_CARTES.md](COMPATIBILITE_CARTES.md).
L'inventaire exhaustif commun/Pro Dock/Neo est dans
[INVENTAIRE_CARTES.md](INVENTAIRE_CARTES.md). Un build Neo ne qualifie jamais
implicitement une modification commune pour la Pro Dock.

## Référence DDR rétablie le 20 octobre 2026

Le constructeur Neo choisit désormais par défaut `neo-fifo-registers` :
**IP DDR3 5.9 originale, mémoire 300 MHz, interface/GPU 75 MHz**, avec les
deux FIFO CPU double horloge en bascules. Les vingt fichiers DDR communs
à la Pro Dock restent conformes à leur profil ; la substitution des FIFO
reste limitée à la copie de compilation Neo. La DDR6 et ses variantes de
fréquence sont conservées comme expériences à sélection explicite.

N38r0 est rechargé comme référence matérielle exacte, sans refaire son
placement. Le prétest mémoire/TARGET passe à nouveau. Son défaut 3D connu
et le constat sur les copies du propriétaire GPU dans le modèle post-PNR
restent ouverts : ce retour ne qualifie pas la console complète. Le mode
`--restore-ddr59-reference` du chargeur conserve la qualification `FAIL`,
vérifie le SHA exact, le constat d'audit connu et les preuves du prétest
historique, exige tous les timings positifs et les autres audits valides,
et interdit le démarrage de Linux. Le processeur reste arrêté et le
scanout désactivé pour la suite du diagnostic.

## Deux profils, un GPU et une interface Linux

| Élément | Mega Pro Dock | Mega Neo / Tang Console |
|---|---|---|
| FPGA | GW5AST-138B, FPG676 | GW5AST-138C, PG484 |
| Écran | LCD 800×480 | HDMI/DVI 1280×720 |
| Pixel | 35 MHz | 74,375 MHz |
| Totaux | 1193×533 | 1650×750 |
| Fréquence d'image théorique | 55,043 Hz | 60,101 Hz |
| CPU / AHB / interface DDR | 800 / 80 / 75 MHz | 800 / 80 / 75 MHz |
| Budget d'une ligne, cycles DDR | 2556 | 1663 |
| Jeu, rendu puis agrandissement ×2 | 400×240 | 640×360 |
| Terminal partagé | 50×15 caractères | 80×22 caractères |
| Terminal plein écran | 100×30 caractères | 160×45 caractères |
| Console hôte | SOFT-USB HS / CDC, 115200 bauds UART | SOFT-USB HS / CDC + BL616 à 2 Mbauds |

Les accélérateurs de rastérisation et de géométrie 3D sont communs. La Neo
conserve les 16 couches, les 64 sprites, les tuiles, les palettes, le RGB565,
le double tampon et les commandes matérielles existantes. Linux réserve
quatre couches au terminal et aux diagnostics ; les jeux disposent des douze
premières. Les surfaces du rastériseur restent limitées à 1024×512 : le rendu
640×360 est agrandi par le scanout, tandis que les couches et le terminal
peuvent utiliser les 1280×720 pixels de la sortie. Le 720p ne signifie donc
pas que toutes les passes 3D sont calculées en 1280×720.

Comme avant ce port, le pilote Linux autorise les commandes GPU 1 à 30 ;
les commandes de géométrie 31 à 34 utilisées par les démos bare-metal ne
sont pas encore exposées par ce pilote. Le moteur reste présent dans le
FPGA et couvert par les simulations de géométrie.

Le profil Neo utilise la DDR3 du module, sans dépendre de l'extension SDRAM.
Depuis N20, la gestion DDR commune reprend exactement les sources de la
**Pro Dock G22r0 validée sur carte** : référence directe 50 MHz, mémoire
300 MHz, interface 75 MHz, resets, pont CPU à FIFO double horloge et arbitre
CPU/scanout/blitter. Les vingt fichiers concernés sont identifiés par
`tang/boards/ddr_prodock.json` et vérifiés avant compilation par
`tools/check_ddr_profile.py`. Ce contrôle est aussi appliqué aux sources
figées lors de la qualification Neo. Les broches et banques restent celles
du module PG484 ; l'identité des sources ne dispense pas du contrôle de
timing et des essais mémoire physiques sur la Neo.

L'essai N27 ajoute une sélection explicite `--ddr-adapter neo-tagged` au
constructeur Neo. Elle remplace **uniquement dans la copie de compilation**
`ddr_ui_adapt.v` par la version figée L31r8 de l'analyseur : tag de tête en
bascules et réponse enregistrée. À cette étape, le profil par défaut était `prodock` et
le fichier commun à la Pro Dock n'est pas modifié. Les empreintes de cette
variante sont dans `tang/boards/neo/ddr_tagged.json` ; la sélection figée
`ddr_variant.json` est incluse au manifeste et contrôlée à la qualification.
Cette variante reste expérimentale tant que timing et essais matériels ne
sont pas validés. `check_ahb_ddr_cdc.py --neo-ddr` teste le trajet CPU complet
avec les deux arbitres et un modèle DDR natif 256 bits, vidéo inactive.

N31 ajoute `--ddr-adapter neo-tagged-split`, une variante séparée du même
adaptateur. Elle précalcule la limite de saturation depuis les pointeurs
courants, puis applique acceptation/retour sans faire retraverser leurs
incréments au signal READY. La capture des 128 bits de réponse ne dépend
plus de la présence d'une étiquette ; seuls VALID et END l'utilisent,
donc une réponse sans étiquette reste ignorée. La référence L31r8 importée
est conservée intacte. `ddr_tagged_split.json` enregistre la provenance et
l'empreinte de cette variante, toujours limitée à la copie de compilation.
Les tests avec files de 2 et 16 entrées, rotations, saturation, resets et
trajet CPU à horloges distinctes passent ; la validation physique reste
requise. Pour cette variante, ajouter `--split-control` aux deux bancs
`TESTS/test_neo_ddr_adapter.py` et `tools/check_ahb_ddr_cdc.py --neo-ddr`.

N32 revient explicitement à `--ddr-adapter prodock`, sans changer les
autres sources RTL, CST/SDC ou options 3/2/1 de N31, pour isoler le retrait
de l'adaptateur expérimental. Le trajet complet original est simulable
avec `tools/check_ahb_ddr_cdc.py --prodock-ddr --out DIR`. Les variantes
restent archivées pour comparaison, sans modification du socle Pro Dock.
N32 termine avec deux violations setup (−0,554 ns au pire, zéro hold).
Son essai SRAM, explicitement demandé malgré ces violations, reproduit la
corruption DDR avant Linux : 528/544 octets différents sur les deux
relectures JTAG de 4 096 octets, ILM sans erreur. Le diagnostic CPU confirme
la corruption et la commande GPU TARGET sans DMA expire également.
Le retrait du patch ne résout donc pas le défaut. N32 reste un diagnostic
non qualifié ; N32r1 réutilise sa netlist avec la seule réplication désactivée.

N33 isole ensuite le stockage des deux FIFO CPU/DDR : le profil
`--ddr-adapter neo-fifo-registers` remplace leurs quatre emplacements
100/64 bits par **656 bascules**, en conservant pointeurs Gray, resets,
flags, latence, IP DDR, adaptateur et arbitres. Le fichier partagé Pro Dock
reste intact. Les audits des netlists synthétisée et routée confirment
l'absence de RAM dans ces deux petites files ; les autres FIFO sont inchangées.
Sur carte, les deux séries ciblées passent de **976 erreurs / 3 168 lectures
avec N32 à zéro avec N33** ; les motifs CPU/JTAG de 4 Kio sont aussi exacts.
Cela désigne la réalisation de ces FIFO ou le routage associé, sans prouver
un erratum silicium. **N33 reste non qualifié** : quinze violations setup
sur le reset du blitter (−2,056 ns au pire, zéro hold) et commande GPU TARGET
sans achèvement visible. Linux n'a pas été démarré. Les résultats et limites
sont consignés dans `TESTS/neo_720p_20261012/n33_board_comparison.json`.

N34 ajoute `build_console_neo.py --gpu-debug`, une instrumentation limitée
aux copies Neo figées. À `0xe9005000`, une capture cohérente indépendante
de `cdc_word` expose les mots de commande, pointeurs, opcode, états et
resets des moteurs. Sur deux chargements SRAM de N34, TARGET arrive bien
(8 mots, wp=rp=8, opcode=22), mais deux sorties de reset restent observées
à zéro : `engine_resetn=9`, au lieu de 15. Les quatre drivers ont pourtant
les mêmes entrées dans les netlists avant/après routage. N34 échoue aussi
au timing (−2,448 ns) ; cette observation n'est pas une qualification.
`n34_reset_observations.json` conserve les captures et les connexions.
N34r1 réutilise la même netlist avec seulement les quatre distributions de
reset demandées en local via `route_console_neo.py --gpu-reset-local`.
Les quatre nets quittent effectivement les ressources globales. Sur deux
chargements SRAM, les resets valent alors 15, TARGET se termine et les
quatre remplissages RGB565 de 4 Kio sont tous relus exactement. Un
remplissage legacy avec sentinelles passe également. Le routage global
change aussi : cela établit une contre-expérience physique utile, sans
prouver à lui seul un erratum LW. **Le timing reste non conforme :
−5,815 ns, 1035 endpoints setup, zéro hold. Linux n'est pas lancé.**
La suite doit distribuer les resets avec moins de fanout et fermer le timing.
L'option expérimentale conserve les gardes de drivers connus et ne modifie
ni le RTL partagé ni le profil Pro Dock. Voir `n34r1_reset_routing.json`
et les résultats physiques dans `TESTS/neo_720p_20261012/`.

Après le diagnostic DDR L31r8 version 1, le chargeur console peut utiliser
`--after-analyser-ddr-test DIR` : il reconnaît l'ELF exact, impose un CPU
déjà arrêté dans la boucle de fin et compare son code ILM et ses résultats
DTCM avant programmation SRAM. Ce mode n'affaiblit pas la qualification
FPGA et ne remplace pas l'arrêt propre requis pour un Linux actif.

L'option expérimentale de référence DDR issue de la PLL, introduite en N8,
est retirée des nouvelles compilations. Les anciens builds figés gardent
leurs sources et restent contrôlables pour l'analyse historique.
La sortie numérique transporte l'image TMDS ; audio HDMI, EDID/DDC, HDCP et
modes vidéo automatiques ne sont pas implémentés dans cette version.
Le générateur 74,375 MHz reprend celui déjà utilisé par l'analyseur : il est
proche du 720p60 nominal 74,25 MHz, mais n'est pas exactement cette fréquence.

Depuis N10, la Neo intègre le même SOFT-USB2 High-Speed 480 Mbit/s que la
Pro Dock : PHY, contrôleur, corrections EP0, FIFO, séquenceurs de reset,
trace et port MSC. Les descripteurs identifient `MegaNeo Console`, série
`NEO00001`. Les broches sont vérifiées sur les schémas officiels 32001A/C.
Le BL616 reste disponible à 2 Mbauds ; ses octets et ceux de CDC sont
arbitrés avant sérialisation vers UART2. Ne pas utiliser deux shells pour
écrire simultanément des commandes : ils partagent le même terminal Linux.
Le test d'arbitrage vérifie néanmoins l'intégrité et l'ordre des octets.

Depuis N11, deux hôtes USB2 **low-speed 1,5 Mbit/s** distincts utilisent les
D+/D− des ports A1/A2. Michael a confirmé le modèle **081f:e401**. Le pilote
Linux expose deux périphériques evdev ; NEBULA jouable accepte ces entrées.
Ce ne sont pas des hôtes génériques : pas de hub, de full-speed 12 Mbit/s,
de parseur HID universel ni de clavier arbitraire dans cette version.
Le CRC16 des rapports est vérifié et une retransmission DATA0/DATA1 n'est
pas republiée ; perte du lien ou timeout relâchent les commandes. Les ports
et compteurs sont indépendants. Le MMIO `0xe9004000` offre une capture
cohérente du rapport complet à la lecture du STATUS de chaque port.
**Aucun contrôleur USB3 n'est intégré**, conformément à la demande.

Ces intégrations sont encore en validation FPGA : présence dans les sources
et simulation ne constituent pas une réussite sur carte. La SD est câblée
au contrôleur SPI AE350 ; son contrôle physique se fera sans écriture.

## Adaptations matérielles

- `tang/boards/neo/console_neo.v` réunit le même SoC AE350, la même DDR3 et les
  mêmes accélérateurs, avec l'interface HDMI et le relais UART de la Neo.
- `neo.cst` utilise les broches PG484C, les banques SSTL15 de la DDR et les
  quatre paires TMDS. Il ne remplace pas les contraintes Pro Dock.
- `neo.sdc` contraint les horloges et limite explicitement les trajets CDC.
  Les entrées série asynchrones et l'assertion des synchroniseurs de reset
  sont exemptées. Les contrôles de maintien entre domaines sans relation
  de phase sont exclus ; les bornes de propagation restent actives, y
  compris sur les bus des boîtes aux lettres. Les libérations de reset
  HDMI vers les OSER10 restent contrôlées.
- Le scanout élargit X de 10 à 11 bits et Y de 9 à 10 bits uniquement lorsque
  la résolution le nécessite. Les numéros de lignes, tags de tampon, indices
  de blocs RGB et RAM de ligne suivent ces paramètres.
- Une couche indexée non alignée peut demander 41 mots DDR pour une ligne de
  1280 pixels. Les mémoires intermédiaires ont été élargies pour conserver le
  dernier mot et éviter le retour au début après 1024 pixels.
- Les paramètres de chaque ligne sont capturés dans le domaine DDR sur la
  Neo avant le lancement des moteurs ; cela évite un large éventail de
  commandes combinatoires provenant de l'horloge pixel.
- Le RGB direct 720p utilise des lectures en vol, même sans couches. Les
  réponses restent ordonnées par l'arbitre DDR partagé.
- Les registres en lecture seule `GPU+0x70` et `GPU+0x74` donnent
  respectivement `(hauteur<<16)|largeur` et `(V_TOTAL<<16)|H_TOTAL`.

Les imports HDMI, PLL et UART sont figés dans `tang/boards/neo/vendor`.
`import.json` conserve les chemins et SHA-256 de provenance depuis le projet
voisin. Le noyau SVO conserve sa notice de licence de Clifford Wolf. Les
broches et l'architecture de carte ont été recoupées avec la documentation
[Sipeed Tang Console](https://wiki.sipeed.com/hardware/en/tang/tang-console/mega-console).
Les sources du projet analyseur ne sont pas modifiées.

## Linux et mémoire

`make -C linux BOARD=neo all` utilise `linux/build-neo`, `neo-linux.dts` et
les lanceurs `fw_console/build/linux_launch*_neo`. Le profil par défaut reste
`BOARD=prodock` et utilise ses répertoires habituels. La chaîne croisée
Bootlin existante est partagée ; les sources noyau, OpenSBI, musl et BusyBox
sont extraites et compilées séparément pour la Neo.

Le pilote compare les dimensions du device tree à celles du FPGA avant de
configurer l'affichage. L'ancien FPGA G22, dépourvu des nouveaux registres,
est accepté uniquement en 800×480. L'ABI 1 et les tailles des anciennes
structures ne changent pas. Le nouvel ioctl `PRODOCK_DISPLAY_GEOMETRY`
renvoie les dimensions, horloges, totaux et budget de ligne.

Les cellules du terminal sont stockées avec un pas de 160 caractères. Les
cartes de tuiles Neo font 256×128 entrées, sur deux banques ; les atlas de
police et toutes les cartes restent dans les deux Mio réservés au noyau à
`0x05e00000`. Le tableau de diagnostics historique 100×15 est centré dans la
partie basse 1280×360. Son calcul d'occupation utilise les 1663 cycles de la
Neo, pas le budget LCD de la Pro Dock.

NEBULA conserve sa simulation de jeu indépendante de l'écran. À l'ouverture
il lit les dimensions du pilote et ajuste les positions, effets, surfaces,
fonds étoilés et pas mémoire. Les sprites gardent leur taille matérielle,
avec leurs centres correctement transformés. Le fond est redimensionné une
fois au chargement, les images sont ensuite produites par le GPU.

La mémoire NEBULA reste limitée à 14 Mio depuis `0x00800000`, sous le
framebuffer de secours situé à `0x01700000`. Le profil Neo réserve trois
pages de 2 Mio et utilise au total 14 225 792 octets. Les atlas de son HUD
réservent les 1024 glyphes réellement référencés, ce qui laisse tenir les
fonds élargis dans cette limite. Les ressources Pro Dock conservent leur
organisation antérieure et leurs images de référence.

## Construction et essai temporaire

```sh
python3 tools/build_console_neo.py --name console_neo_720p \
  --place 3 --route 2 --replicate 1
python3 tools/check_neo_timing.py tang/impl/console_neo_720p
make -C linux all BOARD=neo JOBS=4
make -C linux test BOARD=neo JOBS=4
```

Chaque compilation FPGA fige ses sources, son initialisation ITCM et leurs
empreintes dans son propre répertoire. `tools/route_console_neo.py` peut
réutiliser cette synthèse en vérifiant les empreintes ; il conserve le SDC
et les broches figés du parent, même si les sources de travail ont changé.
Seuls des candidats `INS_LOC` explicites peuvent changer le placement.
Les autres compilations Gowin ne
sont ni arrêtées ni remplacées.

Une compilation n'est qualifiée que lorsque les rapports complets ne
signalent aucune violation de timing et que les empreintes correspondent.
Le contrôle vérifie aussi les deux régressions de synthèse DSP déjà connues :
absorption de registres COPY à validations indépendantes et mélange
d'horloges dans le scanout. Ces audits structurels complètent les simulations
et les essais physiques ; ils ne prouvent pas une équivalence générale.
Le contrôle écrit `qualification.json`, requis par le chargeur.

```sh
python3 tools/neo/load_linux.py --build tang/impl/console_neo_720p \
  --out TESTS/neo_720p_20261012/board_720p
```

Ce chargeur vise le programmeur Sipeed série **2025041420** et l'ESP-Prog
identifié par **Dual RS232-HS**, car les deux emploient le même VID/PID.
Il synchronise l'ancien Linux, démonte `/mnt/sd`, vérifie qu'aucune partition
MMC ne reste montée, puis charge uniquement la SRAM FPGA. Le firmware ITCM
attend en boucle dans la RAM de démarrage externe (4 Kio depuis N6),
distincte de l'ILM matérielle de 64 Kio utilisée par le lanceur.
Aucune écriture SD ni flash n'est effectuée. Le payload
Linux compact est transféré en DDR, puis le lanceur ILM vérifie son CRC
avant OpenSBI. La capture UART fonctionne pendant le transfert et le boot.
Avant le transfert complet, le chargeur écrit un motif de 4 Kio (valeurs
fixes, bits glissants et pseudo-aléatoires) puis le vérifie deux fois en ILM
et aux deux extrémités du transport DDR. Le payload entier est ensuite
vérifié par JTAG avant exécution. Un échec interrompt le chargement.
`--already-programmed` sert à recharger le logiciel après ce premier essai.
`--recover-failed-load DOSSIER` permet de reconfigurer après l'échec de
transport ILM observé sur N18r2 : il exige son résultat archivé et vérifie
le PC, le niveau de privilège et l'instruction de boucle sur le processeur
avant le chargement SRAM. Il ne remplace pas l'arrêt propre d'un Linux actif.
Il accepte aussi un échec JTAG enregistré avant toute tentative de lancement :
les marqueurs du journal doivent confirmer cette étape et la lecture JTAG
doit retrouver le PC et les deux instructions exactes de la boucle d'attente
en RAM de démarrage. Un boot réussi ou un état inconnu est refusé. Cela
permet d'essayer le candidat suivant après un échec du contrôle DDR initial.

Console interactive, après fermeture des outils de test :

```sh
python3 -m serial.tools.miniterm \
  /dev/serial/by-id/usb-SIPEED_USB_Debugger_2025041420-if01-port0 2000000
```

Le CDC du port **SOFT-USB** est identifié par le numéro de série `NEO00001`
(VID/PID `359f:2011`). Il propose le même shell, à 115200 bauds côté UART ;
la liaison USB doit négocier 480 Mbit/s. Ce débit de bus ne représente pas
le débit de caractères du terminal. N'envoyer des commandes que depuis un
terminal à la fois, car le CDC et le BL616 pilotent le même shell.

Contrôle automatique, une fois Linux chargé et le terminal interactif fermé :

```sh
python3 tools/neo/check_usb.py --out TESTS/neo_720p_20261012/usb_board_720p
```

Ce test sélectionne exclusivement `NEO00001`, contrôle la vitesse via sysfs
et compare 200 réponses Linux avec des tailles et des découpages variables.
Il rejette l'écho de la ligne de commande comme preuve de réponse. Un
changement de périphérique ou une réénumération fait échouer le test.
L'échange traverse l'UART à 115200 ; ce n'est pas un benchmark bulk HS.

Les deux ports USB-A sont réservés aux manettes **081f:e401**. Le pilote
publie `Tang Neo gamepad 1` et `Tang Neo gamepad 2` dans evdev. Dans NEBULA,
la croix déplace le vaisseau, le bouton principal déclenche la nova,
START pause/reprend et SELECT change la disposition. Les deux manettes
peuvent contrôler le même joueur ; le jeu ne devient pas multijoueur.
Le mode `--demo` continue à jouer automatiquement.

```sh
prodockctl geometry
prodockctl layout split
nebula --demo --split
# Q pour quitter le jeu, F pour changer de vue en mode jouable
nebula
prodockctl layout console
```

L'analyseur en flash n'est pas remplacé. Un redémarrage électrique recharge
le contenu flash antérieur ; ce port n'installe pas encore de démarrage
permanent Neo depuis la SD et ne convertit pas ses anciens fichiers de démo
bare-metal 800×480 en programmes 720p.


## Diagnostic de distribution du reset (15 octobre 2026)

N35 répartit les resets graphiques en douze copies de même latence, dans les
seules sources figées Neo. Simulation des resets en cours de calcul et
comparaison cycle par cycle avec N34 passent. Timing : −3,034 ns/319 setup,
0 hold, contre −5,815 ns/1035 setup pour N34r1. Sur carte, les douze copies
sont libérées, mais mrst[1] est maintenant observé à 0 ; il utilise une LW
et maintient la FIFO de commandes en reset. N35r1 reroute la même netlist
avec ce signal explicitement demandé local ; résultat encore en attente.

Mise à jour du 16 octobre : aucun rapport final N35r1 n'est disponible.
L'absence des anciens PID depuis le bac à sable ne permet pas d'affirmer
que le processus hôte est arrêté. Aucun résultat de ce build n'est retenu.

Le reproducteur autonome **sans DDR ni FIFO ni GPU** passe timing. Premier
A/B : reset sur LW bloqué à 0 (955 trames/60 époques), reset sur PRIMARY
libéré avec zéro erreur (954 trames/60 époques). Sources et rapports dans
[le dossier de reproduction](../TESTS/neo_720p_20261012/reset_reproducer/README.md).
Les répétitions sans donnée UART restent non concluantes. Ce résultat
isole un défaut de distribution sur la Neo testée, sans prouver encore
un erratum matériel ni départager les versions de Gowin. Le routage
réel est contrôlé, car LOCAL_CLOCK n'aboutit pas toujours à des fils locaux.


N36r0 ajoute la capture du payload lorsque le slot DDR est vide, en gardant
les cycles de validation/acceptation identiques. La comparaison RTL et les
resets en cours de calcul passent. Deux chargements SRAM passent TARGET
et huit remplissages de 4096 octets sont exacts ; 1120 lectures DDR ciblées
sans erreur. Tous les resets observés sont libérés. **Timing encore FAIL :
−4,866 ns, 97 setup, 0 hold**, principalement la sonde de diagnostic, puis
DDR init et géométrie. État après ces essais : N36r0 en SRAM, CPU arrêté. Point de reprise historique :
`TESTS/neo_720p_20261012/board_n36r0_reload2`; état complet dans
`TESTS/neo_720p_20261012/n36_progress.json`. Linux n'est pas lancé.

## Timing conforme et vérification 3D (16 octobre 2026)

N37 pipeline la lecture de la sonde Neo (un wait AHB explicite). N38 ajoute
des flags d'occupation dans la file de scanout et conserve localement la
phase de lecture du shader. Les copies figées seules portent les changements
du GPU commun ; ni l'IP DDR ni l'arbitre de la Pro Dock ne sont modifiés.
Équivalence sur 1,9 million de cycles DDR, 3 Mio de pixels/guards exacts en
simulation, sept resets en plein calcul. **N38r0 : zéro violation setup/hold,
setup minimal +0,259 ns, hold minimal +0,129 ns**, audits FIFO/DSP/resets PASS.

Cependant, les nouveaux tests matériels de rendu révèlent encore un défaut :
N36 compte correctement les triangles mais produit 31 577 octets couleur
incorrects ; N38 termine les 105 commandes, compte les 402 sommets, mais
produit 15 triangles au lieu de 61. Même un maillage de neuf sommets échoue
sur N38 : un triangle au lieu de cinq, erreurs couleur et profondeur,
textures inchangées. Le timing conforme ne suffit donc pas à qualifier le GPU.

N38r1 reprend exactement la netlist N38 en demandant quatre contrôles GPU
hors LW : capture des coordonnées, reset des tampons pixels, capture des
commandes pixels, reset scanout. Les fonctions des drivers synthétisés
sont contrôlées avant d'ajouter les contraintes. Ce routage est refusé :
un autre reset GPU passe sur LW. N38r2 (Gowin V1.9.12.03) échoue au timing ;
N38r3 passe timing mais les demandes PRIMARY restent physiquement sur LW.
Aucune de ces trois variantes n'a été chargée.
**État après les essais N38 : N38r0 en SRAM, CPU au parking, Linux non lancé, aucune
écriture SD/flash ; point de reprise `board_n38r0`.** Les preuves détaillées
sont dans `TESTS/NEO_720P_20261012.md`, l'état actualisé dans
`TESTS/neo_720p_20261012/n36_progress.json` (nom historique conservé).

Trois essais par face isolent les symptômes : le triangle intérieur garde
une profondeur exacte mais présente des débordements couleur ; les deux
faces nécessitant du clipping disparaissent, sans erreur signalée. N39
précharge les opérandes privés de clipping et conserve le reset des masques
pixels sans remettre à zéro les 512 bits de payload. L'équivalence des cycles,
masques et octets DDR actifs passe sur 28 583 transactions ; le modèle
indépendant confirme les 3 Mio et sept resets pendant le calcul. N39r0 est
compilé avec 15 violations setup (−1,172 ns), sans hold et avec audits structurels
conformes. Son chargement diagnostic passe mémoire/TARGET, puis bloque sur CLEAR
avant le test des triangles. Tous les resets observés sont libérés. Le nouveau
routage a placé sur LW `v1_pending`, qui commande encore les données du slot DDR.

N40 retire cet enable : les producteurs conservent déjà leurs données jusqu'à
l'acquittement enregistré. L'échantillonnage continu passe l'équivalence stricte
sur 28 583 transactions et les tests indépendants de pixels/resets. N40r0 route.
N39r1, même netlist avec place 4, dégrade le timing (−2,225 ns / 92 setup)
et reproduit exactement le blocage CLEAR, après vérification des 3 Mio initiaux.
**État après N39 : N39r1 en SRAM, CPU arrêté, GPU bloqué sur CLEAR.**


N40r0 retire bien `v1_pending` de LW, mais le maillage physique est encore
incorrect : les onze commandes sont rejetées, aucun pixel n’est écrit. Le
chargeur détecte désormais ce cas en comparant aussi les compteurs de rejet,
au lieu de se contenter de la fin de commande. Cette garde a échoué comme
attendu sur N40, avant tout transfert Linux. Le timing reste FAIL (−2,083 ns,
112 setup, zéro hold). N40r2 reprend la même netlist avec 137 contraintes
locales sur les contrôles graphiques largement distribués ; résultat en attente.
**État courant : N40r0 en SRAM, CPU arrêté, GPU idle après rejet, Linux non lancé.**
Reprise : `TESTS/neo_720p_20261012/board_n40r0_rejection_guard`.


Mise à jour du 16 octobre au soir : la reproduction autonome est maintenant
lisible par JTAG et répétée sur deux IDE, sans DDR/FIFO/GPU. 6 000 instantanés
confirment le contraste auto/local ; un candidat fonctionnel reste pourtant
étiqueté LW avec 1.9.12.03. Une mention LW seule n’est donc pas une preuve de
panne. Voir `TESTS/neo_720p_20261012/reset_reproducer/JTAG_20261016.md`.

N40r2/N41r0 restent non qualifiés ; leurs essais explicites n’atteignent pas le
TAP AE350, sans mesure GPU possible. **État courant : N38r0 restauré en SRAM,
précontrôle mémoire/TARGET strict PASS, CPU arrêté, scanout désactivé, Linux
non lancé. Le rendu N38 reste incorrect : ce n’est pas une console qualifiée.**
Reprise : `TESTS/neo_720p_20261012/board_n38r0_after_n40r2`.
N41r1_newide est en cours, même netlist/CST/SDC que N41r0, moteur 1.9.12.03.

### Outil Gowin retenu pour la suite — 16 octobre 2026

À la demande de l’utilisateur, **V1.9.12.03**, la version la plus récente
installée dans `/home/michael/gowin/IDE`, devient le choix par défaut pour
les nouvelles synthèses et les nouveaux placements/routages des deux cartes.
La sélection commune se trouve dans `tools/gowin_toolchain.py` ; les scripts
de simulation prennent également leur bibliothèque de primitives dans cette
installation. Le correctif de bibliothèque FreeType est appliqué uniquement
aux processus de compilation, sans modifier l’installation Gowin.

Les anciens résultats et instantanés restent associés à leur outil d’origine.
N41r1_newide est une comparaison de **routage** : sa netlist a déjà été
synthétisée avec V1.9.12. Une prochaine synthèse complète utilisera V1.9.12.03.
Le changement d’outil ne vaut pas validation du timing ni du rendu matériel.

À 23:06, N41r1_newide a terminé en échec : setup −2,730 ns, recovery
−5,996 ns, aucune violation hold. Il n’a pas été chargé. L’analyse distingue
les passages USB/AHB, les resets HDMI et les chemins internes GPU/AHB.
`console_neo_n42syn` reprend la synthèse complète avec V1.9.12.03 ; la
carte reste sur N38r0, CPU arrêté. Le problème matériel n’est pas résolu.

N42syn a passé les audits de synthèse ; N42r0 est en routage. L’essai
suivant N43 utilise explicitement l’IP **DDR3 6.0**, générée par le flux Tcl
officiel de V1.9.12.03 pour la Neo PG484C. Le profil optionnel
`neo-ddr6-fifo-registers` conserve les FIFO CPU en registres et protège
l’adaptateur, l’arbitrage et les PLL de référence par leurs empreintes.
Les 40 ports DDR restent identiques ; tous les anciens paramètres mémoire
sont conservés, avec les quatre compléments et le choix BSRAM émis par le
nouveau générateur. **92 tests Python passent ; aucune validation matérielle
DDR6 à ce stade.** Voir la fin de `TESTS/NEO_720P_20261012.md`.
