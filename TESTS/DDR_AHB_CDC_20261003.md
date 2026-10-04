# Blocage CPU/DDR lors du retour du GPU complet — 3 octobre 2026

## Constat matériel et comparaison

Le GPU complet `gpu_l12_usb_hs33_lock2ms_r6` passe le timing rapporté
(minimum +0,138 ns) et l'équivalence graphique. Sur carte, deux chargements
passent chacun 20 tours USB, puis le troisième perd 65 octets d'un écho
de 256. Lors d'un autre chargement, les échos passent mais le test DDR
s'arrête après `DDR PASS 0 write`. Les tests sans cache de masque et
d'adresse terminent avec zéro erreur. `Z` seul peut aussi bloquer avant
le message de démarrage. Les compteurs EP0 montrent alors des commandes
reçues et transmises au CPU, sans nouveaux octets UART produits.

Le témoin historique `gpu_l12_diag_r13`, sur la même carte et avec le
même firmware binaire SHA256
`79696900e4c5aad3fc50a314d10850370b4bd1f6514d8f2aa3fdbe06a9e25260`,
passe les trois écritures/lectures DDR de 1 Mio avec cache, le framebuffer,
les changements de page et le blitter. Le test s'arrête ensuite sur
`HARED END` au lieu de `SHARED END` : il conserve un défaut USB distinct.
Les journaux sont dans `usb_ax15_20261002/`.

## Observation J-Link

Michael confirme le J-Link Ultra série 506005083 relié à l'AE350 de cette
Pro Dock. Connexion JTAG 1 MHz, IDCODE `0x1000563d`, A25 RV32 identifié.
Aucun reset CPU ni téléchargement de firmware n'est demandé au débogueur.
La connexion SEGGER arrête temporairement le CPU pour détecter ses fonctions.

- Témoin r13 : PC `0x800057d6`, boucle `get_byte()` ; CPU toujours actif
  après la perte d'un caractère USB.
- r6 : breakpoint avant la première store avec cache, PC `0x800079e8`,
  `a5=0`, `MCAUSE=MEPC=MTVAL=0`, `MSTATUS=0x80007800`.
- Un pas exécute cette store et atteint `0x800079ea`.
- L'exécution libre suivante n'atteint pas le breakpoint `0x800079f0`
  placé après la boucle d'écriture, avant le flush. Une demande d'arrêt
  échoue ensuite et la liaison au J-Link finit par expirer.
- **Le PC affiché après cette erreur de communication n'est pas fiable**
  (valeur en cache du débogueur). Aucun PC exact au blocage n'a été obtenu.

