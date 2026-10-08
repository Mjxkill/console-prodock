# Carte SD et disque USB — fiche de validation

Contrat : `ARCHI/SD_USB_DISQUE.md`. Preuves : `TESTS/sd_usb_20261005/`.
Reprise et correctifs du 7 octobre : `TESTS_REPRISE_20261007.md`, avec les
preuves nouvelles dans `reprise_20261007/`. Les tableaux ci-dessous décrivent
l'état historique du 5 octobre, pas la validation complète actuelle.
Cette fiche sépare strictement ce qui est prouvé **en simulation ou sur PC**
de ce qui est prouvé **sur la carte**. Rien n'est écrit en flash : tous les
chargements sont en SRAM et par J-Link, perdus à l'extinction.

La revue postérieure a révélé cinq défauts non couverts par la qualification
C22. Leur correction et leurs nouveaux tests sont suivis dans
[`CORRECTIONS_REVUE_20261008.md`](CORRECTIONS_REVUE_20261008.md).

## Qualification C37 — 9 octobre 2026

La version corrigée passe trois rechargements HS, la suite GPU, 300 requêtes
EP0, 2 × 8 Mio de lectures SD identiques et 8 Mio d'écriture/lecture DDR.
Les neuf commandes malformées sont bloquées jusqu'au reset BOT sans écriture
parasite ; douze lectures interrompues récupèrent un contenu identique.
ORBITAL est restauré : 51 références exactes, 520,828 s à 54,81 images/s,
zéro erreur/underflow/rejet. [Rapport et limites](CORRECTIONS_REVUE_20261008.md) ·
[Archive C37](../bitstreams/console_gpu_sdusb_guard_800.md).

Les paragraphes C22 et du 5 octobre ci-dessous sont historiques.

## Qualification C22 — 8 octobre 2026

Le nouveau FPGA C22 passe le timing complet, les audits de synthèse et les
89 trajets CDC MSC vérifiés. Sur carte : trois rechargements HS, 300 requêtes
EP0, suite GPU complète, SD reconnue et deux lectures de 8 Mio identiques,
douze reprises après interruptions READ10, puis 8 Mio écrits/relus sur DDR
avec CRC exact. Aucun timeout, perte ni resynchronisation. Aucune écriture
sur la SD physique. ORBITAL est ensuite restauré et confirmé fluide.

Programme de stockage C3 : `reprise_20261007/usbdisk_c3.bin`, sources et
commande dans `usbdisk_c3_manifest.json` et `usbdisk_c3_sources.tar.gz`.
`d` sélectionne le disque DDR sans retirer la SD ; `m` retrouve la SD.
Le test par défaut reste en lecture seule pour la SD, sans montage.

[Détail des mesures et limites](TESTS_REPRISE_20261007.md) ·
[Archive C22](../bitstreams/console_gpu_sdusb_800.md).

## 1. État au 5 octobre 2026

