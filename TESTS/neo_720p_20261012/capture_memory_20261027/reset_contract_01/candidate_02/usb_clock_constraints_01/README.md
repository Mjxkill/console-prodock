# Horloges USB et capture UTNA, sans nouveau routage

Audit hors carte du 27 octobre 2026. Les anciennes preuves de provenance
restent dans `../usb_actual_comparison_01/`. Aucun RTL, CST ou SDC modifié.

## Compatibilité des contraintes avec le PHY actif

**Aucune contradiction de fréquence n'est trouvée entre l'ancien PHY actif
et le SDC Neo.** Le nom de macro `V_120` ne permet pas de déduire la fréquence
du PHY ancien. Les primitives routées apportent une preuve plus précise :

| Chemin réel, vérifié sur les deux cartes | Fréquence nominale | Déclaration STA |
|---|---:|---|
| PLL F : 50 ×24 /25, CLKOUT0 → clk48 | 48 MHz | CLK_48M |
| PLL B : 48 ×20 /16, CLKOUT1 → phy_clk | 60 MHz | PHY_CLKOUT |
| PLL B : 48 ×20 /1, CLKOUT0 → fclk_960m | 960 MHz | fclk_960M |
| fclk_960m → DHCE → CLKDIV DIV_MODE="8" → sclk | 120 MHz | sclk, période 8,333 ns |

`clock_audit.json` conserve les cellules, leurs paramètres/pins et lignes
du `.vo`, ainsi que les horloges effectivement reconnues dans le `.tr`.
Les sources SDC sont les fichiers réellement chargés par les deux Tcl :
Neo `source/tang/boards/neo/neo.sdc`, Pro Dock
`source/diagnostics/timing_reports.sdc`.

Le SDC Sipeed associé au binaire ancien contient déjà, lignes 9–15,
ces quatre horloges et le même `set_clock_groups -asynchronous` entre
PHY_CLKOUT/sclk/fclk_960M. Le nom de net sclk correspond exactement à la
sortie du CLKDIV dans les deux `.vo`. La fréquence déclarée 120,005 MHz
résulte de l'arrondi 8,333 ns, pas d'un deuxième mode de réception.

Le mode C28/V_120 change réellement la logique : par exemple, la FIFO RX
devient `fifo_rx_pkt`, avec mémoire SDPB 16 bits, contre `fifo_rx` / 8 bits
dans le vieux PHY. Dans les deux cas, la génération sclk reste /8.
La différence de version/mode n'établit donc pas une mauvaise période SDC.

Les groupes asynchrones excluent l'analyse synchrone des traversées internes
60/120/960 MHz. C'est conforme au SDC fourni avec ce vieux PHY ; cela ne
constitue pas une preuve universelle de CDC. Une contrainte de délai ajoutée
sans revoir cette priorité peut ne pas s'appliquer. Aucun changement
d'exception n'est proposé dans ce travail.

Contrôle indépendant des fichiers routés : les 44 liaisons Q→D des pointeurs
Gray (premiers et seconds étages, FIFO RX et TX) sont toutes présentes dans
les SDF. Maximum de fil : **0,839 ns sur Neo**, **1,043 ns sur G22r0**,
inférieur à 8,333 ns dans les deux. Les bornes ne comprennent pas un calcul
complet C2Q/setup/hold/MTBF et ne prouvent pas l'analogique ou les resets.
Les domaines PHY_CLKOUT et sclk ne comptent pas d'endpoints setup négatifs
dans le résumé STA Neo ; le **timing global R21r2 demeure FAIL**.

Le contrôle ne conclut pas qu'une configuration IP B est officiellement
portable sur C. Cette question de support reste distincte de la cohérence
des fréquences et des noms de contraintes observés ici.

## Capture fraîche disponible sur le bitstream existant

Les dernières lectures root (`video_readonly_20261027_155600`) donnent sur
R19 et R21r2 : ID UTNA, statut zéro, séquence zéro. Elles prouvent seulement
que le côté AHB de l'observateur a quitté son reset ; aucun snapshot n'a été
demandé, et aucun compteur USB vivant n'a été lu.

Le module `usb_idle_trace` ne pilote aucun signal du datapath USB. La commande
à `0xe900200c` modifie uniquement son armement, ses compteurs et ses FIFO de
diagnostic. Ce serait une expérience nouvelle, distincte du relevé en lecture
seule déjà terminé. Aucun accès à MSC, SD, DDR ou moteurs GPU n'est requis.

Protocole borné proposé, à intégrer au contrôleur root et non exécuté ici :

1. Vérifier carte/FS/ancre/parking, ID `0x55544e41`, statut zéro et séquence q.
2. Écrire **1** (clear+arm, filtre adresse USB zéro) à +0c. Attendre au plus
   100 lectures espacées de 2 ms : statut zéro, séquence q+1 modulo 2^32.
   Cette première réponse contient l'état **avant** effacement/armement.
3. Attendre 200 ms. Écrire **6** (snapshot+disarm), attendre q+2 selon les
   mêmes bornes. Lire 32 mots à `0xe9002040` deux fois, avec statut/séquence
   encadrant les lectures. Exiger deux banques identiques, en-tête
   `[0x55544e41,1,6]`, aucune nouvelle commande concurrente.
