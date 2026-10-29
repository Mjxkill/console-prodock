# Neo : chemins DDR entre logique, PHY et broches

Comparaison du 24 octobre 2026, sans chargement FPGA ni accès matériel.

**Résultat : les arcs SDF du PHY vers les broches DQ/DQS, DM,
commande/adresse et CK, et les retours primaires vers IDES/DQS, sont
identiques entre N56r8, N56r9 route2 et N56r9 route9. Les liaisons internes
entre logique programmable et PHY diffèrent. Cela ne démontre pas encore
la cause du blocage DMI de route9, ni un échec de calibration.**

## Versions effectivement comparées

| Nom dans ce rapport | Build | Observation matérielle disponible |
|---|---|---|
| N56r8 | `console_neo_n56r8_hdmi_sg4` | CPU accessible, mire HDMI confirmée ; framebuffer encore défaillant |
| R2 | `console_neo_n56r9_route2` | CPU accessible, écritures et relectures DDR de la mire réussies ; lecteur vidéo bloqué |
| R9 | `console_neo_n56r9_route9_dma_c150` | Deux chargements SRAM réussis, TAP visible, DMI en timeout ; état réel DDRinit non mesuré |

SHA-256 des bitstreams :

```text
N56r8 51841fe4ae76a7eb635a0398534f35b6c7030fa8b768d88b892fede3b1601c35
R2    150bd72724ef7ec79c511afe2cc1c01f5976113ec00c39e8fc15e1f272731a01
R9    1593a2aaf7d84e5d099520d96b5d60852340601fd861d2c21108bace846e2fde
```

Les trois qualifications globales restent **FAIL**. Les mots « démarre » et
« CPU accessible » ne qualifient pas le framebuffer ni tout le système.
Les références Pro Dock sont inchangées. La Neo reste sur N56r8, mire active.

## Méthode et couverture

L'extracteur [analyze.py](analyze.py) relit les fichiers routés `.vo`, `.sdf`,
`.rpt.txt`, les contraintes et les identités des bitstreams. Chaque arc SDF
retenu est vérifié contre les nets réellement connectés dans le Verilog
routé, y compris les ports vectoriels et concaténations. Les noms SDF
échappés sont normalisés, sans fusionner des instances différentes.

- 72 broches logiques DDR, avec bille, banque, site I/O et options électriques.
- 201 primitives PHY/buffers : types, connexions, paramètres, arcs internes
  et timing checks identiques dans les trois builds.
- 302 trajets composés par build, avec les trois valeurs MIN/TYP/MAX et les
  fronts montant/descendant distincts : 72 trajets sortie à partir du dernier
  driver ; 70 trajets incluant l'arc clock→Q du sérialiseur ; 44 commandes
  OEN, également 44 avec leur lancement ; 40 retours primaires DQ/DQS ;
  32 dérivations DQ vers la première LUT de logique programmable.
- Ces 302 cas se recouvrent volontairement : ce ne sont pas 302 nets
  physiques indépendants. Les deux sorties sans lancement sérialisé sont
  `ddr_reset_n` et `ddr_addr[15]`, cette dernière étant constante.
- 77 329 arcs de routage touchant l'IP/PLL DDR sur N56r8 ; 77 677 sur R2/R9.
  Le relevé intégral est conservé en CSV, sans réduire l'analyse aux seuls
  chemins affichés dans les rapports de violations.
- Les six fichiers de source IP DDR 32 bits/PLL du manifeste ont été relus
  et leurs empreintes vérifiées ; ils sont identiques sur ces trois builds.

Les sorties négatives CK_n et DQS_n inversent la polarité des segments en
amont du buffer final. Les commandes OEN restent des chemins de contrôle de
tri-state, pas des transitions de données DQ. Les valeurs sont conservées
en picosecondes entières pour éviter les erreurs d'arrondi d'addition.

## Chemins immédiats vers les broches

Valeurs **MAX SDF**, en ns. Les sommes sont limitées aux segments indiqués.
Le détail par broche, avec MIN/TYP/MAX, est dans [pin_paths.csv](pin_paths.csv).

