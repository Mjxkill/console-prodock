# N56r10 : capture interne GAO, candidat Neo isolé

**Résultat actuel : routage terminé, qualification FAIL, non chargé.**
Le détail indépendant est dans [POSTROUTE.md](gao_startup_audit/POSTROUTE.md).
Le journal donne44min31s pour placement/routage. Le bitstream natif
`impl/pnr/ao_0.fs` porte le SHA
`7ca33ea0a54a4ba557319489239e330f6fbfca69840982894ca447a705b05f28`.
Une copie binaire identique `console_neo.fs` permet au qualificateur existant
de lire ce nom ; `bitstream_output_identity.json` consigne cette adaptation.

Setup−0,849ns (64endpoints), hold−0,384ns (13endpoints), recovery−0,364ns,
removal+0,196ns. Les13violations hold nouvelles concernent le GAO/TCK,
pas le domaine d'échantillonnage50MHz. Les résultats ne permettent pas de
qualifier la future lecture JTAG. Les avertissements PR1014 et les huit
horloges PRIMARY étaient déjà présents dans R9 ; les erreurs de lecture
des sections par le qualificateur sont conservées et traitées séparément.

Le VO publié conserve le circuit applicatif mais exclut les primitives GAO.
Les20raccordements sont vérifiés dans la netlist GAO générée ; le rapport
de timing n'expose qu'une partie de leurs chemins physiques. L'audit ne
prétend donc pas avoir vérifié les20terminaisons physiques finales.

À la demande de l'utilisateur, N56r10 ajoute un GAO post-synthèse à la
console complète issue de R9 DMA C150. Le constructeur est
`prepare_gao_startup.py`. Le candidat se trouve dans
`tang/impl/console_neo_n56r10_gao_startup`.

La netlist fonctionnelle VG, les sources HDL, les broches, les contraintes
CST/SDC et les options de routage sont conservées exactement depuis R9.
Seul `source/tang/boards/neo/startup.gao` est ajouté. Les identités parent et
candidat sont enregistrées dans `gao_preparation.json` ; les ROM copiées
sont vérifiées dans `copied_input_audit.json`. Les références Pro Dock
G22r0/R17 restent protégées et aucune carte n'est programmée par le
constructeur.

La campagne locale complète
`TESTS/dual_board/20261024_neo_gao_startup/result.json` passe **11 groupes**.
Cela ne qualifie ni le placement-routage ni le comportement sur carte.

## Capture prévue

- 20 sondes exactes post-synthèse : locks et machines d'initialisation des
  PLL AE350/DDR, DDRinit, deux étapes de reset AE350, deux étapes de
  synchronisation DDRinit, reset issu du CPU et reset vidéo. Deux niveaux
  d'horloges sont conservés comme indices d'activité seulement.
- Horloge indépendante `clk_d`, référence carte **50 MHz**.
- 4 096 échantillons, soit **81,92 µs** ; position de déclenchement 128.
- Déclenchement `ddr_init == 1`, capture automatique initiale activée.
- Une capture forcée ultérieure est nécessaire pour l'état final, ou si
  le déclencheur n'arrive pas. Cette profondeur ne couvre pas toute la
  séquence PLL_INIT, dont certains délais seuls durent déjà 2 ms.
- Les niveaux asynchrones ne donnent pas l'ordre des transitions proches
  à moins de 20 ns. Les clocks 80/75 MHz sous-échantillonnées ne permettent
  pas de mesurer leur fréquence ni d'affirmer leur absence.

L'[audit pré-PNR indépendant](gao_startup_audit/README.md) confirme les
connexions dans le wrapper et dans `gao.v` synthétisé. GAO seul ajoute
**556 LUT, 354 registres, 15 ALU et 6 BSRAM**, selon son rapport de
synthèse. Ce n'est pas encore le total du candidat routé. Le format interne
de stockage a **21 bits**, car le déclencheur est enregistré en plus des
20 sondes ; il ne faut pas interpréter un dump comme une suite de mots
de 20 bits sans le format fourni par l'outil.

## État et conditions d'interprétation

Gowin V1.9.12.03 accepte `add_file -type gao` puis `run pnr`. La génération
GAO post-synthèse, la lecture des deux netlists et les contraintes physiques
sont acceptées ; le placement est lancé. L'étape exacte est dans
`tang/impl/console_neo_n56r10_gao_startup/build.log`.

