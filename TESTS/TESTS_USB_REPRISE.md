# Console USB — correction des reprises de paquets IN

Revue des 29 et 30 septembre 2026, à la suite du problème USB signalé pendant
l'intégration des couches en tuiles L11.

## Reproduction du défaut

La Pro Dock FTDI `2023112818` est identifiée sur le bus USB `3:73` lors de
cette revue ; le port CDC est `/dev/ttyACM1`, VID:PID `359f:2011`.
Ces numéros de périphériques sont à relire avant un nouvel essai.

- L'image initialement chargée répond `MegaPro GPU G6 FAST`, sans `TILES`.
  Le deuxième tour d'écho perd 22 octets sur une rafale de 4 096 ; le CPU
  répond ensuite normalement à la demande d'identification.
- Le build L11 `gpu_l11_r14` est vérifié avant chargement : 79 sources
  conformes au manifeste, 110 chemins de timing positifs, marge +0,140 ns.
- Après chargement SRAM de r14, le test standard échoue sur l'écho de
  256 octets : 223 octets reçus.
- Le test répété avec données pseudo-aléatoires échoue aussi : 548 octets
  reçus sur 1 024, puis plus de réponse au sondage immédiat.

Les problèmes de communication apparaissent avant l'activation des tuiles.
La simulation L11 en 800 × 480 et la comparaison des références firmware/
Python ont été rejouées avec succès pendant cette revue.

## Défaut 1 : adresse de prélecture après reprise

`sync_tx_pkt_fifo.v` possède deux adresses de lecture de sa RAM : `rp`, pour
le prochain octet, et `rp_next`, pour anticiper l'octet suivant lors de
lectures consécutives.

Après une tentative de paquet sans acquittement, `rp` revient au début
du paquet conservé dans `pkt_rp`. L'ancien code ne rétablissait pas
`rp_next` : la reprise lisait un octet situé après la tentative précédente
à la place du deuxième octet du paquet.

Le banc [usb_tx_retry_tb.sv](rtl/usb_tx_retry_tb.sv) reproduit le défaut :
après une tentative de 16 octets commençant à l'adresse 8, le deuxième
octet de la reprise vaut `19` hexadécimal au lieu de `09`.

Correction : rétablir les deux pointeurs ensemble, y compris le cas où
une lecture accompagne la fin de la tentative.

- [Échec avant correction](usb_tx_retry_before.txt).
- [Simulation corrigée](usb_tx_retry_simulation.txt) : 191 octets vérifiés,
  avec reprises, tentative interrompue et franchissement de la limite RAM.

## Défaut 2 : longueur variable d'un paquet réémis

La FIFO conservait le début d'un paquet non acquitté mais le multiplexeur
d'endpoints recalculait sa longueur depuis le nombre d'octets disponibles.
De nouveaux octets UART pouvaient donc être inclus dans une retransmission.

Si le PC avait reçu le premier paquet et que son acquittement avait été
perdu, il éliminait cette retransmission comme doublon. Les nouveaux octets
ajoutés étaient alors eux aussi éliminés, alors que la console les retirait
de sa FIFO après acquittement de la reprise.

Le banc [usb_in_packet_tb.sv](rtl/usb_in_packet_tb.sv) reproduit ce scénario :

1. Quatre octets sont transmis sans acquittement côté périphérique.
2. Sept nouveaux octets UART sont ajoutés.
3. L'ancienne interface propose une reprise de onze octets au lieu de quatre.

Correction dans `usb_fifo.v` : mémoriser par endpoint la longueur annoncée
lors de la première lecture ; la conserver jusqu'à `txpktfin` ou au reset
USB. Les octets arrivés ensuite restent dans le paquet suivant.

Le test couvre aussi un paquet plafonné à 64 octets, plusieurs tentatives
avec de nouveaux arrivants et un paquet d'un seul octet. La correction du
pointeur de prélecture est nécessaire en complément.