Évidence : `usb_ax15_20261002/jlink_baseline_attach_20261003.txt`,
`jlink_r6_ddr_hang_20261003.txt`, `jlink_r6_before_20261003.log`.
Syntaxe du débogueur vérifiée dans la
[documentation SEGGER](https://kb.segger.com/J-Link_Commander).

## Défaut de conception identifié par inspection

Dans `ae350_soc.v`, `ddr3_clk_in` et le HCLK du pont sont reliés à la
broche 50 MHz. La sortie PLL nommée `ddr3_ref_clk` n'est plus utilisée.
Le SDC coupe bien les chemins **clk50 ↔ ddr3_sys_clk (75 MHz)**.
Le rapport de timing positif ne vérifie donc pas ces traversées.

Dans le pont fournisseur `board/sipeed/gw_ahb_ddr3.v`, les données passent
par des FIFO à deux horloges mais plusieurs contrôles les contournent :

| Sens | Contrôles directs |
|---|---|
| UI 75 → AHB 50 MHz | `ahb_end`, `ahb_req`, `ahbr_cmd_flag`, `fifo_wr_empty` |
| AHB 50 → UI 75 MHz | `ahbw_single`, `ahbr_single`, `ahbr_start`, `data_valid` |
| AHB → UI | Adresse de lecture tenue par le protocole précédent |

Exemple de convergence dangereuse : un front de `ahb_end` peut être vu
par le registre qui efface `ahbw_single`, sans être vu sur le chemin qui
remonte `hready`. Au cycle suivant, `ahb_end && ahbw_single` ne peut plus
être vrai. FIFO vide, cet état peut rester bloqué.

Une seconde revue indépendante confirme le défaut et le câblage réel des
horloges. C'est une vulnérabilité concrète compatible avec les observations ;
son déclenchement sur carte n'a pas été directement capturé et elle ne
prouve pas la cause des pertes USB.

## Correction et contrat

Le nouveau `board/ahb_ddr_cdc.v` transporte :

- AHB → UI : une commande de 100 bits, écriture/lecture, adresse alignée
  à 8 octets, masque de 8 octets et données de 64 bits ;
- UI → AHB : une réponse de 64 bits, également utilisée comme acquittement
  des écritures acceptées par le tampon DDR aval.

Deux `ddr_dcfifo` de profondeur 4 portent les transactions. Les commandes
et fins ne traversent plus directement les domaines. L'adresse AHB est
capturée en phase adresse, HWDATA en phase données ; HREADY retient le
maître jusqu'à la réponse. NONSEQ et SEQ sont acceptés, IDLE/BUSY ignorés.
Masques byte/halfword/word/doubleword et deux cycles ERROR pour les accès
mal alignés, tailles supérieures à 64 bits ou hors du Go configuré.

Le reset s'affirme même avec une horloge arrêtée. Chaque côté tient sa
FIFO en reset pendant au moins trois fronts locaux, puis attend la reprise
du domaine opposé à travers deux bascules. Cela évite de publier une tête
ou un pointeur FIFO antérieur au reset.

**Précondition :** le reset de transaction doit aussi invalider les
commandes/lectures DDR aval. L'intégration actuelle l'associe à la perte de
calibration DDR, HRESETN étant lui-même dérivé de cette calibration.
Un reset HRESETN isolé laissant les arbitres et la DDR actifs n'est pas
couvert ; les réponses tardives d'une telle lecture doivent être drainées
ou identifiées par génération avant d'ajouter ce mode.

Les sources fermées restent intactes. Les 20 placements RAM de l'ancien
pont sont retirés de la copie CST du build, car ces cellules ont disparu.
Le SDC de production et les fréquences restent inchangés. La latence du
chemin CPU change ; aucune équivalence cycle par cycle n'est revendiquée
pour ce remplacement. Le chemin natif GPU conserve son interface.

## Validation numérique

Commande reproductible :

```sh
python3 tools/check_ahb_ddr_cdc.py --out /tmp/console_cdc_new_run
```

Sept rapports de fréquence/phases passent, chacun avec 2 216 commandes,
1 098 écritures, 1 118 lectures (dont lectures abandonnées par reset) et
1 116 vérifications de données. Tests : tous les masques et voies, rafales
de 256 beats sans cycle IDLE, accès aléatoires, attentes commande/données
indépendantes, latence de lecture variable, ERROR, pause de chaque horloge
sans reset, reset d'une lecture en vol, reset avec commande ou réponse
en attente et horloge arrêtée. Aucun débordement FIFO.

Les scénarios couvrent 50/75 MHz et leur dérive, l'inversion du rapport,
125/124,5 MHz et environ 124,9/125,2 MHz. Preuves et empreintes des sources :
`ahb_ddr_cdc_20261003/result.json`, journaux voisins. Le modèle DDR annule
les transactions lors du reset commun ; il ne simule pas un CPU/cache A25
réel ni la métastabilité analogique.

Les premières compilations matérielles sont décrites ci-dessous. La
validation sur carte reste à établir pour ce nouveau pont.

### Premier routage et placement ciblé

`cdc_r1` termine avec trois violations dans le GPU :

- reset mémoire → enable d'adresse de ligne : −0,454 et −0,243 ns ;
  enable partagé à R27C32, connexion finale de 3,709 ns vers R15C49 ;
- commit → enable de `shadow_base` : −0,046 ns, dernière connexion
  de 4,422 ns entre R88C134 et R81C114.

Aucune violation n'est rapportée dans le nouveau pont, mais cela ne mesure
pas les chemins asynchrones de ses pointeurs Gray. `cdc_r1` n'est pas
chargé. Deux contraintes de placement rapprochent ces enables de leurs
consommateurs, avec résolution des noms des cellules depuis leurs broches
CE. Aucun changement fonctionnel, de fréquence ou d'exception de timing.
Compilation suivante : `gpu_l12_usb_hs33_cdc_r2`.

### Deuxième routage et simplification de la préparation des lignes

`cdc_r2` supprime la violation `shadow_base`, mais déplacer l'enable de
ligne déplace aussi ses consommateurs : 13 violations setup, minimum
−1,741 ns, TNS −13,644 ns, toutes du reset mémoire vers les enables
`waddr`/`wleft`. Aucune violation hold. Cette image n'est pas chargée.

La contrainte ajoutée sur cet enable est retirée. Le RTL prépare maintenant
`waddr` et `wleft` au début des lignes (rectangle/copie, zoom, affine,
rangée de texte), quand leur géométrie est déjà stable. Leur chargement
ne dépend plus de la détection du dernier pixel, du dernier caractère ou
de la dernière réponse de copie. Les masques, demandes DMA et fins gardent
leur cadence précédente.

Équivalence `cdc_r3` contre les sources figées `gpu_l12_usb_hs33_ep0_r3` :
604 commandes, 2 081 517 cycles blitter, 251 234 mots ; DMA identique sur
2 081 518 cycles avec délai de fin nul. Pages et gardes exactes,
107 156 écritures et 348 623 lectures. Journal :
`gpu_hs_cdc_r3_equivalence_20261003.txt`.

`gpu_l12_usb_hs33_cdc_r3` passe les chemins GPU, sans baisse de fréquence
ni modification du SDC. Il reste trois violations USB (−0,246, −0,184,
−0,093 ns) : le chemin TXVALID vers le PHY puis TXREADY vers le contrôleur
comprend une dernière connexion de 5,409 ns de R33C174 vers R41C113.
Cette image n'est pas chargée. `cdc_r4` place la LUT finale TXREADY à
R38C142, entre ses producteurs et consommateurs, et demande les exports
officiels SDF/Verilog pour examiner aussi les délais des pointeurs CDC.
La contrainte `shadow_base` est conservée. Le témoin r13 reste chargé.

### Revue parallèle du contexte des acquittements USB

Un observateur passif compare l'endpoint courant et l'endpoint retardé
dans `usb_fifo.v` lors de chaque FIN. Le modèle officiel HS3.3 est exporté
depuis `gpu_usb_hs33_ready_r2` ; ses trois entrées de génération (wrapper,
définitions, RTL fournisseur chiffré) sont identiques à celles de `cdc_r3`.
Les exports chiffrés régénérés ont des empreintes différentes ; aucune
identité de placement avec la carte n'est revendiquée.

Le test ajoute 24 blocs de 256 octets, agrandit la file durant un ACK perdu,
intercale des contrôles EP0 et sondages EP3, puis retransmet. Résultat :
6 347 octets exacts, 96 paquets de 64 octets, 27 reprises, 157 contrôles
dont 27 avec reprise bulk en attente, 346 FIN sans mismatch d'endpoint,
620 octets OUT exacts. Les pointeurs de la FIFO de 4 096 octets bouclent.
Cela **ne reproduit pas** le défaut matériel. UTMI idéal, sans PHY analogique
ni délais SDF ; les observateurs privés de l'ancien contrôleur sont remplacés
par des constantes, les verdicts de données utilisent les interfaces publiques.
Preuve : `usb_hs33_bulk_blocks_20261003.json` et `.log`.

### r4 : timing et premières mesures sur carte

`gpu_l12_usb_hs33_cdc_r4` termine avec zéro violation setup/hold et
110 chemins détaillés, minimum +0,138 ns. Bitstream :
`28a83d1048e5ec80ed6c1b8c0b5c0c9894b8846a19124216a80fe6a1ff1f3f8d`.
Les 99 sources figées ont été contrôlées avant transfert puis de nouveau
avant chargement. Le SDC reste d'empreinte
`c9367c2d390554345db5bcc5dbb115a8c348b955dd5013e99e1ecade80c8f64b`.

L'export SDF officiel du même routage permet d'examiner les 12 bits Gray
jusqu'à la première bascule de synchronisation. Les connexions seules
valent au maximum 0,461 à 0,949 ns selon le bit ; avec clock-to-Q, le
maximum est 1,331 ns, contre 13,333 ns pour la période la plus courte.
L'écart conservateur entre bits et coins PVT reste au plus 0,759 ns.
Chaque source est une sortie Q enregistrée. Cela borne les délais
physiques de ces pointeurs, sans simuler la métastabilité analogique.

Reproduction :

```sh
python3 tools/check_ahb_ddr_cdc_sdf.py \
  --stage tang/impl/gpu_l12_usb_hs33_cdc_r4 \
  --out /tmp/cdc_r4_gray.json
```

Rapport archivé : `gpu_hs_cdc_r4_gray_sdf_20261003.json`.

Premier chargement SRAM, FTDI 2023112818 : nouvelle énumération HS480,
échos 1/64/256 exacts, puis perte de 10 octets sur l'écho 1024
(positions 73–81 et 509). Le contrôle EP0 suivant échoue avec EPROTO71.
**Le défaut USB persiste.** Les tests GPU automatiques ne démarrent pas
à ce chargement, conformément à l'arrêt sur première erreur.

Deuxième chargement du même bitstream, commande D envoyée directement
sans stress binaire préalable : masque/adresse sans cache, puis trois
passes de 1 Mio avec cache passent avec zéro erreur. `DDR END errors=0`
est suivi d'une réponse normale à `?`. Le blocage CPU observé sur r6 n'est
pas reproduit ici ; ce résultat ne suffit pas à garantir tous les resets.
La suite GPU complète est ensuite lancée sur ce même chargement.

Preuves : `usb_ax15_20261002/gpu_l12_usb_hs33_cdc_r4_first/`,
`gpu_l12_usb_hs33_cdc_r4_ddr_boot/` et
`gpu_l12_usb_hs33_cdc_r4_ddr_probe.txt` dans le même dossier.
Script exact du test au démarrage : `ahb_ddr_cdc_20261003/board_ddr_boot.py`.

La suite graphique complète termine ensuite avec succès : échos 1/64/256/
1024/4096, DDR avec cache, G0–G6, FAST, L11 et L12. Cela couvre 16 surfaces,
64 sprites, tuiles, triangles, course et affine, avec trafic CPU DDR
concurrent et zéro underflow. Course : 55,08–55,41 fps ; affine :
54,94–54,99 fps. Journal :
`usb_ax15_20261002/gpu_l12_usb_hs33_cdc_r4_gpu.txt`.

### Capture xHCI exécutée par Michael et stress après capture

La capture demandée a été exécutée sur ax15, GPU complet cdc_r4, animation
arrêtée. Le noyau 6.17 expose le slot29 du contrôleur 0000:00:14.0 pour la
console3-7, adresse6, HS480. Les 1 000 échos unitaires sont tous exacts.
Avant les diagnostics finaux, les Transfer Events ne contiennent que
1 001 `Success` et 1 000 `Short Packet`. Les 17 `Stopped` apparaissent
après le test, durant la fermeture du port. Aucun événement perdu ou
tronqué déclaré par tracefs ; nettoyage sans erreur. USBmon indisponible.

La latence écriture→premier octet va de 0,542 à 1,323 ms (médiane0,809ms).
L'historique FPGA des quatre derniers paquets montre ACK et FIN, pas
d'erreur RX ni de paquet encore pending. Cela ne reproduit pas la panne
du premier chargement. Preuves : `usb_xhci_cdc_r4_20261003/`, notamment
`analysis.json`, `capture.json`, `echo/result.json`, `echo/fpga.txt` et
`xhci.trace`.

Le stress non privilégié immédiatement suivant passe 100 tours de tailles
1/64/256/1024/4096 : **544 100 octets exacts**. Trois rechargements SRAM
supplémentaires du même fichier, 20 tours USB chacun, sont lancés pour
distinguer la stabilité de cette initialisation de sa reproductibilité.

Le test s'arrête au **premier** de ces trois rechargements : 1/64/256
passent, puis l'écho 1024 perd l'octet208. La réponse à `?` est complète.
Sans rechargement, un autre stress perd l'octet704 du même type de bloc,
et certaines lettres des messages initiaux sont absentes. Ce n'est donc
pas seulement une perte limitée aux premiers octets de l'énumération.
Cela établit des comportements différents entre chargements, sans
identifier à lui seul le mécanisme d'initialisation en défaut.

`check_usb_xhci.py` accepte maintenant `--sizes` (défaut inchangé :1).
La capture reste bornée à30s, sur instance tracefs privée, avec worker
non privilégié et arrêt à la première différence. La série mixte reprend
les données pseudoaléatoires déterministes du stress. Auto-test des
filtres et syntaxe Python : PASS. Le worker matériel de vérification
échoue dès son premier octet sur le chargement défaillant ; l'historique
UTMI montre le DATA1 de CRC8157, une tentative marquée ACK/FIN et trois
autres sans ACK, sans erreur RX signalée. Aucune capture électrique
ne permet encore d'identifier l'acquittement effectivement émis par l'hôte.

La nouvelle capture root est demandée à Michael dans
`TESTS/usb_xhci_cdc_r4_blocks_20261003`, avec tailles1/64/256/1024/4096.
La carte reste au repos sur cdc_r4 pendant cette intervention. Preuves :
`usb_ax15_20261002/gpu_l12_usb_hs33_cdc_r4_repeat/`,
`gpu_l12_usb_hs33_cdc_r4_repeat_same_boot.log` et
`usb_xhci_cdc_r4_blocks_worker_check/` dans le même dossier.

### Capture par blocs reçue : erreur avant le premier écho

La seconde capture demandée a bien été exécutée et récupérée dans
`usb_xhci_cdc_r4_blocks_20261003/`. Son `analysis.json` distingue les seuls
Transfer Events des acquittements de commandes xHCI. Elle contient 687
USB Transaction Error : 80 EP2 IN, 605 EP3 IN et 2 EP0 ; aucune EP2 OUT.
Douze erreurs précèdent le premier OUT applicatif (10 EP2, 2 EP3). La
première survient 67,415 ms après soumission des lectures et 86,821 ms
avant le premier OUT E. EP3 est vide et ne possède aucun producteur dans
notre RTL ouvert. Cela exclut une explication limitée au contenu des
FIFO de l'application, sans localiser encore le défaut PHY/contrôleur.

Le premier écho61 est livré au noyau à7415956.262197, mais Python ne le
lit que421,179ms plus tard. Ce délai inclut donc la restitution par le
pilote après les erreurs, ce n'est pas une mesure du temps de réponse
du FPGA. Le bloc64 suivant perd son premier octet e7 : le noyau remet
exactement63 fois un octet, de7415956.694535 à7415956.699743, sans nouvelle
Transaction Error pendant cette fenêtre. Les63octets sont exactement
les63derniers du bloc attendu. Le diagnostic EP0 final échoue à-71 et
`fpga.txt` est vide. Le reset xHCI du toggle a déjà eu lieu auparavant ;
l'absence de capture des PID/ACK électriques empêche de prouver ici le
mécanisme exact de perte. Aucune perte/overrun tracefs, troncature ou
erreur de nettoyage n'est déclarée.

Une trace passive des IN/NAK est ajoutée pour distinguer le token reçu,
la réponse offerte/acceptée au PHY et son délai. Elle sera récupérable
via J-Link et deux FIFO à horloges séparées, sans requête EP0 pendant
la panne. Le GPU complet est conservé. Ce changement est une
instrumentation, pas encore une correction de la panne USB.
