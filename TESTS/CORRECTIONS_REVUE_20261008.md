# Corrections de la revue contradictoire — 8–9 octobre 2026

Suivi des cinq défauts reproduits dans
[`REVUE_CONTRADICTOIRE_20261008.md`](REVUE_CONTRADICTOIRE_20261008.md).
Les preuves historiques et la référence matérielle C22 sont conservées.

**Les cinq défauts reproduits sont corrigés et C37 est qualifié sur carte.**
Le FPGA passe le timing sans violation setup/hold, marge minimale +0,071 ns.
Les tests logiciels, simulations, audits CDC, USB, GPU et stockage passent.
ORBITAL R6 est restauré et tourne automatiquement sur C37 après son endurance.
L'archive C22 reste intacte ; la nouvelle référence est
[`console_gpu_sdusb_guard_800`](../bitstreams/console_gpu_sdusb_guard_800.md).

Les limites non résolues sont explicites en fin de document : attente MMIO
SPI si le périphérique se bloque, course lors de la restitution volontaire
du disque, écritures SD physiques non qualifiées. Ce résultat ne constitue
pas une preuve d'absence universelle de défauts.

## F1 — Erreur de programmation SD après acceptation des données

Le pilote attend la fin d'occupation puis envoie CMD13 et consomme les deux
octets R1/R2. Un statut non nul donne `SD_REJECTED`, jamais `SD_OK` ; une
absence de réponse donne `SD_TIMEOUT` et invalide l'initialisation de la carte.
Le jeton `05` d'acceptation des données ne suffit plus à déclarer l'écriture
réussie. Le plancher de réduction de fréquence est aussi borné à 400 kHz.

Le modèle accepte maintenant le CRC et les données tout en simulant une
programmation ratée : ancien contenu conservé et R2=04. Les écritures d'un
et de deux blocs échouent correctement. Une écriture suivante sans injection
réussit et se relit exactement. Le test intégré emploie le vrai `sd_write()`
comme backend du vrai firmware MSC : l'échec SD remonte par un CSW d'échec et
le sense SCSI `03/0C/00`, sans incrémenter le nombre de blocs écrits.

## F2 — CMD25 terminé sans jeton STOP

Le pilote contrôle l'attente qui précède STOP. Si elle expire, il renvoie
`SD_TIMEOUT`, invalide `card.ready` et refuse les accès suivants jusqu'à un
`sd_init()` explicite. Il n'annonce plus une réussite après la seconde attente.
Quand CMD25 a été accepté, son abandon utilise le jeton STOP d'écriture,
y compris après refus d'un bloc ; CMD12 reste réservé à l'arrêt d'une lecture.

Le contre-exemple historique reste couvert : busy dépasse la première attente,
puis retombe avant l'ancienne limite cumulée. Le test vérifie le timeout,
l'interdiction de nouveaux accès, puis une réinitialisation et une relecture
exacte après reprise. Un timeout n'implique pas une écriture atomique : certains
blocs peuvent déjà être programmés ; le pilote signale précisément l'échec.

## F3 — Champs CBW/CDB incohérents exécutés comme une écriture

Le firmware vérifie LUN=0, les bits réservés des flags, la longueur CDB
complète (sans masquer ses bits hauts), sa plage 1…16 et la longueur attendue
des opcodes implémentés. Une commande refusée n'atteint pas le backend disque.
Les opcodes inconnus continuent de produire une réponse SCSI d'opcode illégal.

Les mutations longueur CDB courte, flags réservés, longueur avec bits réservés
et LUN incorrect verrouillent le transport. Les tests vérifient l'absence de
CSW de succès, l'absence d'écriture et la réussite d'une commande normale après
reset BOT. Le choix de refus est défensif : la distinction normative entre
CBW invalide et CBW non « meaningful » reste celle du rapport de revue.

## F4 — Resynchronisation libre après CBW invalide