Ces deux défauts sont établis en simulation. Les essais sur carte finaux
confirment la disparition des pertes sur les séquences testées ; ils ne
prétendent pas identifier chaque événement électrique ayant déclenché
les reprises dans les versions antérieures.

## Défaut 3 : disponibilité et longueur désynchronisées

Le build r4, qui contient les deux premières corrections et passe le timing,
passe aussi le diagnostic complet G0–G6/FAST/L11. Le test USB prolongé détecte
encore une perte isolée : 4 095/4 096 octets au quatrième tour, puis, après le
diagnostic GPU, 255/256 octets au treizième tour d'un autre essai. La console
répond à `?` après chaque échec.

`usb_fifo.v` figeait la longueur pendant `txact`, mais continuait de mettre
à jour `txcork` depuis l'état vide de la FIFO. Si un octet UART arrivait
pendant une requête IN commencée à vide, la longueur restait zéro et
`txcork` s'ouvrait. Le banc ajouté reproduit cette incohérence :
[usb_cork_before.txt](usb_cork_before.txt).

Correction : calculer l'autorisation d'envoi à partir de la longueur choisie
et les acquérir ensemble. **Tant que CORK est fermé, le paquet peut devenir
disponible même si `txact` reste actif.** Une fois le paquet ouvert, longueur
et disponibilité restent figées pendant sa lecture. Un changement d'endpoint
acquiert les valeurs de ce nouvel endpoint. Le reset revient à l'état vide.

La première version de cette correction gelait aussi l'état vide pendant
`txact`. Elle passait le modèle de simulation initial mais le build r11,
validé au timing puis chargé sur carte, ne répondait plus à l'identification.
Le manuel du contrôleur (IPUG927-1.5E, section 3.2) permet de fournir les
données après l'activation de `txact` ; le banc ne couvrait pas une attente
prolongée de données. Le nouveau scénario révèle ce gel trop strict :
[usb_cork_wait_before.txt](usb_cork_wait_before.txt). r12 autorise l'ouverture
avec une longueur non nulle pendant cette attente, puis fige le paquet.

Les tests vérifient désormais l'attente active, l'arrivée tardive d'un
premier octet, un deuxième octet après ouverture (qui reste pour le paquet
suivant), la sélection simultanée, le reset et les reprises. Le retour à r4 sur la même carte rétablit immédiatement l'identification
et un tour de 5 441 octets exacts. r12 passe ensuite le timing mais reste
sans réponse USB sur la carte : l'attente active n'était pas le seul cas
manquant au modèle.

### Interaction avec un sondage à vide

Un strobe POP alors que CORK est fermé ne transfère pas de paquet non vide.
La mémorisation introduite par la deuxième correction enregistrait pourtant
une longueur nulle comme paquet en attente. En reliant ensuite CORK à cette
longueur, la troisième correction rendait ce zéro permanent : les nouvelles
données ne pouvaient plus ouvrir le paquet. Le nouveau scénario injecte
ce sondage à vide avant l'arrivée UART et reproduit le blocage de r12 :
[usb_empty_pop_before.txt](usb_empty_pop_before.txt).

r13 n'enregistre une reprise que pour `txpop && !txcork && txlen != 0`.
Les sondages vides restent sans effet sur l'état des reprises. La simulation
de paquets et celle de 30 000 octets concurrents passent. Après chargement
de r13 sur la Pro Dock, l'identification revient et **100 séries consécutives
passent, soit 544 100 octets exacts**, sans perte ni nouvelle tentative
applicative. Chaque série vérifie aussi l'identification du firmware.

## Vérifications

Les tests utilisent les modules réellement compilés pour la console.
Les données USB sont vérifiées indépendamment des pointeurs du composant.

