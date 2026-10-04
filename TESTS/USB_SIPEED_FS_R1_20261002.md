# USB FS dédié — témoin isolé r1 du 2 octobre 2026

**PASS audit préalable, compilation et timing ; FAIL énumération sur carte ensuite.**

Le témoin HS Sipeed intact a lui-même produit un doublon : 103 échos unitaires corrects, puis `70 → 7070` à l’index 103, avec une vitesse de 480 Mbit/s. Voir [résultat HS](usb_ax15_20261002/sipeed_reference_r1/result.json). Le présent témoin remplace la chaîne HS par une chaîne FS cohérente pour permettre une comparaison à **12 Mbit/s**. Il ne démontre ni une équivalence HS/FS ni la cause du défaut HS.

## Sources et modifications limitées

Dossier neuf : `tang/impl/usb_sipeed_fs_r1`. La référence `usb_sipeed_reference_r1` et les sources de production sont inchangées. `source/` conserve la référence Sipeed ; `project/` contient le témoin compilé. Les empreintes et origines sont consignées dans `sources.json`, le diff complet dans `changes.patch`, et la préparation reproductible dans `prepare.py`.

| Fichier ou composant | Modification / provenance |
|---|---|
| `project/src/TOP.v` | Activation de la branche FS déjà commentée dans le top Sipeed : `USB_SoftPHY_Top`, D+/D− sur `usb_term_dp_io` / `usb_term_dn_io`, pullup à 1. Suppression de l’instance PHY HS et de ses quatre ports. `HSSUPPORT=0`. Sortie PLL 960 MHz déconnectée. |
| `project/src/usb_ref.cst` | Suppression exclusive des contraintes HS : paire M21/M22 et entrées différentielles U21/V21 et T20/U20. Les contraintes CLK_IN, LED, UART, pullup et term_dp/dn sont conservées. |
| `project/src/usb_ref.sdc` | Suppression exclusive de `sclk`, de `fclk_960M` et du groupe asynchrone qui les concernait. Périodes 50/48/60 MHz et les deux faux chemins UART d’origine inchangés. Aucune nouvelle exception. |
| `project/usb_uart_loopback.gprj` | Retrait du PHY HS des entrées actives ; remplacement du contrôleur HS par la netlist FS officielle existante. 16 entrées actives. |
| PHY FS `src/usb_softphy/usb_softphy.v` | Netlist Sipeed intacte ; module `USB_SoftPHY_Top`. IPC : `usb_11_softphy`, version 1.0, `Clock_Frequency=60MHz`, `DisableIO=false`. |
| Contrôleur FS `src/usb_device_controller_fs/usb_device_controller.vg` | Netlist officielle générée antérieurement par Gowin V1.9.12 dans `gpu_l12_diag_r23_fs/usb_ip`, réutilisée sans modification ni régénération. |
| PLL, FIFO, UART, descripteur | Fichiers Sipeed conservés octet pour octet. Seule la valeur du paramètre `HSSUPPORT` de l’instance du descripteur change dans le top. Le descripteur FS et la limite FIFO annoncent déjà 64 octets. |

Empreintes des deux IP réutilisées :

```text
PHY FS : b7bfe336d7ce1a5d4f275ec5ab6cf12df28a565995fc430d85ddd8bf54f0c660
Contrôleur FS : 211bdb357052537b1cb19f769dcdd01b72968172a6686b0798f3509d1e1ce342
```

`controller_provenance/` conserve la configuration `FSSUPPORT`, `DESC_PACKET_MAX64`, `UTMI`, `SELFPOWERED`, les types d’endpoints, les sources fournisseur, le projet et le manifeste du build d’origine. Le SHA de la netlist correspond à celui de ce manifeste antérieur. Aucun corps de netlist fournisseur n’a été édité.