Le placement a depuis terminé et le journal a atteint
`[60%] Routing Phase 0 completed`. Cela reste une progression du logiciel,
pas une mesure de timing ni un résultat matériel.

Avant un essai matériel, identifier les bitstreams et artefacts produits,
vérifier le timing global et les routes des horloges/resets ainsi que les
connexions GAO après routage. `ROUTED_NOT_QUALIFIED` indique uniquement la
fin du constructeur, jamais une validation.

La configuration GAO change le placement/routage : une capture N56r10 ne
doit pas être présentée comme une capture du bitstream R9 original. Vérifier
d'abord si N56r10 reproduit l'échec CPU/DMI. Un défaut disparu avec cette
instrumentation n'est pas une preuve de correction.

Au lancement du build, la Neo demeure sur **N56r8**, CPU arrêté, mire et LED
vérifiées par caméra après les essais USB. Le jeu R3 reste sur Pro Dock,
qui n'est pas utilisée pour cette expérience.

Une nouvelle photo prise pendant le routage,
`gao_startup_audit/n56r8_before_gao_build_end.jpg`, ne montre plus la Neo
ni son petit écran : la caméra est orientée vers le grand moniteur Samsung.
Cette photo ne confirme donc ni la mire, ni la LED, ni une panne ; le dernier
état visuel exploitable reste celui des essais précédents. Un recadrage a été
demandé sans interrompre la compilation.

Après réponse de l'utilisateur, `gao_startup_audit/n56r8_camera_reframe_01.jpg`
montre de nouveau le petit écran avec le même motif que la photo précédente
des essais USB, ainsi que la LED brillante. Cette comparaison visuelle
n'est pas une mesure de mémoire ni de fréquence.

## Interprétation prévue des mesures

Les noms ci-dessous sont ceux de la netlist figée, pas des signaux ajoutés
dans le chemin fonctionnel. L'interprétation porte sur des niveaux stables
et plusieurs échantillons, jamais sur un échantillon isolé d'un signal
asynchrone.

| Mesure | Ce qu'elle permettra de séparer |
|---|---|
| `pll_lock`, `state_178[2:0]`, `pll_ae350_lock` | Lock brut AE350, séquence PLL_INIT et lock transmis au reset. La LUT synthétisée de sortie vaut `16'h8000` : lock filtré = lock brut ET état111. |
| `ae350_rst_sync[1:0]` | La libération du reset AE350 attend deux fronts bus80 après le lock filtré ; la valeur finale attendue est00. |
| `ddr_init`, `u_soc/init_sync[0]`, `soc_dbg[0]` | Fin d'initialisation DDR puis ses deux étages de synchronisation sur le bus80 ; `soc_dbg[0]` commande POR_N et HW_RSTN du bloc AE350. |
| `u_soc/exts_hrstn`, `vid_hrstn` | Reset sortant du bloc dur, puis sa copie enregistrée vers la vidéo. Une entrée reset libérée ne prouve pas que le bloc dur a déjà libéré ses sorties. |
| `u_soc/pll_lock`, `u_soc/state_0[2:0]`, `soc_dbg_177[1]`, `soc_dbg_2_3` | Lock brut DDR, séquence PLL_INIT, lock filtré et contrôle STOP/ENCLK2. La polarité de STOP doit être lue avec le modèle de PLL, sans l'interpréter à partir de son nom. |
| `vid_hclk`, `gpu_clk` | Niveaux de clocks sous-échantillonnés : activité visible possible, aucune mesure de fréquence, aucune preuve d'arrêt si la trace est constante. |

Si DDRinit reste à1 mais POR_N à0, la capture permet de cibler la chaîne
PLL/reset/synchronisation ; elle ne prouve pas à elle seule un défaut de
FIFO. Si POR_N et les resets sortants restent à1 mais le DMI ne répond
toujours pas, le défaut se situe au-delà de cette condition de démarrage
observée ; la stabilité du core800, le chemin JTAG et les accès mémoire
restent à distinguer. Si N56r10 démarre, ce résultat ne corrige pas
rétroactivement R9 : l'instrumentation a changé le placement/routage.