```sh
verilator --binary --timing -Wno-fatal --top-module usb_tx_retry_tb \
  --Mdir /tmp/console_usb_tx_retry \
  TESTS/rtl/usb_tx_retry_tb.sv tang/rtl/usb/sync_fifo/sync_tx_pkt_fifo.v
/tmp/console_usb_tx_retry/Vusb_tx_retry_tb

verilator --binary --timing -Wno-fatal --top-module usb_in_packet_tb \
  --Mdir /tmp/console_usb_in_packet TESTS/rtl/usb_in_packet_tb.sv \
  tang/rtl/usb/sync_fifo/usb_fifo.v \
  tang/rtl/usb/sync_fifo/sync_tx_pkt_fifo.v \
  tang/rtl/usb/sync_fifo/sync_rx_pkt_fifo.v
/tmp/console_usb_in_packet/Vusb_in_packet_tb
```

Le banc [usb_stream_tb.sv](rtl/usb_stream_tb.sv) ajoute un producteur et
un consommateur simultanés : 30 000 octets, 14 733 tentatives, 3 685
reprises, plusieurs tours complets des pointeurs de FIFO. Tous les octets
sont exacts ([journal](usb_stream_simulation.txt)). Il se compile avec les
mêmes sources que `usb_in_packet_tb`.

Le banc historique `uart2_to_ep2_tb.sv` vérifie également le récepteur
UART, ses tolérances de débit et le trajet USB OUT → UART.

Le nouvel outil [check_usb_stress.py](../tools/check_usb_stress.py) répète
l'écho binaire avec des données pseudo-aléatoires reproductibles et compare
tous les octets. En cas d'échec, il conserve attendu, reçu et réponse au
sondage suivant, sans considérer une retransmission applicative comme un succès.

```sh
python3 tools/check_usb_stress.py --rounds 20 --out /tmp/console_usb_stress
```

Un seul programme doit utiliser le port CDC. Le script prend un verrou
exclusif ; arrêter la manette Web ou tout terminal avant de l'exécuter.

## Compilation et état de validation

- `gpu_l11_usb_r1` : première correction seule ; rejeté par le contrôle de
  timing, marge −0,837 ns dans le socle DDR. **Non chargé.**
- `gpu_l11_usb_r2` : les deux corrections ; rejeté au timing, marge
  −2,791 ns vers l'adresse de lecture de la BSRAM du blitter. **Non chargé.**
- `gpu_l11_usb_r3` : les deux corrections et découplage de cette adresse
  de lecture ; rejeté au timing à −2,019 ns sur le chemin DDR ready/reset →
  arbitre → rotation de masque → tampon CPU. **Non chargé.**
- `gpu_l11_usb_r4` : **timing validé**, 110 chemins détaillés, minimum
  +0,140 ns, TNS nul. Chargé sur la Pro Dock ; diagnostic complet
  G0–G6/FAST/L11 réussi. Test USB prolongé encore en défaut (voir défaut 3).
- `gpu_l11_usb_r5` : cohérence de `txcork` et longueur ; rejeté au timing
  à −2,468 ns, préparation d'adresse du lecteur vidéo. **Non chargé.**
- `gpu_l11_usb_r6` : retrait du contrôle de limite DDR des activations de
  registres d'adresse/alignement ; rejeté au timing à −1,759 ns sur le
  retour DDR vers l'état du blitter, avec deux autres familles de chemins
  en défaut (bornes de copie, état du rasteriseur de triangles). **Non chargé.**
- `gpu_l11_usb_r7` : codage des états simplifié et bornes de copie préparées
  à l'avance ; rejeté au timing à −1,460 ns sur les descripteurs de sprites,
  avec aussi un décodage trop large des nouveaux états. **Non chargé.**
- `gpu_l11_usb_r8` : tests directs des bits d'état et libération de quatre
  ancrages de mémoire de sprites ; rejeté au timing à −1,102 ns sur
  l'acquittement DDR vers le blitter, et −0,265 ns vers une étiquette DDR.
  **Non chargé.**
