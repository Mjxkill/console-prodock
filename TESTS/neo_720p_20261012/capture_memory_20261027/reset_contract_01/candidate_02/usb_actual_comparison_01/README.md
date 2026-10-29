# USB actif : G22r0 Pro Dock et R21r2 Neo

Audit du 27 octobre 2026, sans accès matériel, changement de source ni compilation.
Il établit la provenance et les différences ; il ne valide pas l'énumération USB.

## Conclusion vérifiée

Les deux configurations utilisent la même architecture USB HS, mais **pas les
mêmes deux IP générées**. Sur 19 fichiers sous `source/tang/rtl/usb`, 16 sont
identiques ; les différences sont `usb_device_controller.v`, `usb2_0_softphy.v`
et les resets locaux de `usb_msc_port.v`. Le commentaire « SAME modules » en
tête de `boards/neo/soft_usb.vh` ne décrit donc pas exactement le snapshot.

| Élément | Pro Dock G22r0 | Neo R21r2 resetqual coupled |
|---|---|---|
| Cible de construction | GW5AST-138B, FPG676AC1/I0 | GW5AST-138C, PG484AC1/I0 |
| Contrôleur actif | Génération C28, IP 3.3 | Binaire de référence Sipeed, novembre 2024 |
| PHY actif | Génération C28, IP 3.5, `V_120` explicite | Binaire Sipeed, novembre 2024 ; macro `V_120` absente du template associé |
| Outil indiqué dans ces IP | GowinSynthesis V1.9.12.03 | GowinSynthesis V1.9.10.03 |
| Cible du projet IP retrouvé | B / FCPBGA676A | IPC Sipeed `gw5ast138b-007`, malgré intégration console cible C |
| Contrôleur USB configuré | HS, UTMI, EP0 64 octets, autoalimenté, endpoints bulk | Mêmes choix dans l'IPC Sipeed correspondant |
| Horloges USB prévues | 50 → 48 MHz → 960 MHz / 60 MHz | Mêmes modules PLL et paramètres |

La valeur `version=1.0` des IPC Sipeed ne permet pas d'identifier avec certitude
leur version de livraison IP. L'absence de `V_120` dans ce vieux template ne
permet pas, seule, de déduire la fréquence réelle de toutes ses horloges internes.
La différence B/C est une différence de configuration à examiner ; elle ne
prouve ni incompatibilité du binaire, ni révision de silicium, ni erratum.

## Preuve de l'utilisation effective

`active_provenance.json` lie les sources aux entrées de synthèse et aux modules
effectivement instanciés, pas seulement à des fichiers présents dans l'archive.

- Le `build.tcl` R21r2 route `console_neo.vg`. Sa table de sources désigne
  `console_neo_n56r9_scan_observer`, synthèse du 23 octobre 2026. Son Tcl
  ajoute explicitement les deux IP anciennes (lignes 42–43).
- Les **27 modules USB/PLL**, les **quatre blocs chiffrés** et les **sept
  instances top** contrôleur/PHY/PLL/séquenceurs sont identiques à cette
  synthèse N56r9. Les 19 sources USB correspondantes sont également identiques.
- Les deux IP anciennes sont identiques octet par octet aux fichiers de
  `/home/michael/gowin/ref/TangMega-138KPro-example/usb2_soft/usb_uart_loopback/src`.
  Les IPC associés documentent la cible B et les paramètres précités.
- G22r0 réutilise la netlist de G22r ; sa table de sources désigne G22. Les deux
  IP des sources G22, G22r0 et C28 sont identiques. Les métadonnées C28
  `usb_controller.json` / `usb_phy.json` donnent explicitement 3.3 et 3.5.
- Les IP nouvelles générées pour Neo C/PG484 dans
  `n56r3_validation_20261021/usb_ip_candidate/generated` ont les empreintes
  contrôleur `f11307d3…f198ee2a` et PHY `5a1eb838…846abaa`.
  **Elles ne sont pas dans cette branche R21r2**. Le résultat de leur génération
  ne constitue pas une correction du USB actuellement routé.

La première comparaison avec N56r1 est conservée dans `comparison.json` :
plusieurs modules n'y sont pas identiques, car N56r9 a refait une synthèse
complète (noms et mapping changés). Cette comparaison préliminaire n'est pas
utilisée comme preuve d'identité binaire. Les blocs chiffrés source et intégrés
ne sont pas directement comparables non plus ; la liaison passe par les
entrées de synthèse, les instances actives et la netlist héritée exacte.

## Horloges et resets

