# USB2 — revue des captures xHCI du 2 octobre 2026

Les captures établissent une récupération xHCI avec remise à zéro du toggle entre deux livraisons du même octet. La seconde identifie l’erreur déclenchante comme **USB Transaction Error sur EP2 IN**. Elles ne déterminent pas encore le défaut initial dans le PHY, le contrôleur ou leur interface.

## Périmètre et preuves

Analyse en lecture seule, sans nouveau test matériel ni modification du transport. Les deux captures concernent `359f:2011`, série `11252024`, topologie `3-7`, adresse `3:91`, vitesse négociée **480 Mbit/s**, slot xHCI **49**, contrôleur `0000:00:14.0`, noyau `6.17.0-35-generic`.

| Capture | Fichiers de référence | Résultat applicatif |
|---|---|---|
| A — `160051_866672` | [trace xHCI](usb_xhci_20261002_160051_866672/xhci.trace), [échos](usb_xhci_20261002_160051_866672/echo/result.json), [FPGA](usb_xhci_20261002_160051_866672/echo/fpga.txt), [métadonnées](usb_xhci_20261002_160051_866672/capture.json) | Index 17 : `ea` demandé, `eaea` reçu |
| B — `160500_867079` | [trace xHCI](usb_xhci_20261002_160500_867079/xhci.trace), [échos](usb_xhci_20261002_160500_867079/echo/result.json), [métadonnées](usb_xhci_20261002_160500_867079/capture.json) | Index 21 : `0e` demandé, `0e0e` reçu |

Les horodatages ci-dessous sont monotones, en secondes. Les indices commencent à zéro. L’endpoint xHCI **5** représente USB **EP2 IN**, et l’endpoint xHCI **1** représente USB **EP0**. Dans un Transfer Event, `len` est le reliquat : `Short Packet len 1023` pour une URB de 1024 octets correspond ici à **un octet reçu**, sans erreur.

## Capture A : doublon et première émission FPGA

À `7344872.721857`, une URB EP2 IN livre un octet. À `.721863`, xHCI programme `Reset Endpoint`, slot 49, endpoint 5, `flags t:C`. Après avancement du pointeur, une autre URB termine vide à `.721977`, puis une troisième livre un octet à `.721992`. Les deux livraisons non vides sont séparées de **135 µs** ; le test reçoit `eaea` pour une seule commande. Voir `xhci.trace`, lignes 89–99.

La trace FPGA conserve la première émission de `ea` : DATA0 (`c3`), un octet annoncé, CRC transmis `c1 30` correct pour cet octet, **aucun ACK ni FIN observé** sur ce premier essai. Le prédécesseur est DATA1 avec le CRC `81 07` de `a1`, acquitté et terminé. Aucun ZLP ne figure parmi les trois prédécesseurs conservés. Cette capture ne montre pas le PID de la reprise finale.

Limite corrigée dans B : le filtre de A appliquait le slot à `xhci_handle_transfer`, qui expose le TRB du buffer, sans slot dans `field3`. Il éliminait donc les événements utiles. A prouve le reset, mais pas son code d’erreur déclencheur. B utilise `xhci_handle_event`, qui expose les véritables Event TRB. [Points d’appel Linux v6.17, lignes 2775–2776 et 2830–2832](https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/usb/host/xhci-ring.c).

## Capture B : erreur EP2, retard hôte et doublon distincts

**Premier incident, après l’écho correct `59` (index 8).** À `7345121.507224`, le transfert court réussit ; l’octet est rendu à `.507249`. Le **TD suivant**, à une autre adresse, produit `USB Transaction Error len 1024` à `.507251`, puis un reset `t:c` à `.507254`. Son URB termine vide à `.507325`. Voir lignes 73–83.

