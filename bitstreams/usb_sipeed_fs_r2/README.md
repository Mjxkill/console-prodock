# USB EP0 : preuve A/B de réception prête et témoin FS r2

## Résultat

Le contrôleur **Gowin 3.2 FS exact du r23** transmet le descripteur demandé correctement avec `rxrdy_i=0`, mais répond **NAK (`5a`) au paquet OUT de status**. Avec `rxrdy_i=1`, le même modèle répond **ACK (`d2`)** et termine le transfert. Le défaut est reproduit pour les trois longueurs demandées **8, 18 et 64 octets**.

Le modèle Sipeed ancien accepte ce même status avec `rxrdy_i=0` ou `1`. La différence de comportement entre versions est donc observable ; une compilation réussie du nouveau contrôleur ne garantissait pas sa compatibilité avec le raccordement ancien.

Cette preuve concerne le **blocage EP0 du contrôleur FS**. Le premier essai sur carte du témoin corrigé passe également : **12 Mbit/s, 1 000 échos unitaires et trois blocs exacts**. Cela n’établit pas la cause des insertions ou pertes de données bulk High Speed et ne valide pas la console CPU/GPU.

## Contrat fournisseur et raccordement fautif

Le [guide officiel IPUG927-1.8E, §3.2.1, page 7](https://www.gowinsemi.com/upload/database_doc/2121/document/6a5957fc5a564.pdf) précise que les commandes standard EP0 utilisent également les signaux de disponibilité : `txcork_i` doit rester bas et `rxrdy_i` haut. Le guide actuel vise 1.9.12.03 ; l’A/B ci-dessous démontre directement le comportement du contrôleur 3.2 employé ici, sans extrapoler uniquement depuis cette documentation.

Le témoin FS r1 conserve la branche Sipeed `usb_fifo.v:602–604` : lorsque l’endpoint est 0, `s_usb_rxrdy` est forcé à0. `TOP.v:192` raccorde cette sortie au contrôleur. Les sources figées de la console r20 et r23 présentent la même branche à `usb_fifo.v:647–649`.

Les macros ne révèlent aucune omission : le fichier define r20 est identique octet pour octet à celui de Sipeed ; r23 ne change que `HSSUPPORT` en `FSSUPPORT`. Les familles de macros correspondent aux chaînes du plugin 1.9.12. `ENDPTx_*_T_TYPE=0` signifie Bulk. Aucun port d’entrée public du contrôleur n’est omis dans les trois tops inspectés.

## Modèle exporté et banc

Entrée fournisseur inchangée :

```text
tang/impl/gpu_l12_diag_r23_fs/usb_ip/usb_device_controller.vg
SHA-256 : 211bdb357052537b1cb19f769dcdd01b72968172a6686b0798f3509d1e1ce342
```

L’export officiel utilise Gowin 1.9.12, `set_option -gen_verilog_sim_netlist 1` puis `run all`, dans le dossier neuf `tang/impl/gpu_usb_controller32_fs_model_r1`.

L’export direct rencontre la limite de 384 ports contre 293 I/O ordinaires. L’assemblage ouvert [usb_ep0_controller_model.v](rtl/usb_ep0_controller_model.v) instancie donc la netlist intacte et le véritable descripteur FS Sipeed, avec les mêmes adresses, longueurs et identifiants que la carte. Les ports UTMI, EP0 et ROM utiles restent observables. La synthèse peut optimiser cet assemblage normalement ; aucune netlist fournisseur n’est éditée et aucun signal interne n’est forcé.

L’entrée utilisateur EP0 est fixée à `txval_i=0`, `txcork_i=0`, `txdat_len_i=7` : c’est le contexte des requêtes standard internes avant toute configuration CDC. Seul `rxrdy_i` varie entre les deux essais.

Le [banc dédié](rtl/usb_ep0_descriptor_tb.sv) et son [runner](../tools/check_usb_ep0_descriptor.py) vérifient :

1. Fin de l’attachement du contrôleur (`OPMODE=00`), reset USB FS puis reprise.
2. SETUP GET_DESCRIPTOR correctement acquitté.
3. DATA1 contenant exactement `min(wLength,18)` octets, contenu complet comparé à une référence indépendante et CRC16 vérifié.
4. ACK de l’hôte, puis OUT DATA1 ZLP de status ; **ACK du contrôleur obligatoire**, un NAK fait échouer le test.
5. SET_ADDRESS 7, status IN DATA1 ZLP, ACK, attente de 2 ms.
6. Deux nouvelles lectures complètes à l’adresse 7, avec les mêmes contrôles de status.

Les octets UTMI FS sont espacés de 40 cycles à 60 MHz. Le modèle travaille en numérique idéal : pas de PHY analogique, de câble, de métastabilité ni d’annotation SDF. L’export place/routage fournit un modèle officiel, sans constituer une équivalence des délais avec le bitstream de la carte.

## Résultats et limites des premiers essais

| Contrôleur | `rxrdy` | `wLength` | Données | Status OUT et suite |
|---|---:|---:|---|---|
| FS 3.2 r23 | 0 | 8 | 8 octets corrects, CRC correct | NAK 5a ; FAIL au premier status |
| FS 3.2 r23 | 0 | 18 | 18 octets corrects, CRC correct | NAK 5a ; FAIL au premier status |
| FS 3.2 r23 | 0 | 64 | 18 octets corrects, CRC correct | NAK 5a ; FAIL au premier status |
| FS 3.2 r23 | 1 | 8 | Correctes aux trois lectures | Trois ACK de status ; PASS |
| FS 3.2 r23 | 1 | 18 | Correctes aux trois lectures | Trois ACK de status ; PASS |
| FS 3.2 r23 | 1 | 64 | Correctes aux trois lectures | Trois ACK de status ; PASS |
| Sipeed ancien, repli FS | 0 | 18 | Correctes aux trois lectures | Trois ACK de status ; PASS |
| Sipeed ancien, repli FS | 1 | 18 | Correctes aux trois lectures | Trois ACK de status ; PASS |

Rapports FS 3.2 :

- `rxrdy=0` : [8](usb_ep0_fs32_ready0_len8_boot2_20261002.json), [18](usb_ep0_fs32_ready0_len18_boot2_20261002.json), [64](usb_ep0_fs32_ready0_len64_boot2_20261002.json).
- `rxrdy=1` : [8](usb_ep0_fs32_ready1_len8_boot2_20261002.json), [18](usb_ep0_fs32_ready1_len18_boot2_20261002.json), [64](usb_ep0_fs32_ready1_len64_boot2_20261002.json).
- Ancien contrôleur : [rxrdy0](usb_ep0_sipeed_ready0_len18_boot2_20261002.json), [rxrdy1](usb_ep0_sipeed_ready1_len18_boot2_20261002.json).

Tous ces rapports portent `sources_unchanged=true`. Les deux fichiers initiaux sans suffixe `boot2` ne sont **pas** des résultats A/B valables : le premier banc lançait SETUP avant la fin de l’attachement, à environ 10 ms, alors que le modèle quitte OPMODE 01 vers 17 ms. Ils sont conservés comme diagnostic de ce démarrage prématuré. Le banc final attend explicitement OPMODE 00.

Le message Linux `device descriptor read/all` désigne la lecture complète après SET_ADDRESS et acquisition préalable de `bMaxPacketSize0`. Il ne précise pas à lui seul si la phase DATA ou le status échoue ; le NAK démontré fournit ici un mécanisme concret compatible avec un timeout de contrôle. [Linux v6.17, hub.c](https://github.com/torvalds/linux/blob/v6.17/drivers/usb/core/hub.c#L4703)

## Témoin matériel FS r2 préparé

Dossier neuf : `tang/impl/usb_sipeed_fs_r2`. Une seule ligne fonctionnelle change par rapport au FS r1 :

```verilog
assign usb_rxrdy = (endpt_sel == ENDPT_UART_CONFIG) ? 1'b1 : ep_usb_rxrdy;
```

Le chemin des endpoints non nuls conserve exactement l’expression précédente. Le contrôleur, le PHY FS, le descripteur, les FIFO, l’UART, les PLL et les contraintes sont identiques octet pour octet à r1. L’audit préalable vérifie cette différence unique et les empreintes des 15 autres entrées actives. Les sources de production ne sont pas modifiées.

Gowin 1.9.12 termine le 2 octobre à 19:28:31. Validation après P&R :

| Analyse | Marge minimale |
|---|---:|
| Setup | +2,141ns |
| Hold | +0,153ns |
| Recovery | +11,746ns |
| Removal | +1,942ns |
| Largeur d’impulsion | +5,357ns |

110 marges détaillées positives, six TNS nuls et zéro endpoint setup/hold violé. Périodes 50/48/60 MHz et faux chemins UART Sipeed inchangés. Ressources : 4 584 éléments logiques, 5 545 registres, 6 BSRAM, 2 PLL, 3/8 PRIMARY, 11 ports.

`board_test_manifest.json` contient **87 empreintes**, dont la preuve A/B et le modèle officiel. La vérification suivante passe sans accès carte :

```sh
python3 tools/check_usb_reference.py --stage tang/impl/usb_sipeed_fs_r2 --expected-usb-speed 12 --check-only
```

Bitstream : `tang/impl/usb_sipeed_fs_r2/project/impl/pnr/usb_uart_loopback.fs`.

```text
SHA-256 : d627e3d3276a54d0ee6c1041caece263d5162f9c7dee7717075caaa9b6659de0
```

Livrables copiés dans `bitstreams/usb_sipeed_fs_r2/`. Archive : `TESTS/usb_sipeed_fs_r2_build_20261002.tar.gz`, avec somme SHA-256. Le chargement et l’évaluation à 12 Mbit/s sont conduits séparément par la session principale.

## Premier essai matériel FS r2

La session principale charge le bitstream ci-dessus en SRAM sur la carte FTDI `2023112818`, puis relève la vitesse **12 Mbit/s** dans sysfs, branche `3-7`, console `/dev/ttyACM1`.

Le [résultat matériel](usb_ax15_20261002/sipeed_fs_r2/result.json) porte `status=pass`, le même SHA de bitstream et **1 003 transactions exactes** :

- 1 000 échos de 1 octet ;
- blocs de 64, 256 et 1 024 octets.

Le témoin USB seul n’emploie ni CPU, ni GPU, ni DDR de la console. Ce succès valide cette séquence à Full Speed ; il ne vaut pas validation High Speed, endurance illimitée ni validation de l’ensemble graphique. Les répétitions de chargement en cours sont rapportées séparément après leur fin.