- `gpu_l11_usb_r9` : acquittement DMA enregistré et préparation anticipée
  des étiquettes DDR ; rejeté au timing à −2,221 ns sur le multiplexage
  de lecture des registres GPU vers le CPU. **Non chargé.**
- `gpu_l11_usb_r10` : présélection enregistrée des registres GPU pendant
  la phase adresse AHB, sans cycle supplémentaire ; rejeté au timing à
  −0,307 ns dans la correction du quotient négatif et −0,181 ns sur la fin
  de caractère du blitter. **Non chargé.**
- `gpu_l11_usb_r11` : simplification du quotient négatif et préparation de
  la fin de caractère ; **timing validé**, 110 chemins, minimum +0,140 ns,
  TNS nul. Chargé, mais absence de réponse USB : gel à vide trop strict
  dans la troisième correction, décrit ci-dessus. **Non archivé.**
- `gpu_l11_usb_r12` : ouverture cohérente du paquet pendant une attente
  active de données ; **timing validé**, +0,140 ns. Chargé mais USB toujours
  muet : réservation à tort d'un paquet vide. **Non archivé.**
- `gpu_l11_usb_r13` : exclusion des sondages vides de la mémorisation des
  reprises ; **timing validé**, 110 chemins, minimum +0,093 ns, TNS nul.
  Chargé sur la Pro Dock : **100 séries USB, 544 100 octets exacts**.
  **G0–G6/FAST/L11 validés**, puis 100 autres séries USB avec composition
  L11 active : **1 088 200 octets exacts au total**. Bitstream archivé.

### Chemin critique du blitter

La remise à zéro de l'adresse `rj` dépendait directement du décodage du
dernier pixel (dégradé, copie, texte ou zoom). L'inférence de BSRAM plaçait
ce décodage devant son adresse de lecture. Une impulsion enregistrée
`row_rewind` sépare maintenant les deux opérations. Elle remet le pointeur
à zéro pendant `M_ROW_SEG`, avant la première consommation du DMA : aucun
cycle supplémentaire n'est ajouté aux commandes.

Le banc lié [blitter_equiv.sv](rtl/blitter_equiv.sv) compare les sorties de
contrôle à chaque cycle et les pixels/masques à chaque consommation avec
le module inchangé du build L11 r14. Sur les 541 commandes : **1 247 830
cycles et 94 260 mots identiques** avant le changement de latence DMA décrit ci-dessous. Les trois pages et leurs gardes mémoire
restent exactes ; les compteurs de transactions et d'attente sont identiques.
Journal : [gpu_l11_usb_blitter_equivalence.txt](gpu_l11_usb_blitter_equivalence.txt).

```sh
python3 TESTS/test_gpu_accel.py \
  --equiv-blitter-root tang/impl/gpu_l11_r14/source \
  --out /tmp/console_l11_blitter_equiv
```

### Décodage des états et bornes de copie

`blitter.v` et `gpu_triangle.v` codent chaque état par un bit au lieu d'un
nombre binaire. Les transitions utilisent `case (1'b1)` et des tests directs
de bits, avec `parallel_case` : le code ne compare pas un vecteur de
55 bits à une constante pour reconnaître chaque état. Les acquittements DDR et les comparaisons de bords ne
traversent plus un long décodage pour choisir l'état suivant. Les transitions
et les cycles restent les mêmes ; aucun état d'attente n'est ajouté.

Les quatre bornes de la surface source d'une copie sont préparées en deux
étapes dans les cycles déjà disponibles entre le chargement des coordonnées
(`M_F3`) et leur utilisation (`M_COPY_CLIP`). Cela sépare translation et
comparaison, sans changer leur largeur signée ni les limites admises.

Le banc d'équivalence du blitter inclut désormais aussi le rasteriseur et
ses diviseurs **dans leur version de référence inchangée**, renommés pour
coexister avec les nouveaux modules. Les 1 247 830 cycles et 94 260 mots
restent identiques avant le changement de latence DMA décrit ci-dessous.