Le firmware ne recherche plus une nouvelle signature dans les octets reçus.
Un en-tête invalide, une perte RX ou une commande interrompue hors reset hôte
place le transport en quarantaine jusqu'au reset BOT ou du bus.

Le nouveau `usb_msc_guard.v` suit les frontières de paquets CRC-valides dans
le domaine USB : CBW de 31 octets et signature, longueur de données annoncée,
phase CSW. Un paquet OUT prématurément court verrouille aussi le transport.
Les retransmissions sans ACK ne font pas avancer une seconde fois les phases.
Le port AHB expose HALT au bit 10 du statut, une demande de HALT au bit 6 du
contrôle et l'ABI du garde à l'adresse +0x28. USBDISK R4 exige ABI=1 au démarrage,
ce qui interdit de lancer silencieusement ce firmware sur C22 sans garde.
Le binaire C4b annonce READY uniquement après ce contrôle et l'initialisation
du disque. Il fait 20 304 octets et a été qualifié sur C37.

Le contrôleur Gowin ne fournit pas de commande utilisateur de STALL. Le wrapper
force donc le NAK d'EP1 et remplace uniquement son PID de handshake par STALL
à l'interface UTMI. GET_STATUS pour EP1 IN/OUT reflète HALT, avec CRC16 corrigé.
La décision reste stable si TXREADY retarde l'octet PID. Les données bulk,
le CDC et les netlists fournisseur ne sont pas réécrits. CLEAR_FEATURE seul
ne lève pas le verrou ; la récupération testée effectue reset BOT puis
CLEAR_FEATURE sur les deux directions.

Le modèle officiel du contrôleur Gowin HS 3.3 est utilisé pour les simulations
de paquets. Il vérifie STALL IN/OUT, GET_STATUS sur 01 et 81, CLEAR_FEATURE
insuffisant, CDC utilisable pendant le verrouillage et récupération. Les cas
incluent mauvaise signature, paquets de 0/30/32 octets, demande logicielle de
HALT et données prématurément courtes. Des essais complémentaires injectent
un CRC faux et une retransmission de CBW après perte d'ACK.

La partie du banc consacrée au débit brut des FIFO désactive explicitement le
garde car ses octets ne constituent pas des commandes BOT. Elle ne constitue
donc pas une validation SCSI sous garde ; cette validation est couverte par
les tests firmware, puis par les transferts et erreurs injectées sur C37.

## F5 — Faux PASS du débit ORBITAL

Le débit est calculé avec la différence des compteurs entre deux mesures et
le temps réellement écoulé, qui englobe les échanges série. Chaque échantillon
doit montrer une animation active, une progression du compteur et l'absence
de nouveaux underflows. Les contrôles du validateur utilisent des exceptions
explicites et restent actifs sous `python3 -O`.

Sept tests couvrent le témoin, un PC retardé (300 images en 30 s), un compteur
figé, l'animation arrêtée, une erreur signalée, un underflow et l'absence
d'acquittement de reprise. Le fichier PASS n'est écrit qu'après la confirmation
de reprise d'ORBITAL. Tous passent
avec et sans `-O`. Cela corrige l'outil ; les 54,83 images/s historiques de C22
restent une mesure distincte, dont la durée réelle était déjà cohérente.

Le calcul de débit corrigé a également été testé sur C22 resté chargé :
**51 poses exactes, 28 543 images entre les deux échantillons, 520,830962 s
réelles, 54,802810 images/s**, 3 264 octets d'écho exacts. Zéro underflow,
erreur et commande rejetée. ORBITAL a été relancé. Preuve
`c22_orbital_validator/`, avec empreinte de l'outil utilisé. Cette mesure
précède le dernier durcissement de l'écriture du PASS après acquittement ;
elle ne qualifie pas le nouveau FPGA USB.

## Chargement et preuves