| Chemin | N56r8 | R2 | R9 |
|---|---:|---:|---:|
| Sortie Q du sérialiseur → PAD DQ/DQS/DM/adresse/commande/CK | 2,737 | 2,737 | 2,737 |
| Lancement clock du sérialiseur → PAD positif, front montant | 3,897 | 3,897 | 3,897 |
| PAD DQ → IOBUF → IODELAY → entrée D d'IDES | 1,018 | 1,018 | 1,018 |
| PAD DQS → IOBUF → DQSIN | 0,619 | 0,619 | 0,619 |
| Sortie Q1 → OEN → PAD | 0,597 | 0,597 | 0,597 |
| Lancement clock → Q1 → OEN → PAD | 1,447 | 1,447 | 1,447 |
| Q de `mux_reset_n_s0` → PAD RESET_n | 5,117 | 4,393 | 4,631 |

Exemple DQ0 en entrée : `0,619 + 0 + 0,399 + 0 = 1,018 ns`.
Les IODELAY DQ sont configurés avec `C_STATIC_DLY=5`,
`DYN_DLY_EN=FALSE`, `ADAPT_EN=FALSE`. Les réglages vivants de calibration DQS
ne sont pas contenus dans ce relevé statique.

Les 270 cas hors dérivations DQ vers la fabric sont identiques sauf la
sortie RESET_n. Pour cette dernière, R9 est **plus courte que N56r8**, qui
démarre : aucun seuil de panne ne peut être déduit de cette seule route.

## Distribution des horloges au PHY

Les 103 arcs de routage vers FCLK/HCLKIN/CLKIN des primitives PHY, les
101 vers PCLK et les 72 vers TCLK/ICLK ont exactement les mêmes triplets
MIN/TYP/MAX dans les trois builds. Maximum SDF de chaque groupe :

| Groupe | N56r8 | R2 | R9 |
|---|---:|---:|---:|
| Horloge rapide vers primitives PHY | 0,005 | 0,005 | 0,005 |
| Distribution PCLK des primitives PHY | 3,279 | 3,279 | 3,279 |
| Connexions dédiées DQS → TCLK/ICLK | 0,000 | 0,000 | 0,000 |

**Un zéro SDF sur une liaison dédiée ne signifie pas un délai physique nul.**
Il décrit la décomposition du modèle du fabricant. L'identité de ces arcs
ne démontre ni le verrouillage de la PLL/DLL ni le réglage réellement atteint
par la calibration. Les clocks sont à 300 MHz côté mémoire et environ
75 MHz côté interface parallèle pour les trois builds.

## Différences dans la logique programmable

Voici des arcs individuels identiques par leurs extrémités, comparés au
même coin MAX. Ces valeurs sont des délais de routage Q→D, **pas des slacks**.

| Route vers l'entrée parallèle du sérialiseur | N56r8 | R2 | R9 |
|---|---:|---:|---:|
| `oserdes_d_rr_80/Q → cmd_oserdes_gen[20]/D1` ; A14 | 3,342 | 2,974 | 5,239 |
| `oserdes_d_rr_76/Q → cmd_oserdes_gen[19]/D1` ; A13 | 2,050 | 3,780 | 5,047 |
| `oserdes_d_rr_53/Q → cmd_oserdes_gen[13]/D2` ; A7 | 2,918 | 1,448 | 4,677 |

Les FF sources et les entrées PCLK de ces OSER sont sur le même net
`gpu_clk`, issu de l'interface DDR à environ 75 MHz. On ne doit donc pas
comparer ces 5,239 ns directement à une demi-période DDR de 1,667 ns.
Il faut inclure clock-to-Q, setup/hold, distribution des clocks et contraintes
pour juger leur marge ; ce rapport ne remplace pas cette analyse STA.

Autres groupes, maximum de routage du groupe dans chaque build ; le chemin
qui réalise ce maximum peut être différent :

| Groupe | Nombre d'arcs | N56r8 | R2 | R9 |
|---|---:|---:|---:|---:|
| Fabric → D0..D7/TX0..TX3 des OSER | 780 | 3,708 | 4,408 | 5,239 |
| IDES Q0..Q7 → première charge dans la fabric | 256 | 2,519 | 2,716 | 2,720 |
| Reset et entrée CALIB des primitives PHY | 136 | 3,140 | 3,140 | 3,508 |
| Commandes vers DQS/DLL/IODELAY hors clocks/reset | 478 | 2,656 | 1,719 | 1,511 |

