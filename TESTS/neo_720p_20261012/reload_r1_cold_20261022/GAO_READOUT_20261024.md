# N56r10 : chargement et premières captures internes

## État carte

N56r10 exact est chargé en SRAM sur la Neo à la demande explicite de
l’utilisateur (« alors charge la N56r10 »). SHA FS :
`7ca33ea0a54a4ba557319489239e330f6fbfca69840982894ca447a705b05f28`.
La caméra montre un écran noir et la LED utilisateur allumée. Le TAP AE350
`0x1000563d` est présent ; l’examen DMI à 100 kHz a expiré après 30 s.
Cette tentative n’a pas permis d’arrêter le CPU.
Pas de Linux, SD, flash ou écriture mémoire GPU/DDR. N56r10 reste en place.
Preuves : [chargement](r10_gao_load_trial/README.md).

La qualification statique reste FAIL : setup −0,849 ns / 64 endpoints,
hold −0,384 ns / 13 endpoints GAO, recovery −0,364 ns, removal +0,196 ns.
Le reset 4 sur LW est toujours rejeté par l’audit. Les résultats initiaux et
la requalification corrigeant le parseur de section restent séparés.

## Accès GAO établi

Trois problèmes du banc logiciel ont été distingués :

1. Un TMPDIR trop long dépasse la limite du socket Unix `gao1`. Les dernières
   sessions emploient un dossier court privé `/tmp/console-gao-*`.
2. L’environnement IDE transmet FreeType système pour compatibilité Ubuntu ;
   le Programmer enfant charge alors un libpng système exigeant un symbole
   absent de son zlib livré. Son erreur `ZLIB_1.2.3.4 not found` était masquée
   par « No Gowin devices found ». Le préchargement local de zlib système
   **en plus** de FreeType corrige le lancement. Aucune bibliothèque installée
   n’a été remplacée. La tentative écrasant FreeType a échoué et est conservée.
3. L’énumération CLI donnait trois lignes Debugger sans identité. La lecture
   directe de FT_GetDeviceInfoDetail identifie sans ambiguïté Neo :
   série `2025041420A`, description `USB Debugger A`, index 2,
   location 12737 = `0x31c1`.
   ESP-Prog CPU : index 0, location 12401 = `0x3071`, description
   `Dual RS232-HS A`. Les interfaces B occupées par le pilote noyau donnent
   des entrées vides. Le scan FPGA `--cable-index 1 --location 12737`
   confirme l’ID `0x0001081b`, famille GW5AS/AST138.
   Les sélections incorrectes conservées dans les essais WINUSB, index 2
   et UID sans suffixe A ont échoué ou lu un autre TAP : elles ne prouvent
   pas une identité Neo valide.

Voir [identification D2XX et scan](gao_cli_research/ft2ch_neo_location12737/),
[conflit de bibliothèque](gao_cli_research/programmer_env_probe/),
[GUI fonctionnelle](gao_cli_research/gui_09_zlib_freetype/).

## Captures

Le CLI installé `gao_sh` est exécuté sous verrou Neo, location 12737,
avec la configuration GAO exacte et `capture_init_data_enabled=true`.
Le chemin logiciel étudié demande `OP_SELECT_CAPTURE_INIT` puis
`OP_READ_CAPTURE_INIT` et saute `startTrigger`. Cela ne prouve PAS que le
contenu est immuable ni que la
lecture n’a aucun effet sur l’acquisition. Les processus serveur/enfant
créés par chaque essai sont arrêtés, aucun autre processus n’est touché.

Chaque CSV contient 4 096 échantillons × 20 signaux. L’export annonce des
microsecondes, mais son incrément est un index ; la période d’échantillonnage
configurée est de 20 ns (`clk_d` à 50 MHz), soit 81,92 µs au total.
Ne pas déduire la fréquence réelle de `vid_hclk` à 80 MHz ou `gpu_clk` à
75 MHz à partir de leurs valeurs échantillonnées à 50 MHz.