Les chargeurs ILM et ORBITAL attendent désormais une ligne de pause complète,
ou un état USBDISK `SERVING=0`, avant J-Link. Absence d'acquittement, ligne
incomplète et disque encore servi font échouer le chargement. Cela remplace
l'attente arbitraire ; la course préexistante de restitution du disque au
matériel pendant un nouveau CBW reste distincte et non résolue par cet ACK.
Les vérifications de bornes ILM, empreintes de ressources, vitesse HS et
résultat J-Link des deux chargeurs utilisent également des exceptions
explicites et restent actives sous `python3 -O`.

Preuves dans [`corrections_20261008/`](corrections_20261008/) :

| Preuve | Résultat / périmètre |
|---|---|
| `storage_faults_r2/result.json`, `sd.log`, `msc.log` | F1–F4 en modèles, ASan/UBSan actifs |
| `sd_host.log` | SD/FatFs, CRC/retries, fichier relu indépendamment par mtools |
| `msc_host.log` | 1 631 987 contrôles MSC, hôtes immédiat/irrégulier/lent |
| `msc_port_clocks.json` | Trois couples d'horloges/phases, purge et HALT avec horloge arrêtée, compteur bouclé après 68 097 octets |
| `usb_guard_controller_r5.json` et `.log` | Modèle officiel HS, 23 paquets IN, 4 retransmissions, erreurs et récupération |
| `orbital_validator_r2.log`, `orbital_validator_r2_optimized.log` | Sept tests du validateur dans les deux modes Python |
| `c22_orbital_validator/result.json` | Débit réel corrigé et 51 poses sur la carte C22 |
| `load_identity_r3.log`, `load_identity_r3_optimized.log`, `host_tools_ax15.log` | Sept tests chargeurs, avec/sans optimisation ; refus des écritures d'essai hors DDR |
| `usbdisk_c4b_manifest.json`, `usbdisk_c4b_sources.tar.gz` | Sources et binaire ILM R4 figés ; entrée 0xA000000C, READY après initialisation |

`storage_faults_r1` conserve l'échec de LeakSanitizer dans le bac à sable ;
la relance r2 hors bac à sable passe sans désactiver les sanitizers.
`disk_faults_gate.log` conserve l'absence locale de PyUSB ; les tests passent
sur ax15, où la dépendance est déjà installée, sans toucher au matériel.
Les simulations r1 et variantes intermédiaires sont conservées avec leurs
résultats ; r5 est celle qui correspond au RTL final du garde à ce stade.

## Timing et qualification matérielle

| Variante | Résultat | Décision |
|---|---|---|
| C23 | Licence inaccessible dans le bac à sable | Compilation non utilisable |
| C24 | 33 extrémités setup, minimum −1,728 ns | Refusée |
| C25 | Placement 0 / routage 1, sources antérieures au contrôle OUT court | Arrêté après plus de quatre heures ; seul PID 514798, dossier vérifié |
| C26 | 62 extrémités setup, minimum −2,364 ns | Refusée |
| C27 | 33 extrémités setup, minimum −1,463 ns | Refusée ; GPU positif, retours AHB/USB et un chemin PHY négatifs |
| C28 | Sources du garde C27, placement AHB/UTMI rapproché | Refus CT1094 : deux bascules à CE différents dans une même paire |
| C29 | Même RTL, bascules séparées selon leurs CE | 27 extrémités setup, minimum −1,141 ns ; refusée |
| C30 | Netlist C29, rapprochement des LUT et de deux contrôles GPU | Échec avant routage : `add_file -type vg` non accepté par V1.9.12 |
| C31 | Même netlist et placements que C30, détection du type par extension | 5 extrémités setup, minimum −0,747 ns ; GPU/AHB positifs, refusée |
| C32 | Même netlist ; reset EP1 près des FIFO et seconde branche PHY regroupée | 10 extrémités setup, minimum −0,921 ns ; refusée |
| C33 | Même modification locale, routage incrémental depuis le fichier `.pr` C31 | 2 extrémités setup CEA de la FIFO USB, minimum −3,711 ns ; GPU/PHY positifs, refusée |
| C34 | Même modification locale, placement incrémental depuis le fichier `.p` C31 puis nouveau routage | Mêmes 2 violations CEA et marges que C33, refusée |
| C35 | Routage incrémental C33 ; une seule LUT CEA rapprochée des BSRAM EP1 | Refus CT1005 : emplacement R64C74 non disponible pour cette LUT |
| C36 | Même changement unique, emplacement LUT R66C72 utilisé par les FIFO | Arrêté après validation du timing C37 ; seul PID 694628, dossier vérifié |
| C37 | Même changement unique depuis C34, réutilisation du `.p` seul | **Zéro setup/hold, marge +0,071 ns**, audits et qualification carte passés |

