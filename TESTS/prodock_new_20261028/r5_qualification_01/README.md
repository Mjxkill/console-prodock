# Qualification hors carte du candidat Pro Dock SD R5

**R5 contient le bon bootstrap SD.** Le compilateur termine, le VO reproduit
exactement le binaire attendu, et les broches ainsi que les réseaux d’horloge
publiés restent ceux de G22r0. Aucun nouveau bloqueur ROM/brochage n’est
identifié pour l’essai SRAM diagnostique décidé par root.
**Le timing global n’est pas fermé.** Les violations USB/CDC/reset ci-dessous
restent présentes. Aucun essai matériel n’est effectué par cet audit.

FS : `24d6bfbc364aec025e9970ccfb0ab40463f1f576c153bd4c64313f5a3a551c2a`.
Cible déclarée : Pro Dock GW5AST-LV138FPG676AC1/I0, programmateur 2025071717.
Le contrôleur de chargement doit encore identifier la carte effective.

## ROM et provenance

Les 20 936 octets reconstruits depuis les 32 SP du VO sont identiques à
sd_boot.bin, SHA `d8ab75277c4cb4eb2a4123fbdf269d96fa8a5cd44cb84eaa11c8e3fdf66d8ae8`.
Les 44 600 octets restants sont tous nuls. Les quatre lanes source donnent
aussi exactement ce binaire. Le SHA des 64 Kio reconstruits est
`1367eadc8099fe5283c1b8fa18ace3436bd3529bd61b0211ae369cb1e37341a0`.
Ce contrôle porte sur les INIT du VO, pas sur une relecture physique du FPGA.

R5 réutilise la VG R4 exacte `6358e266…` et son PR `7f6a7938…` comme ancre.
Les 136 sources, leur manifeste, CST et SDC sont inchangés. Les options du
dispositif et du PnR sont identiques après normalisation des chemins, du nom
et de l’ancre. Le journal confirme le saut de synthèse ; les SHA complets
sont vérifiés dans `provenance.json`. Les 128 sources protégées G22r0 ont
également été vérifiées. Les trois changements historiques restent le cfg
ITCM, la netlist AE350 régénérée et le retrait de cinq requêtes de rapports.
Aucune contrainte temporelle ou électrique n’a été modifiée pour R5.

Le checker corrigé SHA `cb39392b…` est lié au résultat. Ses 16 groupes de tests
incluent le refus de l’ancienne ROM et le contre-exemple d’INIT indenté.
L’auditeur est désormais paramétrable (`--stage`/`--out`) ; trois tests de
gardes refusent un build échoué, une traversée de chemin et l’écrasement
d’un rapport existant.

## Timing : état exact et limites

Gowin V1.9.12.03, setup Slow 0,873 V / 0 °C et hold Fast 0,927 V / 85 °C.

| Mesure publiée | R5 |
|---|---:|
| Endpoints setup violés, résumé outil | 218 |
| Endpoints hold violés, résumé outil | 185 |
| Setup minimal publié | −7,789 ns |
| Hold minimal publié | −3,451 ns |
| Recovery minimale publiée | −12,298 ns |
| Removal minimale publiée | −2,265 ns |

Les 25 chemins setup et recovery publiés vont de PHY_CLKOUT vers bus80_clk.
Les 25 hold vont dans l’autre sens. Les 25 removal incluent bus80→PHY et
clk50→PHY. Les pires endpoints sont respectivement `hs_s_0_s0/D` du port
MSC, `wr_gray_s1_1_s0/D` de la FIFO de commandes UTNA, `gather_7_s0/CLEAR`
du port MSC et `count_1_s1/CLEAR` du contrôleur de démarrage USB. Les quatre
minima et compteurs setup/hold sont identiques à R3. Les totaux recovery et
removal ne sont pas publiés ; 25 chemins négatifs de chaque type sont visibles.