### Chemin critique de l'arbitre DDR

Dans `ddr_arb.v`, `serve_m1` et `serve_m2` pilotaient à la fois
l'acceptation et le multiplexage de l'adresse/des données. Le signal
`ready` traversait donc cette sélection puis la rotation de l'adaptateur
128→256 bits avant d'atteindre le tampon CPU du GPU.

Le choix du maître est maintenant calculé sans `ready`, qui continue de
conditionner chaque acceptation. La priorité reste writer urgent, CPU,
writer, reader. Les données d'un cycle sans commande valide n'ont pas de
signification ; toute commande acceptée garde sa valeur et son cycle.

[ddr_arb_equiv.sv](rtl/ddr_arb_equiv.sv) compare le module modifié au module
inchangé sur les 4 096 combinaisons : états plein/vide, file d'étiquettes
pleine, huit codes de commande, données associées, urgences, demandes,
les deux signaux ready et reset. Les acceptations, commandes, masques,
données et écritures d'étiquettes sont identiques.
Journal : [ddr_arb_equivalence.txt](ddr_arb_equivalence.txt).

Pour reproduire, extraire le module `ddr_arb.v` du manifeste
`gpu_l11_usb_r3/source` dans `/tmp/console_ddr_arb_reference.v` en renommant
uniquement `module ddr_arb #(` en `module ddr_arb_reference #(`, puis :

```sh
verilator --binary --timing -Wno-fatal --top-module ddr_arb_equiv \
  --Mdir /tmp/console_ddr_arb_equiv TESTS/rtl/ddr_arb_equiv.sv \
  tang/rtl/board/ddr_arb.v /tmp/console_ddr_arb_reference.v
/tmp/console_ddr_arb_equiv/Vddr_arb_equiv
```

### Préparation d'adresse du lecteur vidéo

Dans `gpu_line_reader.v`, le contrôle de dépassement du premier Gio de DDR
conditionnait les registres d'adresse et d'alignement, créant un long
chemin vers leurs activations. Ils sont maintenant chargés même si la
ligne est refusée. Dans ce cas, l'état passe toujours à la couche suivante
sans lever `request_valid` : aucune adresse refusée n'est émise.

[Le banc lié](rtl/gpu_reader_equiv.sv) exécute le lecteur antérieur du
build r5 avec les mêmes entrées que le nouveau lecteur dans la simulation
complète 800 × 480. Les signaux de contrôle sont comparés à chaque cycle,
les adresses lorsque la requête est valide, les pixels et index lorsque
le bloc produit est valide. Résultat : **77 670 746 cycles, 12 997 458
cycles avec requête valide, 646 850 blocs identiques**, y compris les
surfaces hors DDR et le retour au framebuffer simple.

Les compteurs du banc restent identiques : 1 797 891 lectures CPU, scènes
de tuiles à 2 284 et 2 452 cycles/ligne. Journal :
[gpu_l11_usb_reader_equivalence.txt](gpu_l11_usb_reader_equivalence.txt).

Pour reproduire, extraire `gpu_line_reader.v` du manifeste r5 en renommant
uniquement son module en `gpu_line_reader_reference`, puis ajouter ce
fichier et `TESTS/rtl/gpu_reader_equiv.sv` à la commande Verilator L11
(documentée dans `TESTS_GPU_L11.md`).

### Placement des descripteurs de sprites

L11 avait ancré quatre banques des descripteurs à leurs positions du build
FAST (`R10`, `R28`, `R46`). Le placement r7 situait le lecteur près de `R81` :
le trajet BSRAM → calcul de bord passait **5,668 ns en routage seul**, avant
l'addition et le découpage. Ces quatre ancrages sont retirés dans `gpu.cst`,
ce qui laisse Gowin placer les descripteurs près de leur consommateur.
Les autres ancrages restent présents ; aucune contrainte temporelle n'est
relâchée et le contenu logique des mémoires ne change pas.

