# Écran noir Neo R1 — revue sans accès matériel

La capture de référence est
`TESTS/neo_720p_20261012/reload_r1_cold_20261022/display_observation/openocd.log`.
Linux est actif ; cette revue ne le modifie pas et ne se connecte à aucune carte.
Cette phrase décrit l'état au début de la revue, pas une ancre matérielle
réutilisable : voir le changement d'état signalé ci-dessous.

## Observations et limites

Les trois lectures donnent le bon identifiant `47505531`, une géométrie
1280×720, une base `01700000`, le mode RGB565 actif (`3`), un stride de
2560 octets, la composition active et les sprites désactivés. Le commit
reste occupé. Les images progressent de sept entre les lectures, les
underflows d'environ 5 056, soit presque toutes les 720 lignes par image.
Les compteurs de lignes terminées, checksum et maximum de cycles restent
nuls. Les lectures ne donnent pas les états internes des lecteurs ou de
la file de requêtes.

Un premier traitement de ligne qui ne s'achève jamais explique ces
observations. Les compteurs de durée ne sont publiés qu'à la fin d'un
traitement : leur valeur nulle ne prouve pas qu'aucune requête DDR n'a été
émise. Le commit est appliqué seulement au vblank si `request_idle` ; une
ligne bloquée peut empêcher également la désactivation par un nouveau
commit. Aucune de ces observations ne désigne à elle seule la cause.

`module_comparison.json` vérifie l'identité octet par octet des modules
synthétisés R1 et N57 : `gpu_scanout`, `gpu_line_reader`, `gpu_rgb_reader`,
`gpu_sprite_cache`, `neo_scan_queue` et `ddr_gpu_arb`. Les IP USB modifiées
dans N57 ne constituent donc pas un correctif explicite du scanout.

`control_inventory_v2.json` inventorie les connexions du netlist routé R1 :

- Les horloges scanout pixel, mémoire et bus sont sur PRIMARY.
- `u_gpu/mrst[1]` est sur LW ; il attaque 19 entrées de LUT et un inverseur.
  Ses charges directes ne sont ni des horloges ni des CE. Son pilote est
  `u_gpu/mrst_1_s0`, DFFCE synchronisé par `gpu_clk`, initialisé à zéro.
- Les deux étages `u_scan_queue/up_0_s0` et `up_1_s0` sont locaux. Leurs
  sorties routées sont respectivement `u_scan_queue/up_0[0]` et `up[1]`.
- Aucun autre contrôle de ces trois groupes n'apparaît dans la table des
  ressources globales R1. L'arbitre est
  `u_soc/g_ddr.u_ddr/u_gpu_arb`, pas un module top `u_ddr_arb`.

Le fichier initial `control_inventory.json` et son script archivé restent
conservés ; sa recherche de noms RTL ne résolvait ni l'arbitre ni les alias
des sorties `up`. **Utiliser v2 pour ces éléments.**

Les deux files scanout sont synchrones à `gpu_clk` (75 MHz), pas des FIFO
asynchrones. Le passage pixel→mémoire emploie une boîte aux lettres tenue
avec requête/accusé par toggle ; l'horloge pixel est distincte. L'identité
du RTL et l'inventaire de connexions ne prouvent pas les niveaux physiques.
La Pro Dock fonctionnelle utilise également un reset scanout sur LW ; le
seul mot « LW » ne permet pas de conclure.

## Expérience proposée au propriétaire du matériel

Cette procédure n'a pas été exécutée par cette revue. Elle exige un FPGA
réinitialisé et un CPU garé, avec l'identité de bitstream vérifiée ; elle
ne convient pas à des écritures improvisées pendant Linux.

1. Réutiliser le même R1, ses gardes et son préflight. Vérifier le scanout
   désactivé et le commit inactif. Initialiser une surface RGB565 connue
   de 1280×720 à `0x01700000` (1 843 200 octets), puis en vérifier le contenu.