| Élément | Simulation / PC | Sur carte |
|---|---|---|
| Pilote SD en mode SPI + FatFs | PASS (modèle de carte SDHC) | **à faire : aucune carte insérée** |
| Broches SD, SPI et GPIO de l'AE350 | — | voir § 4 |
| Descripteurs composites, Get Max LUN, Bulk-Only Reset | PASS (contrôleur officiel) | voir § 4 |
| EP1 en mode paquet validé, port `usb_msc_port` | PASS (banc + contrôleur officiel) | voir § 4 |
| Lecteur sans carte servi par le matériel | PASS (banc + contrôleur officiel) | voir § 4 |
| Firmware Bulk-Only/SCSI | PASS (modèle d'hôte, UBSan + ASan) | voir § 4 |
| Port série inchangé (régressions CDC et EP0) | PASS, journaux identiques | voir § 4 |

## 2. Simulations et essais sur PC

Commandes de reproduction (les chemins d'Icarus Verilog sont ceux de
`TESTS_GPU_L12.md`) :

```sh
python3 TESTS/test_sd.py                 # pilote SD + FatFs, image FAT32 relue par mtools
python3 TESTS/test_usb_msc.py            # firmware du disque contre un modèle d'hôte
python3 tools/check_usb_msc_sim.py --output /tmp/usb_disk.json   # contrôleur officiel HS 3.3

verilator --binary --timing -Wno-fatal --top-module usb_msc_port_tb --Mdir /tmp/console_usb_msc \
  TESTS/rtl/usb_msc_port_tb.sv tang/rtl/usb/usb_msc_port.v tang/rtl/usb/usb_msc_empty.v \
  tang/rtl/usb/sync_fifo/usb_fifo.v tang/rtl/usb/sync_fifo/sync_tx_pkt_fifo.v \
  tang/rtl/usb/sync_fifo/sync_rx_pkt_fifo.v tang/rtl/board/ddr_dcfifo.v tang/rtl/board/cdc_word.v
/tmp/console_usb_msc/Vusb_msc_port_tb
```

### Pilote SD (`sd_host.txt`)

Image FAT32 de 64 Mio créée par `mkfs.vfat`, remplie par mtools, lue et écrite
par `sd.c` + FatFs à travers un modèle de carte SDHC octet par octet, avec
erreurs de CRC injectées : 7 blocs relus, 1 réduction de fréquence, fichiers
identiques ; le fichier écrit par le firmware est relu identique par mtools,
indépendamment de FatFs.

### Port du disque (`usb_msc_port_tb.txt`)

Horloges 80 MHz et 60 MHz indépendantes, modèle de contrôleur au niveau des
signaux de `usb_fifo`. Vérifié :

- lecteur sans carte : INQUIRY (36 et 255 octets demandés), INQUIRY EVPD,
  TEST UNIT READY, REQUEST SENSE, MODE SENSE, READ et WRITE de 1 024 octets,
  octets parasites avant une commande, reprises sur ACK perdu ;
- un octet écrit sans avoir le disque est refusé et signalé ;
- disque demandé au milieu d'une commande de l'hôte : accordé seulement après
  son état, compteurs alignés ;
- réception de 8 230 octets en 18 paquets plus vite que le firmware ne lit
  (contre-pression), sans perte ;
- émission de 38 410 octets en 75 paquets avec 27 ACK perdus rejoués : les
  seules longueurs vues par l'hôte sont celles validées (512… puis le reste),
  jamais de paquet court pendant qu'un bloc s'écrit ;
- purge, reset du bus (le firmware garde le disque), reset Bulk-Only,
  saturation à 3 584 octets signalée sans débordement ;
- restitution du disque sans purge, puis chien de garde : le matériel répond
  de nouveau en lecteur sans carte.

### Contrôleur officiel Gowin HS 3.3 (`usb_disk_hs33.json`, `.log`)

Le modèle de simulation est exporté par le flot officiel Gowin
(`tang/impl/gpu_usb_controller33_hs_msc_model_r1`, même netlist de contrôleur
que le modèle des essais précédents, ROM du descripteur composite). L'hôte
agit au niveau UTMI ; aucun signal interne du fournisseur n'est forcé.

- descripteurs lus par l'hôte et décodés par l'outil : périphérique EF/02/01,
  `359f:2011`, configuration de 98 octets, association d'interfaces CDC,
  interfaces 0, 1, 2, endpoints 0x83, 0x02, 0x82 inchangés, EP1 OUT et IN bulk
  de 512 octets ;
- Get Max LUN : 1 octet nul, identique après un ACK perdu ; GET_LINE_CODING du
  port série intact avant et après ; Bulk-Only Reset vu par le port ;
- lecteur sans carte interrogé à travers le vrai contrôleur, ACK perdu compris ;
- prise de main, puis EP1 IN : NAK tant que rien n'est validé, paquet de 512
  rejoué à l'identique après ACK perdu pendant que le port série émet, 1 037
  octets écrits lentement sortis en 512 + 512 + 13 ;
- EP1 OUT : 12 paquets de 512 envoyés sans que le firmware lise : 10 NAK et
  2 NYET, puis tout est livré sans perte ni doublon ;
- restitution du disque, lecteur sans carte de nouveau.

Résumé du journal : `IN 1562 bytes/17 packets, 4 replays, 134 NAK; OUT 6175
bytes, 10 NAK, 2 NYET; serial 4 bytes`.

### Firmware du disque (`usb_msc_host.txt`)

`usb_msc.c` compilé pour le PC sous UBSan et ASan, contre un modèle du port et
d'un hôte qui découpe les octets validés en paquets comme le matériel (512 puis
64 octets) et lit à trois cadences. 2 947 173 contrôles : toutes les commandes,
60 écritures et lectures aléatoires de 1 à 128 blocs comparées à une copie,
résidus, complément de zéros, erreurs (hors capacité, opcode inconnu, sens ou
longueur incohérents, défauts du support, protection en écriture, support
absent puis inséré), resynchronisation, reset du bus en cours de lecture,
hôte qui cesse de lire (abandon après délai), disque repris par le matériel
avant et pendant une commande.

Le formateur FAT16 du disque en DDR est compilé à part sur PC : `fsck.vfat`
ne signale rien, mtools lit `LISEZMOI.TXT`.

### Non-régression du port série

- Cinq bancs existants (`usb_in_packet_tb`, `usb_stream_tb`, `usb_cdc_fifo_tb`,
  `usb_uart_config_recovery_tb`, `usb_control_diag_tb`) : journaux identiques,
  octet pour octet, entre les sources modifiées et celles du dernier commit.
- Contrôleur officiel HS 3.3, options `--bulk-blocks 8 --interleave-out
  --interrupt-polls --sof-context --cdc-context` : PASS
  (`usb_cdc_regression_hs33.json`).
- Reprise EP0, cinq cas (`normal`, `retry7`, `retry32`, `preempt_wait`,
  `preempt_sent`) : PASS (`usb_ep0_recovery_*.json`).

### Limites des simulations

Hôte idéal : ni PHY, ni câble, ni pilote Linux ou Windows réel. Le chemin
SD est vérifié contre un modèle de carte, pas contre une carte. Aucune preuve
de timing physique.

## 3. Builds FPGA

À compléter : voir § 4.

## 4. Essais sur carte

À compléter.