### Acquittement DMA et préparation des étiquettes DDR (r9)

Les retours `w_done`, `f_done` et `c_ack` de `gpu_blit_dma.v` sont désormais
enregistrés. Ils signalent **au cycle suivant** l'acceptation effective de
la dernière écriture DDR. L'adresse, les données, les masques, l'ordre et
l'acceptation des écritures restent inchangés. Cela coupe le trajet demande
de lecture vidéo → priorité d'arbitre → ready du blitter → état suivant.
La fin n'est jamais annoncée avant l'acceptation de l'écriture.

Cette modification ajoute volontairement un cycle à la fin d'un transfert,
contrairement aux autres réécritures qui conservent les cycles.
[Le comparateur DMA](rtl/gpu_dma_equiv.sv) vérifie chaque cycle avec le module
antérieur : tous les signaux natifs sont identiques et ces trois retours
sont retardés d'exactement un cycle.

La régression complète conserve **95 449 écritures DDR**, dont 69 159
écritures pleines, et tous les octets des trois pages et de leurs gardes.
Elle dure désormais **1 269 390 cycles** contre 1 247 830 auparavant
(**+1,73 %** sur cette séquence). Les lectures CPU/affichage concurrentes
continuent pendant ce supplément de temps ; leurs compteurs augmentent.
Le benchmark r13 sur carte confirme **55,11 images/s** dans les deux modes
de course. Le maximum GPU vaut 9,851 ms (original) et 10,445 ms (cached),
avec zéro ligne manquante.

Dans `ddr_ui_adapt.v`, le prochain emplacement libre reçoit l'étiquette
chaque cycle où la file n'est pas pleine. Seule une commande acceptée fait
avancer le pointeur et publie l'étiquette. L'écriture reste interdite à
file pleine, où cet emplacement est aussi la tête occupée. Cela retire
la décision d'arbitrage de l'activation d'écriture des étiquettes sans
changer le protocole ni sa latence.

[ddr_ui_equiv.sv](rtl/ddr_ui_equiv.sv) compare les modules actuels et r8 :
20 000 cycles, 5 063 lectures, 2 461 écritures, 26 cycles file pleine et
917 émissions/réceptions simultanées, rotations et moitiés de rafale
variées. [Journal](ddr_ui_equivalence.txt).
Pour reproduire, renommer uniquement `module ddr_ui_adapt #(` du snapshot
r8 en `module ddr_ui_reference #(` puis le compiler avec le banc et le
module courant (`--top-module ddr_ui_equiv`).

### Lecture CPU des registres GPU (r10)

Le décodage de `bus_addr` traversait le multiplexage des valeurs puis les
sélections scanout/blitter et GPU/registres système avant le registre de
retour CPU. `gpu_scanout.v` prépare maintenant les 24 bits de sélection
pendant la phase adresse AHB, au même instant que `bus_addr`. La phase
suivante applique ces bits aux valeurs courantes des registres. L'accès ne
prend aucun cycle de plus, et les valeurs de statut restent courantes.

Le banc lié [gpu_registers_equiv.sv](rtl/gpu_registers_equiv.sv) compare
avec l'ancien multiplexeur et son propre registre d'adresse. Le banc
[gpu_registers_tb.sv](rtl/gpu_registers_tb.sv) balaie trois fois les
4 096 adresses, y compris les adresses non alignées et non définies,
avec resets et écritures bloquées pendant une validation de scène :
**18 663 cycles comparés, 6 314 cycles d'attente**, résultat exact.
[Journal](gpu_l11_usb_registers_equivalence.txt).
Le même comparateur passe aussi **82 840 528 cycles AHB** dans la
simulation L11 complète, dont les images, les compteurs et les budgets de
ligne restent identiques. [Journal](gpu_l11_usb_layers_simulation.txt).