C29 est lancé depuis l'instantané C28 pour éviter de régénérer les IP. Le
premier script de reroutage a néanmoins laissé les sources RTL dans le projet
Tcl : Gowin a automatiquement refait la synthèse. Ce fait et les empreintes
effectives sont conservés dans `c29_resynthesis.json` ; C29 ne doit pas être
présenté comme un routage seul de la netlist C28. La version suivante du script
utilise explicitement une entrée `vg` sans RTL et vérifie son empreinte après
l'exécution. La syntaxe V1.9.12 est `add_file {chemin.vg}`, sans `-type vg`.
C31 confirme « Skip synthesis, because there is only one netlist file in this
project ». Aucun changement manuel de netlist n'est effectué.

C33 utilise `set_option -inc_pnr` avec une copie du `.pr` C31 dont
l'empreinte est incluse dans le manifeste. La procédure est documentée
dans le manuel installé SUG100-4.4.3E, §4.3, p.39 (Arora V). L'incrémental
réutilise placement et routage ; il ne dispense pas du contrôle complet
des marges ni de la validation sur carte.

L'audit MSC étendu exige 84 liaisons Gray, cinq liaisons de purge et cinq
liaisons HALT, chacune directement Q→D et sous 6,25 ns. Ce budget de routage
ne prouve pas le MTBF et ne remplace pas l'analyse globale setup/hold. C26
passe cet audit mais échoue au timing global : il reste refusé.

Le test physique `check_usb_disk_faults.py`, passé sur C37, impose HS,
USBDISK R4, `MEDIA=DDR`, `SERVING=1` et une capacité exacte de 32 Mio avant toute
écriture. Il vérifie neuf cas, HALT et absence de modification du secteur DDR
témoin. Aucune écriture SD physique n'est requise. Il passe maintenant les neuf cas sur C37, sans erreur de nettoyage.

Les attentes MMIO non bornées de `sd_ae350.c` restent un risque statique identifié
dans la revue. Les corrections de F1/F2 bornent les attentes de protocole SD,
pas un contrôleur SPI matériel qui ne répondrait plus. Ce document ne prétend
pas démontrer l'absence de tout défaut possible.

### Audits C37 avant chargement

SHA-256 du bitstream : `6f47a8cdab5857a0b652f791ff61fbed9a26c3c7ba7f4f30de01da95f0c076e2`.
Les 94 liaisons MSC passent : Gray 1,269 ns au maximum, purge 0,679 ns,
HALT 4,695 ns, toutes sous 6,25 ns. Les 44 liaisons Gray internes au PHY
passent, maximum 0,858 ns, à partir du modèle officiel exporté de ce build
(`fifo_rx_pkt` pour le PHY HS3.5 Advance). Les 12 liaisons AHB et les
16 liaisons des commandes GPU passent également : maxima Q+route
2,364 ns et 1,448 ns. Cela ne prouve pas le MTBF analogique.

Le nouvel audit SDF PHY refuse un chemin absent (43/44) et des unités
incorrectes (1 ps au lieu de 1 ns) ; le témoin 44/44 passe. Preuves
`c37_*cdc*.json`, `c37_phy_gray_sdf.json`, `phy_gray_audit_negative.json`.

### Qualification physique C37 : stockage et chargeur