**Le retard de `a2` (index 9) apparaît après sa réception USB.** La commande commence à `7345121.517771456`. L’événement de réception arrive à `.518287` et le giveback d’un octet à `.518290`, soit **0,519 ms** après le départ. La lecture Python finit seulement à `7345122.011269454` : **493,498 ms** après le départ, dont **492,979 ms après giveback**. L’URB précédemment en erreur est réarmée à `7345122.011188`, 81 µs avant cette lecture. Voir lignes 84–90 et l’échantillon 9.

Il serait donc incorrect d’attribuer ces 493 ms à l’attente du paquet sur le bus. La coïncidence avec le réarmement après environ 500 ms évoque la récupération CDC ; le point exact qui retarde la restitution à l’application n’est pas instrumenté. Linux CDC prévoit un délai `HZ/2` pour les erreurs `-EPROTO` et `-EOVERFLOW`. [cdc-acm.c v6.17, lignes 510–542](https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/usb/class/cdc-acm.c).

**Second incident, doublon `0e` (index 21).** Voir lignes 162–175 :

| Temps | Événement EP2 IN |
|---|---|
| `7345122.144318` | Premier `Short Packet`, reliquat 1023 |
| `.144320` | Premier giveback : un octet |
| `.144321` | TD suivant : `USB Transaction Error`, reliquat 1024 |
| `.144323` | Reset Endpoint, `t:c` |
| `.144411` | URB en erreur rendue vide |
| `.144426` | Second `Short Packet`, reliquat 1023 |
| `.144428` | Second giveback : un octet |

Le doublon est livré par deux URB différentes, séparées de **108 µs**, autour d’une erreur et d’un reset. Ce n’est pas une seule lecture Python interprétée comme deux transactions.

**Sonde EP0 ultérieure.** Elle commence après le doublon, à `7345123.158863`, puis subit `USB Transaction Error` sur l’endpoint xHCI 1 à `.158944`, suivie d’un reset. Le résultat indique `Errno 71 / Protocol error` ; `echo/fpga.txt` est vide. Cette erreur EP0 ne peut pas avoir déclenché le doublon antérieur et prive B de son instantané FPGA. Voir lignes 177–185.

## Interprétation et limites

`t` signifie **TSP=0** ; `T` signifierait TSP=1. Linux n’active TSP que pour `EP_SOFT_RESET` ; les resets observés sont donc durs. Le chemin dur marque l’effacement du toggle. [Décodage et bit TSP dans xhci.h v6.17](https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/usb/host/xhci.h), [construction du reset et traitement dans xhci-ring.c](https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/usb/host/xhci-ring.c), [contrat d’effacement dans xhci.c](https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/usb/host/xhci.c).

Le scénario « premier DATA0 accepté par l’hôte, ACK non reconnu côté carte, reprise après effacement du toggle hôte, second octet accepté » concorde avec A et avec la séquence de récupération de B. **C’est une explication étayée du doublon, pas encore une preuve de la cause initiale.** Aucune de ces captures ne mesure le signal D+/D−, le PID réellement reçu par l’hôte ou les caractéristiques électriques de l’ACK. `USB Transaction Error` ne départage pas à lui seul un défaut de réception, d’émission ou de timing. L’épuisement des retries logiciels n’est pas établi.

Les instances de trace signalent zéro perte et zéro overrun, sans troncature ni erreur de nettoyage. USBmon était indisponible ; le statut numérique des giveback n’est pas imprimé. Les événements TRB n’identifient pas le contrôleur PCI, donc le filtre par slot seul n’exclut pas théoriquement un même slot sur un autre contrôleur ; les URB sont, elles, filtrées par `3-7` et la séquence concorde. Les références Linux sont celles de l’amont v6.17, à distinguer du noyau Ubuntu installé.

La capture B fournit désormais le code d’erreur manquant. La prochaine preuve utile doit localiser l’échec de transaction et l’ACK autour de cette erreur ; changer la logique FIFO uniquement pour masquer le doublon ne serait pas justifié par ces données.
