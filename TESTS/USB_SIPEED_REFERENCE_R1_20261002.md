# USB Sipeed intact — compilation de référence r1, 2 octobre 2026

**PASS compilation et timing ; FAIL essai USB sur carte effectué ensuite.**

Objectif : fournir un témoin USB seul, identique à l’exemple Sipeed, pour comparer son comportement à la console. L’ancien E0b comportait des adaptations et ne constituait pas ce témoin intact.

## Provenance et reproductibilité

- Origine : `/home/michael/gowin/ref/TangMega-138KPro-example/usb2_soft/usb_uart_loopback`.
- Dépôt : <https://github.com/sipeed/TangMega-138KPro-example>, HEAD `d3cebf1703f1bcd06dca8a53bf2b660c86a5ec16`. Le sous-répertoire d’origine est propre dans Git.
- Dossier isolé : `tang/impl/usb_sipeed_reference_r1`, créé neuf.
- `source/` : copie intacte ; `project/` : copie compilée. Les **17 fichiers actifs** du GPRJ, dont SDC/CST et netlists fournisseur, sont inchangés. Le projet d’origine est également inchangé. Leurs SHA-256 figurent dans `sources.json`.
- Cible : `GW5AST-LV138FPG676AC1/I0`, révision B ; top `Top` ; Gowin **V1.9.12** ; Verilog 2001 et VHDL 2008.
- Compilation par ouverture du GPRJ existant, puis `set_option -gen_text_timing_rpt 1` et `run all`. Aucune régénération d’IP ni modification de source, netlist, SDC ou CST.
- `validate.py` vérifie les SHA avant/origine/après, la liste réellement synthétisée, les options et le timing ; résultat archivé dans `validation.json`.

Le `process_config` Sipeed a été chargé par `open_project`. Les paramètres conservent notamment placement **1**, routage **0**, ordre des horloges **0**, correction hold activée, fanout maximal **23**, timing driven et promotion des avertissements CST en erreurs. `cmd.do`, `device.cfg` et le projet de synthèse généré en apportent la preuve.

L’unique option volontairement ajoutée est le rapport timing texte. Gowin normalise aussi `MULTIBOOT_MODE` et `MULTIJUMP_MODE` de `Normal` vers `Single`, alors que ces deux fonctions sont désactivées, et ajoute `SerDes_retiming=false`. Ces quatre différences du JSON sont contrôlées explicitement ; la copie de configuration Sipeed reste intacte dans `source/`.

## Timing obtenu

Rapport : `project/impl/pnr/usb_uart_loopback.tr`, généré le 2 octobre 2026 à 16:32:48, avec les contraintes Sipeed d’origine.

| Analyse | Marge minimale | Chemins détaillés |
|---|---:|---:|
| Setup | +1,617 ns | 25 |
| Hold | +0,144 ns | 25 |
| Recovery | +2,012 ns | 25 |
| Removal | +1,607 ns | 25 |
| Largeur d’impulsion | +1,073 ns | 10 |

Les **110 marges détaillées sont positives**. Les dix lignes du résumé TNS setup/hold valent **0,000 ns**, avec zéro endpoint en violation. L’analyse porte sur 27 909 chemins et 18 255 endpoints. Le rapport donne Fmax **148,893 MHz** pour `sclk` contraint à 120,005 MHz, et **72,539 MHz** pour `PHY_CLKOUT` contraint à 60 MHz.

Limites conservées : le SDC d’origine sépare les horloges PHY par groupes asynchrones et contient les faux chemins du diviseur UART. Aucun chemin Fmax n’est donné pour l’entrée 50 MHz, le 48 MHz et le 960 MHz. L’avertissement `PR1014` sur le routage générique de `CLK_IN_d` est présent. Ce PASS évalue les chemins couverts par ces contraintes ; il ne démontre pas la conformité électrique USB ni la fiabilité sur carte.

Ressources P&R : **5 652 éléments logiques** (4 248 LUT et 1 404 ALU), **5 970 registres**, **8 BSRAM**, **2 PLL**, **5/8 horloges PRIMARY**. Ce projet ne contient ni CPU console, ni GPU, ni DDR.

## Livrables et contrat du test suivant

Bitstream compilé : `tang/impl/usb_sipeed_reference_r1/project/impl/pnr/usb_uart_loopback.fs`.

SHA-256 :

```text
e845b1343a23a1a9a47cb61382e45b97f91272cb1edf051235cbcacb4c4bb556
```

Archive du bitstream : `bitstreams/usb_sipeed_reference_r1/usb_uart_loopback.fs`, avec somme SHA, timing, manifeste et validation. Archive des preuves et entrées actives : `TESTS/usb_sipeed_reference_r1_build_20261002.tar.gz`, accompagnée de son SHA-256.

Le top Sipeed annonce **VID:PID `359f:2010`**, série **`11252024`**. Il relie son émission UART à sa réception UART en interne, à **115200 bauds**. Le test matériel doit envoyer des octets bruts et attendre leur écho ; les commandes et les sondes privées de la console ne s’appliquent pas à ce témoin. Le parent gère seul le chargement SRAM, les essais et la restauration de l’image console.

## Essai sur carte

Après vérification de 45 empreintes locales puis distantes, chargement SRAM
réussi sur FTDI `2023112818` d'ax15, avec `DONE`. La référence s'énumère
à **480 Mbit/s** sur `3-7`, `/dev/ttyACM1`, avec l'identité attendue.

**103 échos unitaires exacts, puis `70` reçu `7070` à l'index 103.**
Le doublon subsiste après une seconde de grâce. Le test s'arrête au premier
défaut ; les blocs prévus ne sont pas envoyés. Aucun diagnostic EP0 privé
ni commande du firmware console n'est utilisé. Les sources compilées
restent inchangées.

[Résultat](usb_ax15_20261002/sipeed_reference_r1/result.json),
[outil de test archivé et empreintes](usb_ax15_20261002/sipeed_reference_r1/analysis.json).
Ce témoin exclut la nécessité du CPU/GPU et de nos modifications de FIFO
pour reproduire le symptôme ; il ne sépare pas encore les composants de
la chaîne USB de référence ni leurs conditions électriques.

`gpu_usb_first_r3` est restauré après cet essai et s'énumère à 480 Mbit/s.
Son stress reste en échec, ce qui est consigné séparément. Le témoin Sipeed
archivé est un reproducteur de panne, pas un bitstream USB validé.