**CDC ne signifie pas automatiquement faux chemin.** Le groupe PHY n’est pas
déclaré asynchrone avec bus80 dans ce SDC. La recovery depuis le reset PHY
vers CLEAR des registres MSC peut concerner une libération asynchrone réelle.
Il faut examiner la synchronisation et la désactivation de chaque reset dans
son domaine destinataire, ainsi que le protocole de chaque traversée, avant
de conclure sur des exceptions. Aucun chemin n’est masqué par cet audit.
Ce contrôle CDC/reset reste une tâche après le diagnostic de boot.

Le tableau TNS par horloge vaut zéro partout. Les Fmax publiées sont :
DDR UI 75,170 MHz pour 75,002 contraints ; AHB 81,662 pour 80 ; PHY 65,591
pour 60 ; sclk 125,033 pour 120,005 ; LCD 72,508 pour 35. Ces résumés ne
couvrent pas à eux seuls les traversées CDC et ne contredisent pas les
violations globales ci-dessus. Ils ne constituent pas une fermeture globale.

Les chiffres G22r0 ne sont pas directement une référence STA comparable :
version, modèles de délai et portée des cinq rapports ciblés diffèrent.
Le fonctionnement historique de la carte ne supprime pas ces limites.

## Broches, horloges et ressources

Les 123 lignes de broches affectées (121 ports avec entrées différentielles)
sont identiques à G22r0. Les 18 lignes de réseaux d’horloge et leurs zones
publiées sont identiques. PRIMARY 8/8, LW 8/8 et PLL 5/12 ; les PR1014 sur
clk_d, ae350_tck_d et rtc_clk ne sont pas nouveaux. Cette comparaison ne
prouve pas l’identité de chaque segment physique ni l’état électrique de la carte.

| Ressource | G22r0 | R5 | Capacité |
|---|---:|---:|---:|
| Logique LUT+ALU | 83 485 | 83 453 | 138 240 |
| LUT | 63 487 | 63 488 | — |
| ALU | 19 998 | 19 965 | — |
| Registres | 53 481 | 53 318 | 139 140 |
| CLS | 58 105 | 58 078 | 69 120 |
| BSRAM | 287 | 287 | 340 |
| DSP, unités du rapport | 177 | 177 | 298 |
| IOLOGIC | 102 | 102 | 300 |
| PLL | 5 | 5 | 12 |

## Portée du succès de reprise

R5 a terminé en 2 151,90 s au niveau du superviseur. L’outil comptabilise
13 min de PnR, dont 5 s de STA, avec un pic rapporté de 2 754 Mo ; le temps
de lecture initiale de l’ancre n’est pas inclus dans ce total PnR. La trace
ciblée strace contient seulement `exit_group(0)` et une sortie normale 0.
Aucun enfant ou signal n’a été observé avec ce filtre ; aucun contenu
d’environnement, IO ou argv n’est tracé.

R5 utilise effectivement la combinaison VG R4 + PR R4 proposée. Son succès
démontre que ces artefacts étaient réutilisables pour produire FS/VO/STA.
Il ne détermine pas pourquoi R4 s’était arrêté : une reprise incrémentale peut
changer l’état interne et le routage, et l’instrumentation est différente.
Il n’y a pas de cause DDR/LW/RTL démontrée, ni de preuve que retirer davantage
de contraintes aurait été nécessaire.

L’étape suivante est distincte : essai SRAM de ce FS exact sur la nouvelle
carte, puis vérification SD/Linux/jeu. L’écriture permanente et la
qualification du démarrage autonome ne découlent pas de ce rapport hors carte.

## Comparaison supplémentaire avec R3

Après normalisation des chemins et de la date, le rapport TR complet est
identique à celui de R3. La comparaison du VO en excluant les INIT ITCM et
la date laisse seulement neuf lignes différentes : noms générés de deux ALU
et de leurs deux nets dans bounds_product0/1. Le SDF garde dix-huit lignes
différentes, dont la date et ces noms. Les premières différences sont
consignées dans `artifact_differences.json`. Cela complète la comparaison des
ressources ; aucune équivalence physique complète n’est revendiquée.