L’horloge PHY de 60 MHz est confirmée par l’IPC et par le [guide officiel Gowin USB 1.1 SoftPHY, IPUG759-1.2.1E, tableau 4-1](https://www.gowinsemi.com/upload/database_doc/2119/document/65572aae01c10.pdf). Le contrôleur et le PHY sont tous deux configurés pour FS ; ce témoin n’emploie pas le PHY HS simplement forcé en repli FS.

## Contrôles avant et après compilation

`audit.py` a terminé avant Gowin avec `PASS_PREBUILD_AUDIT` :

- Empreintes intactes, disparition des ports HS et contrôle des périodes/faux chemins conservés.
- Lint du top par Verilator avec les déclarations publiques des IP pour contrôler syntaxe et ports. Ces déclarations ne simulent pas le fonctionnement du transport. Les avertissements hérités de la référence restent dans `audit/top_syntax.log`.
- Simulation du véritable descripteur : USB **1.10**, VID:PID **359f:2010**, taille maximale **64 octets pour EP0, EP2 IN et EP2 OUT**. Résultat dans `audit/descriptor_test.log`.

Gowin V1.9.12 a chargé le GPRJ et sa configuration Sipeed, avec uniquement l’activation volontaire du rapport timing texte. Placement 1, routage 0, correction hold activée et fanout maximal 23 sont conservés. Les normalisations automatiques `Normal → Single` des fonctions multiboot désactivées et `SerDes_retiming=false` sont consignées dans `validation.json`.

La validation après P&R vérifie de nouveau les entrées, les netlists et la référence d’origine. Les deux faux chemins UART restent qualifiés par les mêmes instances. Le rapport contient uniquement les horloges **50/48/60 MHz** ; les ports HS sont absents du pinout actif. La politique Sipeed des broches inutilisées, entrée tristate avec pullup, reste inchangée : aucune sortie logique HS n’est instanciée, sans revendiquer une absence de tout courant de polarisation sur ces broches.

## Timing et ressources

Rapport `project/impl/pnr/usb_uart_loopback.tr`, généré le 2 octobre 2026 à 16:56:46.

| Analyse | Marge minimale |
|---|---:|
| Setup | +2,221 ns |
| Hold | +0,153 ns |
| Recovery | +11,729 ns |
| Removal | +1,949 ns |
| Largeur d’impulsion | +5,357 ns |

**110 marges détaillées positives ; six lignes TNS à zéro, aucun endpoint setup/hold violé.** Analyse : 25 336 chemins, 16 871 endpoints ; Fmax PHY_CLKOUT 69,225 MHz pour une contrainte de 60 MHz. Les marges valent pour les contraintes conservées, pas pour la conformité électrique USB.

Ressources : **4 589 éléments logiques** (3 199 LUT et 1 390 ALU), **5 545 registres**, **6 BSRAM**, **2 PLL**, **3/8 PRIMARY**, **11 ports**. Aucun CPU, GPU ou DDR de la console.

## Livrables pour le test matériel

`board_test_manifest.json` contient le bitstream, le rapport timing, **71 empreintes**, l’identité `359f:2010 / 11252024` et `expected_speed_mbps=12`. Vérification locale réussie :

```sh
python3 tools/check_usb_reference.py --stage tang/impl/usb_sipeed_fs_r1 --expected-usb-speed 12 --check-only
```

Bitstream : `tang/impl/usb_sipeed_fs_r1/project/impl/pnr/usb_uart_loopback.fs`.

```text
f420fe25751b3e21730488ed7cad3793d037a9ace94a62a2a970cea1603c75ae
```

Copie sous `bitstreams/usb_sipeed_fs_r1/`. Archive des entrées actives et preuves : `TESTS/usb_sipeed_fs_r1_build_20261002.tar.gz`, avec somme SHA-256. Le test suivant doit vérifier **12 Mbit/s réellement négociés**, puis utiliser l’écho UART interne brut à **115200 bauds**. Le parent gère seul le chargement SRAM, l’essai et la restauration de la console.

## Essai matériel et restauration

Les 71 empreintes et le timing sont revérifiés sur ax15. Chargement SRAM
sur FTDI `2023112818`, `3:66`, avec `DONE`. Le noyau détecte le périphérique
**Full Speed** à quatre reprises sur `3-7`, adresses 95 à 98, mais chaque
lecture complète du descripteur expire avec **−110**. Aucun port CDC
n'apparaît ; aucun écho n'est envoyé. L'annonce Full Speed du noyau ne
constitue donc pas une énumération réussie ni une validation du transport.

[Résultat](usb_ax15_20261002/sipeed_fs_r1/result.json),
[journal d'énumération](usb_ax15_20261002/sipeed_fs_r1/enumeration.txt).
Ce cas minimal confirme l'échec d'énumération avec le PHY FS dédié ;
il reste à départager protocole de contrôle, PHY et interface électrique.

Le diagnostic console `gpu_usb_first_r3` est ensuite restauré, après contrôle
de ses sources et du timing. Il s'énumère à 480 Mbit/s, mais le stress USB
reste en échec. [Restauration](usb_ax15_20261002/usb_first_r3_restored_after_dedicated_fs/result.json).