2. Configurer base `0xe9000004 = 0x01700000`, stride
   `0xe900006c = 0x00000a00`, couches `0xe9000030 = 0`, sprites
   `0xe9000040 = 0`, mode `0xe9000008 = 3`, puis commit
   `0xe900000c = 1`.
3. Après 500 ms, relever trois fois les 30 mots de statut. Distinguer :
   commit achevé, progression des images affichées, progression des images
   récupérées, underflows après amorçage, checksum et contenu vérifié.
   Une progression des images seules ne valide pas le fetch ni l'image.
4. Seulement si le premier test termine, effacer les 128 mots de couches
   de la banque inactive (`0xe9000800`) et les 256 mots sprites
   (`0xe9000c00`), activer les couches, conserver les sprites désactivés,
   puis refaire un commit et les mêmes mesures. Les données RGB restent
   identiques ; la différence est le trajet de composition/pipeline.

Si RGB seul échoue aussi, le discriminant suivant serait l'observation
de `mrst`, `request_toggle`, `request_sync`, `line_pending`, `dispatch_line`,
`rgb_start`, `fetch_valid/ready`, nombre de retours et `acknowledge`.
Une variante de routage ne changeant que `CLOCK_LOC "u_gpu/mrst[1]"
LOCAL_CLOCK` peut être évaluée séparément avec contrôles de netlist et
qualification ; elle n'est ni construite ni proposée comme correction
établie ici. Aucun changement SDC, fréquence ou DDR n'est nécessaire à
la première expérience.

## Résultat du test RGB seul effectué par l'agent principal

`TESTS/neo_720p_20261012/reload_r1_cold_20261022/rgb_only/result.json`
conserve l'échec après rechargement SRAM du même R1. Les 1 843 200 octets
du framebuffer ont été chargés puis vérifiés, CPU garé et arrêté, sans
Linux. Le commit se termine ; le RGB565 est actif, les couches et sprites
sont désactivés. Sur une seconde, le compteur d'images avance de 60,
les underflows de 43 460, le nombre d'images récupérées reste nul ainsi
que le checksum. Le compositeur n'est donc pas nécessaire pour reproduire
le défaut. Ce résultat ne distingue toujours pas reset, demande, lecture
DDR ou retour/accusé.

Le candidat `n56r6_scan_reset_prepared` prépare uniquement l'expérience
de routage R1 avec `u_gpu/mrst[1]` local. Son constructeur
`../build_scan_reset.py` ne change ni logique ni DDR ni SDC. Le manifeste,
le Tcl et le diff exact sont soumis à revue avant toute compilation.
La préparation conserve la preuve des synchroniseurs et des charges,
sans présenter ce candidat comme une correction validée.

## Distinction HDMI et changement d'état matériel

L'utilisateur a précisé ensuite que l'écran indique **aucun signal HDMI**.
Le test de mire interne sans DDR conserve pourtant le checksum calculé
`1ff8f800` et des trames internes qui progressent. Il existe donc une
question supplémentaire sur la sortie/détection HDMI ; les compteurs
internes n'établissent pas la présence du signal électrique ni son décodage.

L'utilisateur a ensuite appuyé sur RESET : l'analyseur a été rechargé
depuis la flash et l'image est immédiatement revenue. Cela confirme le
fonctionnement du matériel, du câble et du moniteur avec ce design.
**Les ancres de CPU/bitstream R1 ne sont plus valables après ce RESET.**
La présente revue ne réalise aucun accès à ce design désormais actif.

R1 transmet `pixel_clk` directement à la paire d'horloge HDMI via un
`ELVDS_OBUF`. Ce chemin ne dépend ni du DCE rapide ni des resets des trois
OSER10. Les données utilisent le DCE `u_video_fast` avec CE=VCC et trois
resets libérés sur front descendant pixel, sans contrôle HDMI promu sur LW
dans le rapport R1. Une absence de décodage HDMI n'est pas nécessairement
une absence physique de l'horloge TMDS ; le statut du moniteur seul ne
permet pas de les distinguer. L'agent principal examine séparément ce
chemin face au design analyseur fonctionnel.