Le segment de `wire pll_f_lock` à `usb_app_reset` est **identique octet par
octet** entre le top G22r0 (lignes 160–187) et `soft_usb.vh` Neo (34–63).
Les fichiers `gowin_pll_f.v`, `gowin_pll_b.v` et `usb_reset_release.v` sont
identiques. La logique prévoit :

1. PLL F 50→48 MHz ; son reset d'entrée est à zéro.
2. Qualification de LOCK F pendant 104000 cycles de la référence 50 MHz
   (2,08 ms), puis sortie du reset de PLL B.
3. Qualification de `lock_F & lock_B & ~reset_B` pendant 104000 cycles.
4. Qualification locale de 64 cycles sur `phy_clk` pour `rst_usb`.
5. Contrôleur remis à zéro par `rst_usb`, PHY par `PHY_RESET | rst_usb`,
   entrée `pll_locked_i` du PHY = `~rst_usb`, application par
   `rst_usb | usb_busreset`.

`usb_reset_release` invalide de manière asynchrone sur perte de LOCK et
synchronise la sortie ; c'est une logique distincte du vieux qualificateur
CPU corrigé en R21r2. Cela ne démontre pas la largeur analogique de capture,
la stabilité PLL réelle, ni le timing de toutes les libérations.

Les contraintes maintiennent PLL F en R[2], PLL B en R[1]. Les sites globaux
`phy_clk` / `fclk_960m` diffèrent (Pro Dock BUFG1/2, Neo BUFG2/3), avec sclk
sur BUFG7 dans les deux. Les périodes Neo sont déclarées dans `neo.sdc:43–48` :
48 MHz, 60 MHz, 960 MHz et sclk 8,333 ns. Cette déclaration est un modèle
STA, pas une mesure physique. Le timing global R21r2 reste FAIL.

La différence MSC utilise `hr[2]` et `ur[2]` comme resets locaux à la place
de `reset_n` dans huit blocs. Ces chaînes existaient déjà ; la libération
est désormais propre à chaque domaine. Ce changement concerne le port MSC,
pas la sélection du mode HS du contrôleur ou la calibration PHY.

## Brochage

Le schéma local Sipeed `Tang_Mega_138K_Console_32001C__Schematics.pdf` a été
relu, notamment les feuilles SOM_BTB0/1/2 et J17 USB Soft Device. Les liaisons
correspondent au CST Neo (lignes 189–200) :

| Signal | Neo | Pro Dock |
|---|---|---|
| TX différentiel | J19/H19 | M21/M22 |
| Comparateur RXDP | H17/H18 | U21/V21 |
| Comparateur RXDN | H20/G20 | T20/U20 |
| Pullup | M17 | M19 |
| Terminaison DP | J16 | T19 |
| Terminaison DN | AB16 | U19 |

Les attributs électriques CST de ces six ports sont identiques entre les
cartes (y compris standards, pull, CTLE, drive et VCCIO). Le schéma montre
le réseau RC et la référence des comparateurs ; aucun PHY externe n'est
attendu. Aucun défaut de correspondance de broche n'a été trouvé. La
présence du bon brochage ne mesure ni les alimentations, ni les signaux.

## Lectures CPU sans effet sur USB

La fenêtre `0xe9002000` est `usb_idle_trace`, avec trois registres sûrs :
signature `0x55544e41`, statut busy/rejected, compteur de snapshots terminés.
Leur lecture ne demande aucune capture et ne consomme aucune FIFO USB.
Le Tcl vidéo lit seulement ces trois mots, quatre fois.

**Interprétation limitée :** `UTNA` démontre que le côté AHB a quitté son
reset après l'échange de disponibilité `hr/ur/hu/uh` au moins une fois.
Cela ne prouve pas que l'horloge USB tourne encore. Des zéros peuvent être
produits tant que `hreset = !hr[2] || !uh[1]` reste actif ; ils ne prouvent
pas à eux seuls quelle horloge ou quel reset est défaillant. Compteur zéro
est normal sans commande de capture. La banque +40..bc contient uniquement
la dernière capture, pas des compteurs vivants.

Le port MSC `0xe9003000` est exclu : +08/+20 consomment des données et toute
lecture recharge son watchdog (`usb_msc_port.v:185,189,221`). Même sa lecture
de statut n'est donc pas totalement passive. Le diagnostic EP0 expose quelques
bits PLL/SoC, mais nécessite un transfert USB et n'est pas accessible par
la fenêtre MMIO des trois mots UTNA.

Un prochain essai d'alignement des deux IP doit conserver une expérience
distincte et qualifier intégration, timing puis énumération HS. Cet audit
ne justifie pas d'affirmer que cet alignement réparera à lui seul la liaison.