Les retours DQ ont aussi une dérivation distincte vers des LUT puis des FF
de la logique d'initialisation. Les 32 chemins PAD→première LUT sont
conservés dans les cas `in_fabric_tap0`. Leurs variations maximales absolues
par rapport à R9 atteignent 0,376 ns, pour N56r8 comme pour R2.
Ce ne sont pas les chemins primaires de capture des données par IDES.
La branche DQ0 rejoint effectivement `u_ddr_init` après deux FF ; son rôle
ne doit donc pas être ignoré au motif que le chemin PAD→IDES est inchangé.

## Branche vers la logique d'initialisation : calcul jusqu'à la bascule

Le complément [calibration_taps.csv](../route9_startup_analysis/calibration_taps.csv)
prolonge les 32 chemins DQ au-delà de leur première LUT, dans les trois
builds. Chaque chemin traverse une NOR4 (`INIT=0001`), puis une NAND2
(`INIT=7`), avant la première bascule `in_dq0_reg_[0..3]_s0`.
Il y a une bascule par octet DQ ; ces quatre bascules utilisent `gpu_clk`.
Les deux inversions sont prises en compte dans les additions de délais.
Les LUT, leurs connexions et les bascules sont identiques entre builds.

| PAD → première bascule de détection DQ, valeur MAX en ns | N56r8 | R2 | R9 |
|---|---:|---:|---:|
| Maximum parmi les 32 DQ | 3,058 | 3,063 | 3,084 |
| Chemin DQ0 | 2,380 | 2,408 | 2,297 |

Les maxima globaux proches ne signifient pas que tous les bits ont les
mêmes délais : la plus grande augmentation individuelle de R9 atteint
0,683 ns par rapport à N56r8 (DQ5), et 0,444 ns par rapport à R2 (DQ8).
Les calculs détaillés, INIT et lignes SDF sont dans
[calibration_taps.json](../route9_startup_analysis/calibration_taps.json).

Cette branche réalise une détection combinatoire par groupe de huit bits,
puis une synchronisation. Un arc NOR/NAND est sensibilisé lorsque les
autres entrées de l'octet sont à zéro ; la somme n'inclut pas les hazards,
les marges analogiques ni le timing de l'horloge de capture. Elle s'arrête
à l'entrée D de la première bascule et ne représente pas la durée complète
de la calibration. Ce résultat confirme une branche distincte du chemin
de capture principal, sans prouver qu'elle provoque l'échec R9.

## Vérifications et limites

Une extraction indépendante de 45 trajets témoins, directement dans les
trois SDF sans importer cet analyseur, confirme DQ0, DQS0, CK et A0,
y compris CK_n :
[independent_ddr_samples.json](../route9_startup_analysis/independent_ddr_samples.json).

Les différences, groupes complets et lignes SDF sont dans
[comparison.json](comparison.json), [n56r8.json](n56r8.json),
[r2.json](r2.json) et [r9.json](r9.json).
Les empreintes de toutes les entrées et des extractions sont conservées
dans [manifest.json](manifest.json).

Ce calcul s'arrête aux PAD logiques du modèle FPGA : il ne mesure pas les
pistes PCB, les marges analogiques DQ/DQS ou les taps choisis au démarrage.
Les sommes clock→PAD ne constituent pas un calcul de phase DDR, de latence
de transaction ni une preuve de setup/hold externe.

**Conclusion de diagnostic :** aucune différence n'a été trouvée dans les
arcs modélisés du trajet rapide PHY↔broches qui expliquerait à elle seule
« N56r8/R2 démarrent, R9 reste muet ». Des différences existent dans la
fabric et les commandes de démarrage/calibration. Observer `ddr_init`,
PLL/DLL lock et la libération des resets reste nécessaire pour déterminer
la première étape qui échoue sur R9. La comparaison n'accuse ni ne disculpe
globalement l'IP DDR.

Reproduction locale, sans matériel :

```sh
python3 TESTS/neo_720p_20261012/reload_r1_cold_20261022/route9_ddr_io_compare/analyze.py
```