Les trois rechargements SRAM ont négocié 480 Mbit/s et passé 100 séries
chacun, soit 1 632 300 octets exacts. La suite GPU complète et 300 requêtes
EP0 passent. USBDISK R4/C4b a validé son ABI matériel puis démarré.
Deux lectures SD de 8 Mio sont identiques, sans écriture SD. Sur DDR,
8 Mio écrits/relus passent (5,58/7,19 Mio/s, CRC PC/firmware A8B03134).
Les neuf cas malformés donnent STALL, ne modifient pas le secteur témoin
et récupèrent après reset BOT. Douze interruptions READ10 récupèrent
aussi avec un contenu identique. Zéro timeout/perte/resynchronisation.
Les erreurs SCSI provoquées et les resets attendus sont comptés séparément.

La première restauration ORBITAL s'est arrêtée **avant J-Link** : le
chargeur exigeait le début de ligne USBDISK, mais printf émet parfois
CR-LF-CR. Il normalise maintenant uniquement les CR en bord de ligne,
tout en exigeant une ligne complète et le préfixe exact. Sept tests passent
avec et sans `-O`, dont CR-LF-CR et refus d'un préfixe parasite. La relance
`c37_orbital_load_r2` utilise ce correctif. L'instantané fonctionnel r4
conserve ce changement et les outils d'audit ; les preuves r3 restent
historiques. Le firmware C4b et le RTL C37 n'ont pas été modifiés.

### Endurance finale et archive

La restauration complète ORBITAL a pris 576,3 s, avec relecture J-Link des
5 781 728 octets de ressources et du programme. Le chargeur a utilisé le
FPGA C37 déjà présent (`fpga_reloaded=false`). La mention R31 du programme
désigne son ABI d'origine, pas une reconfiguration du FPGA.

Les **51 références passent**, puis **28 546 images sont produites entre
les compteurs 7 et 28 553 en 520,827593 s réelles : 54,808924 images/s**.
Échos USB : 3 264 octets exacts. Zéro underflow, erreur ou rejet.
Dessin maximal 13 081 009 cycles AE350, soit 16,351 ms ; composition
maximale 1 021/2 556 cycles par ligne. Le redémarrage automatique est
acquitté avant l'écriture du PASS. Le périphérique reste à l'adresse 3:58,
480 Mbit/s, configuration 1 et trois interfaces.

Preuves : `corrections_20261008_c37_orbital_check/`,
`corrections_20261008_c37_orbital_load_r2/`, `c37_final_usb.json`.
Les tentatives arrêtées avant programmation/J-Link restent conservées :
PATH du programmateur lors du premier rechargement, puis CR-LF-CR dans
l'acquittement de restitution. La seconde erreur a son correctif et sa
régression ; aucune de ces tentatives n'est comptée comme une qualification.

Archive finale : bitstream, SHA-256, 125 empreintes de sources et manifeste
de qualification sous `bitstreams/console_gpu_sdusb_guard_800.*`.
`c37_sources.tar.gz` contient également la netlist et la référence de
placement incrémental ; SHA-256
`cf2cb2632df4448b3a167f76b6bebfab785d8cde78481b19fc9db833ec6f4bb3`.
Le firmware stockage séparé est `usbdisk_c4b.bin` (20 304 octets).

### Limites maintenues

- F1/F2 sont vérifiés avec injection de fautes SD en modèle ; la carte SD
  physique a seulement été lue. Ses écritures et son retrait restent à qualifier.
- La restitution volontaire du disque pendant l'arrivée d'un CBW peut
  encore nécessiter un reset BOT ; l'acquittement du chargeur ne résout pas
  cette course préexistante.
- Les attentes MMIO du SPI AE350 restent non bornées si ce périphérique
  matériel cesse de répondre, même si les attentes du protocole SD sont bornées.
- Les audits de routage et tests numériques ne prouvent pas le MTBF
  analogique ni la conformité exhaustive aux treize cas BOT.
- ORBITAL et USBDISK utilisent des programmes ILM distincts ; les chargements
  SRAM/ILM/DDR sont volatiles et aucun démarrage SD autonome n'est ajouté.