- [Lecture 1](gao_cli_research/r10_initial_read_01/initial_core0_window0.csv) :
  DDR init monte au point 126, `init_sync[0]` / POR au point 127.
  `EXTS_HRSTN` et `vid_hrstn` restent à 0. Les deux derniers points
  retombent à 0 pour DDR / init / POR : anomalie
  de bord possible, aucune chute physique n’est affirmée.
- [Lecture 2](gao_cli_research/r10_initial_read_02/initial_core0_window0.csv) :
  DDR / init / POR constamment à 1 ; EXTS / reset vidéo constamment à 0.
  Cette lecture diffère de la première :
  pas une preuve de relecture exacte du tampon initial.
- [Lecture 3](gao_cli_research/r10_initial_read_03/initial_core0_window0.csv) :
  19 colonnes identiques à la lecture 2 ; seul `vid_hclk` change.
  Deux observations ultérieures
  rapportent donc le même état des resets.

Les locks PLL sont hauts, les états `PLL_INIT=111` et `ae350_rst_sync=00`
sur toutes les fenêtres. `PLL_INIT=7` indique la fin de l’initialisation
de la PLL, pas un état prêt du processeur.
Ce constat localise un désaccord entre reset entrant CPU libéré et reset
sortant vers les périphériques maintenu. Il n’établit pas encore la cause du
blocage ni l’intégrité de toutes les mesures (hold GAO en échec). La capture
ne doit pas être promue comme une qualification matérielle.

Voir la [comparaison indépendante](gao_cli_research/capture_analysis/README.md)
et le [chronogramme des resets](gao_cli_research/capture_waveform_root/resets.png).

## Tentatives de routage de l’instrumentation

- R11 : BUFS refusé sur GW5AST (CT1154), avant placement.
- R12 : BUFG accepté syntaxiquement, mais `control0[0]` absent de l’espace
  CST applicatif (CT1135), avant placement.
- R13 : essai d’API backend dans `gw_sh` licencié, arguments refusés faute
  des sept sélecteurs que le frontend précharge en mode Proxy. Aucun placement.
- R14 : mêmes entrées R10, plus un CST GAO séparé ; sept sélecteurs exacts
  préchargés. Contrôle des arguments PASS, les deux CST sont acceptés ;
  routage terminé le 25 octobre. SDC, fréquences et RTL inchangés ; huit horloges PRIMARY
  et dix audits obligatoires.
  Ce routage ne constitue pas un correctif du démarrage.

### Résultat final R14 : aucune différence physique

Le backend termine avec un code de retour nul et produit `ao_0.fs`, mais
le fichier binaire `ao_0.bin` est strictement identique à R10 :
5 270 016 octets, SHA-256
`d6890a96535160d4ace5d27f2bb2fa8ec8c1ec59580ce5e13a30bb46d73f7534`.
Le FS, le VO et le SDF ne diffèrent que par leur date. Le TR ne change
que les chemins d'entrée et la date ; la base de routage et les chemins
de timing sont identiques octet pour octet.

La contrainte a donc été acceptée sans effet observable sur cette
construction. Les marges restent setup −0,849 ns, hold −0,384 ns,
recovery −0,364 ns, removal +0,196 ns ; les 13 violations hold GAO
restent présentes. Neuf audits structurels passent et l'audit du reset
global reste FAIL. R14 n'a pas été chargé ; la Neo conserve R10.

Cette tentative ne permet d'attribuer le blocage du reset AE350 ni au
timing ni à une autre cause. Voir le [rapport post-routage complet](gao_r14_postroute_review/REPORT.md)
et la [comparaison physique](gao_r14_postroute_review/physical_comparison.json).

Campagne commune locale :
`TESTS/dual_board/20261024_luma_living_gao/result.json`, 11 groupes PASS.
Elle reste distincte du timing, du FPGA chargé et des essais de jeu Pro Dock.