4. Attendre 100 ms, écrire **2**, attendre q+3 et lire deux fois. Le bit armed
   doit être zéro et ticks doit valoir **ticks_capture6 +1**, modulo 2^32.
   Au front de6, la banque conserve l'ancien état tandis qu'un dernier tick
   est incrémenté avant que la nouvelle valeur armed=0 prenne effet.
5. Une dernière commande2 après 100 ms doit retourner ticks strictement
   inchangé et armed=0. Elle constitue un témoin de l'arrêt du compteur.

Chaque commande, même sans bit1, renvoie une banque complète : la condition
RTL est `cmd_pop`, pas `command[1]`. Le bit1 est une convention d'interface.
Les bits inconnus ne doivent pas être utilisés. L'adresse cible (14:8) filtre
les tokens IN EP2/EP3 ; elle n'affecte ni ticks, ni SOF, ni rx_error.

Prévoir arrêt à la première incohérence/expiration, sauvegarde des mots bruts
et restauration root du FS prévu. Ne pas empiler une commande en cas de busy
persistant. Le statut bit1 indique un rejet ; un compteur de séquence inchangé
interdit d'interpréter la banque comme fraîche. L'armement réussi suivi d'une
erreur doit être désarmé dans la mesure du possible, sans envoi concurrent,
ou annulé par la restauration contrôlée. Aucun reset USB n'est nécessaire.

| Mot dans la banque | Adresse | Contenu |
|---:|---:|---|
| 0,1,2 | 2040,2044,2048 | ID, version1, commande acquittée |
| 3 | 204c | ticks PHY_CLKOUT pendant armed |
| 4–11 | 2050–206c | IN2/3, NAK2/3, DATA2/3, réponses manquantes2/3 |
| 12 | 2070 | réponses mal formées |
| 13 | 2074 | nombre de **cycles** RXERROR, pas nombre de paquets |
| 14 | 2078 | tokens IN invalides |
| 15,16 | 207c,2080 | bus resets observés, SOF |
| 17 | 2084 | cycles TXVALID sans TXREADY |
| 18,19,20 | 2088–2090 | dernier token, dernière réponse, latences max |
| 21–28 | 2094–20b0 | quatre événements récents |
| 29,30 | 20b4,20b8 | premier défaut |
| 31 | 20bc | armed bit10, pending bit9, adresse bits6:0 |

Il n'y a **aucun diag_board/PLL_LOCK** dans cette banque. Ces bits sont dans
`usb_diagnostic_data`, relié au seul transfert EP0 du module `usb_uart_config`.
Ils ne sont pas récupérables par cette fenêtre CPU sans modifier le design.
Des ticks positifs et une réponse fraîche prouvent une activité du domaine
USB pendant la fenêtre, pas la fréquence exacte du 960 MHz ni l'énumération.
Une fréquence estimée exige de borner aussi les latences de commande/JTAG.
SOF zéro ou RXERROR élevé ne localisent pas seuls la cause.

Le protocole est simulé sur **les sources figées exactes** R21r2, avec sa FIFO
réelle, Icarus quatre états : trois rapports/phases PASS, banque stable et
séquences contrôlées. Le témoin négatif qui exige l'égalité des ticks entre
6 et2 échoue comme attendu. `protocol_result.json` conserve sources et logs.
Ce test n'est pas une qualification du transport physique routé.

## Réutilisation propre de la configuration Pro Dock

Le générateur isolé existant
`n56r3_validation_20261021/usb_ip_candidate/generate_usb_neo.py` fait déjà la
transposition correcte : mêmes sources officielles non modifiées et mêmes
macros C28, projet explicite **GW5AST-138C / PBGA484A / C1/I0**, chemins locaux,
insertion de pads désactivée. Il conserve les endpoints HS et V_120.

Les deux résultats C générés sont archivés et hachés ; ils ne sont pas actifs
dans R21r2. Pour une intégration future, revalider leurs entrées/macros/outils
puis substituer uniquement ces deux IP dans une nouvelle copie Neo. Ne pas
copier le binaire B de G22r0 et ne pas retargeter seulement son en-tête.
Ne pas recopier aveuglément ses contraintes de broches ou ses placements.

Une nouvelle synthèse change les noms/optimisations de contrôle. Il faut
reconstruire les exigences de placement par fonction, vérifier la continuité
des corrections CPU/reset et des observateurs ajoutés après N56r9, puis
auditer les netlists avant tout routage. Une simple resynthèse du snapshot
ne garantit pas de conserver les modifications historiques effectuées
directement dans la netlist. Les IP ont des wrappers intégrés différents :
leur remplacement par découpage textuel sans audit des ports serait incorrect.

Les fréquences prévues et broches Neo restent inchangées. Vérifier ensuite
cibles SDC/CST, diviseurs, CDC, resets et timing, puis seulement démarrage et
énumération HS sur la Neo. Cet alignement est une expérience pertinente ; il
n'est pas encore démontré comme correction du problème USB.