### Arrondi des divisions et fin de caractère (r11)

La correction d'un quotient négatif calculait `-next_q - (next_r != 0)`
après la soustraction du reste. Le nouveau calcul reconnaît un reste nul
par `shifted == 0 || shifted == divisor`, prépare l'incrément du complément
du quotient haut en parallèle et choisit ensuite les bits de résultat.
Le résultat reste identique modulo 36 bits, sans étape supplémentaire.
Le banc [gpu_divider_equiv.sv](rtl/gpu_divider_equiv.sv) compare avec le
module r14 inchangé : **12 000 divisions, 468 000 cycles identiques**, nombres
positifs/négatifs, bornes signées, diviseurs 1 et 131 071, ainsi que le
comportement historique pour un diviseur nul.
[Journal](gpu_l11_usb_divider_equivalence.txt).

Le blitter prépare `text_last_char` pendant `M_TXT_FONT`, avant les huit
pixels (ou seize à l'échelle 2). Cela retire l'addition de l'index du
caractère de la transition de fin de rangée. La régression de 541 commandes
et sa comparaison avec le blitter/rasteriseur/diviseur r14 restent exactes,
avec les mêmes 1 269 390 cycles qu'avant ces deux simplifications.

Les contraintes de fréquence sont inchangées : AE350 800 MHz, bus 80 MHz,
DDR UI/GPU 75 MHz et LCD 35 MHz. Aucun contenu chiffré n'est modifié.

## Validation finale sur Pro Dock — r13

Bitstream chargé en SRAM et archivé :
[`console_gpu_l11_800.fs`](../bitstreams/console_gpu_l11_800.fs),
[empreinte SHA-256](../bitstreams/console_gpu_l11_800.sha256) :
`163203fdb7665e74c7df3e067d1660625a545bb46a851df621c7c2734d4e800d`.

- 79 sources courantes et figées conformes au [manifeste](gpu_l11_sources.json).
- [Timing](gpu_l11_timing.txt) : 110 chemins détaillés, minimum +0,093 ns
  en établissement, +0,138 ns en maintien ; 24 lignes TNS à zéro.
- [Occupation de toute la console](gpu_l11_resources.txt) : 30 101 éléments
  logiques, 21 530 registres, 217 BSRAM, 17 DSP et 8 horloges PRIMARY.
- Firmware inchangé : 53 160 octets d'image ITCM, BSS 28 920 octets.
- [Chargement](gpu_l11_load.txt) terminé (`DONE`), Pro Dock FTDI `2023112818`.
- [100 séries USB initiales](gpu_l11_usb_stress.txt) : 544 100 octets exacts.
- [100 séries avec tuiles actives](gpu_l11_usb_stress_tiles.txt) : 544 100
  octets exacts supplémentaires ; affichage actif, empreinte `4fe83fa7`,
  maximum 952 cycles/ligne, aucun refus ni ligne manquante.
- [Diagnostic complet](gpu_l11_uart.txt) : DDR3, G0–G6, FAST et L11 réussis.
  Les quatre poses L11 correspondent exactement aux références ; le
  défilement atteint 55,06–55,17 images/s, sans commande de dessin.
  Avec trafic CPU DDR, 55,36 images/s et 1 105/2 556 cycles au maximum.
- [Comparaison hôte/firmware/carte](gpu_l11_usb_host_comparison.txt) :
  quatre poses et neuf positions de défilement identiques.

Le contrôle visuel final de Michael confirme : « Oui, le décor défile
correctement ». La carte est laissée sur le décor en défilement (`W`).
Les mesures ci-dessus portent sur les séquences décrites.

### Reproduire les essais finaux

Charger le bitstream archivé sur la Pro Dock identifiée par son numéro de
série, attendre `DONE`, puis exécuter avec un seul utilisateur du port CDC :

```sh
python3 tools/check_usb_stress.py --rounds 100 --out /tmp/usb_initial
python3 tools/check_gpu_console.py --wait 20
python3 tools/check_usb_stress.py --rounds 100 --tiles --out /tmp/usb_tiles
```

L'option `--tiles` initialise la scène L11 avant les échos, laisse le GPU
composer ses couches pendant tout le test et vérifie ensuite la progression
des images, les refus, les lignes manquantes et le budget de composition.
Le journal doit être conservé pour inclure les résultats détaillés.

Les références blitter, triangles et DMA du snapshot r14 sont identiques
aux fichiers du commit `33c6798` ; elles peuvent aussi être extraites de ce
commit pour rejouer les comparateurs sans conserver les anciens builds.


## Cas supplémentaire pendant L12 : octet présent mais non annoncé

Le 30 septembre, `gpu_l12_r2` passe le timing mais échoue en USB : délai
d'écriture sur 4096 octets, puis 59 octets reçus sur 64 lors d'un nouveau
chargement. L11 rechargé sur la même carte passe à nouveau 100 séries,
544 100 octets exacts ([comparaison L11](gpu_l12_l11_usb_comparison.txt)). Le changement
d'implémentation expose donc un défaut absent des séries précédentes ;
la cause physique précise de cette différence n'est pas établie.

L'examen du FIFO trouve un cas logique non couvert : son RAM reçoit un
octet alors que `CORK` est encore fermé et que la longueur enregistrée
vaut zéro. Le contrôleur peut encore terminer son sondage vide avec POP
et acquittement. Le garde de mémorisation de reprise ajouté en r13
n'empêchait pas ce POP d'avancer le pointeur RAM. Un octet pouvait ainsi
être libéré sans avoir été annoncé comme payload.

Le nouveau cas du banc `usb_in_packet_tb.sv` reproduit exactement cette
perte : [avant correction](usb_unpublished_pop_before.txt),
[après correction](usb_unpublished_pop_simulation.txt). La correction
qualifie les POP envoyés aux FIFO par `!s_usb_txcork && s_usb_txlen != 0`.
La sortie de données et les autres handshakes sont conservés.
Le flux concurrent garde exactement 30 000 octets, 14 733 tentatives et
3 685 reprises ([journal](usb_l12_stream_simulation.txt)).

La validation matérielle de cette correction est en cours dans L12.


## 2 octobre : offre périmée lors du changement d'endpoint

Le banc avec contrôleur **et PHY originaux**, après initialisation à UTMI,
reproduit un autre cas : le passage EP0 → EP2 expose brièvement CORK ouvert
et une longueur nulle provenant d'EP0. Cela produit un ZLP DATA0 sur EP2.
Si son ACK est perdu et qu'une donnée UART arrive, la reprise contient cette
donnée sous le même DATA0 ; l'hôte peut l'éliminer comme doublon.

La FIFO ferme désormais CORK lorsque l'endpoint courant diffère de
`s_endpt_sel`. La même condition qualifie POP et la réservation du paquet.
Les registres de longueur et le chemin de données restent inchangés.
Le test avant correction échoue sur la reprise `c3 00 00` → `c3 11 80 b3` ;
après correction, le sondage vide reçoit NAK et les octets utiles gardent
leur identité jusqu'à l'ACK. Les tests historiques conservent leurs journaux.

Voir [la validation L12](TESTS_GPU_L12.md),
[le défaut avant correction](usb_controller_phy_zlp_before_20261002.json) et
[la comparaison de la garde simplifiée](usb_endpoint_guard_r28_equivalence_20261002.json).
Les essais à horloges hôte/carte indépendantes valident le contenu et les
reprises dans les séquences testées ; leurs écarts de framing conservés
empêchent de déclarer le PHY complet conforme. Aucun succès de simulation
n'est présenté comme une validation matérielle.
