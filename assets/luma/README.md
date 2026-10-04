# Luma — Le Sanctuaire des lucioles

Démo d'aventure **entièrement automatique**, destinée au LCD 800 × 480 de la
Tang Mega 138K Pro Dock. Aucun bouton, clavier ou contrôleur n'est nécessaire.
La première partie suit un parcours dans la forêt : entrée de la forêt, passage du
pont, trois créatures, gardien de pierre, escalier du sanctuaire, activation
du cristal, puis spectacle des effets du GPU et reprise du voyage. Le PC sert au chargement et aux tests ;
la chorégraphie et la composition tournent ensuite sur la carte.

## Présentation

- Décor original de 1 536 × 1 024 pixels avec caméra mobile, affiché à sa
  résolution native dans une fenêtre 800 × 480.
- Héros à quatre orientations ; poses de repos, deux pas et attaque.
- Slimes violets : rebond, écrasement, attaque, blessure et dissolution.
- Gardien : marche, attaque, fissures et ruines.
- Contact au sol, tri des personnages par leur position verticale,
  éclats d'impact, fragments de cristal, lucioles, feuilles et reflets.
- Animation localisée de la palette de l'eau, apparition du titre,
  chapitres en français, interface native et fondu de boucle.
- Une seule palette RGB666 de 256 couleurs. Transparence par index zéro ;
  pas d'alpha par pixel dans ce chemin de composition.

Il s'agit d'une **mise en scène**, avec combats et déplacements scriptés,
ni d'un jeu jouable ni d'une IA de navigation. Il n'y a pas de son dans cette
version. La qualité et les mesures effectivement vérifiées sur carte sont
consignées dans `TESTS/TESTS_LUMA.md` à la racine du dépôt.

## Ressources et fabrication

`source/` contient les quatre images originales produites avec le skill
`imagegen`, par son outil intégré `image_gen.imagegen` : décor, feuille du
héros, feuille des ennemis et portrait du grand final. Les prompts sont conservés dans `prompts.md`.
Ce sont des créations pour Luma, sans personnage ou ressource repris de Zelda.

`tools/build_luma_assets.py` conserve ces originaux et effectue la conversion
technique : découpe régulière des feuilles 4 × 4, réduction à 64 × 64,
indexation de la palette, découpe de chaque personnage en quatre sprites
32 × 32 au pas matériel de 32 octets. Les interfaces et petits effets sont
construits par le convertisseur. Leurs glyphes proviennent des fontes système
DejaVu Sans et DejaVu Serif. Le décor emploie une surface indexée en DDR ;
le défilement change les coordonnées de lecture, sans redessiner le fond.

Le paquet `packed/luma.bin` contient un en-tête de 1 024 octets, la palette,
le fond, les personnages, les interfaces et les effets. Les régions sont
alignées sur 32 octets et décrites dans `packed/manifest.json`. L'en-tête
contient la signature LUMA, la version 1, la taille et le CRC32 de tous les
pixels et de la palette après l'en-tête. Le firmware exige ce CRC exact.
Le SHA-256 du paquet lie également le firmware aux ressources à charger.

## Construire et voir les références

Depuis la racine du dépôt, avec les mêmes SDK/toolchain AE350 que la console :

```sh
python3 tools/build_luma.py
python3 tools/render_luma.py --sweep --animation
```

La compilation indépendante utilise `fw_console/build/luma/`. Le manifeste
`packed/firmware.json` conserve les empreintes des sources, du firmware,
des ressources et du bitstream FPGA requis. Le générateur de scènes est
partagé : `fw_console/luma_scene.h` s'exécute sur AE350 et sous UBSan sur le PC.
Les poses sont composées par la référence indépendante `tools/gpu_compose.py`.
L'aperçu vidéo MP4 (encodage FFmpeg) représente les pixels attendus, **pas une capture du LCD**.

## Charger sur ax15

Copier dans `/home/michael/console-validation-20261001` le dossier
`assets/luma/packed`, `tools/load_luma.py`, `tools/check_luma.py` et l'archive
`bitstreams/console_gpu_v1_800.fs`. Les outils de validation USB existants et
`bin/openFPGALoader` doivent y être présents. Puis :

```sh
python3 tools/load_luma.py --reload --out TESTS/luma_chargement_unique
```

Le nom de dossier de preuve doit être neuf. Le chargeur sélectionne uniquement
le FTDI **2023112818**, la console **359f:2011 / 11252024 à 480 Mbit/s** et le
J-Link **506005083**. L'option `--reload` charge R31 en SRAM, attend sa nouvelle
énumération, puis charge les ressources en DDR à `0x04000000` et le programme
exécutable dans l'ILM à `0xa0000000`. Le code tient dans les 64 Kio de l'ILM ;
les données et la pile emploient les 32 Kio du DLM (`fw_console/luma.ld`).

Le GPU, ses horloges 800/80/75/35 MHz et le bitstream R31 sont inchangés. Cette
méthode de développement évite une synthèse FPGA pour les itérations du jeu.
Le programme diagnostic d'origine reste dans l'ITCM. Le nouveau programme
est **volatile** : recharger R31 restaure le diagnostic ; il faut recharger
Luma après une coupure ou une reconfiguration FPGA. La flash n'est pas écrite.

Le transfert J-Link s'effectue sans reset, avec le téléchargement flash et
son cache désactivés. L'attachement initial se fait à 100 kHz, puis le transfert
à 1 MHz. Les données sont vérifiées avant le saut au point d'entrée ELF ; le
programme publie le cache DDR et contrôle son CRC avant de présenter le décor.
Voir les commandes officielles SEGGER
[LoadFile / SetPC](https://kb.segger.com/J-Link_Commander) et
[DisableFlashDL / SetAllowFlashCache / InhibitConnectRetries](https://kb.segger.com/J-Link_Command_Strings).
Un `loadfile` implicite avec reset ne convient pas à cette reprise sur DDR déjà
initialisée. Le chargeur ne demande aucune action sur les autres compilations.

## Diagnostic, sans commande de jeu

La démo démarre et boucle seule. Les commandes ci-dessous servent uniquement
aux tests via la console USB exclusive (un seul programme connecté) :

| Commande | Effet |
|---|---|
| `?` | Identité du programme |
| `P` | Pause de la séquence |
| `G` | Reprise automatique et remise à zéro des compteurs de débit |
| `T` + numéro uint16 little endian | Position exacte, pause, attente de trois images, compteurs/hash |
| `S` | Compteurs, hash LCD, image courante, erreurs, CRC initial |
| `E` + longueur uint16 LE + octets | Écho binaire exact, réception bornée dans le temps |

Pour l'aventure indexée, le hash LCD porte sur les indices des pixels. Pour
les effets RGB565, le test compare aussi le CRC du framebuffer entier et la
somme RGB666 des pixels composés au LCD. La validation visuelle sur l'écran
reste distincte de ces vérifications.

## Suite R2 : démonstration des effets du GPU

Après l'activation du sanctuaire, cinq tableaux prolongent l'aventure :

1. **Le passage** : le décor passe à une palette de nuit, les anneaux se
   déploient, trois lumières colorées tournent autour du sanctuaire.
2. **Entre deux mondes** : un portail révèle une autre partie du paysage.
   Ses coordonnées de texture tournent et se déforment dans un maillage affine de 24 triangles ; l'intérieur apparaît progressivement en transparence.
3. **Le cœur de lumière** : un cristal à huit facettes s'agrandit et tourne,
   entouré de trois fragments en orbite. Les facettes sont texturées, éclairées
   par sommet, projetées en perspective et cachées par le tampon de profondeur.
4. **L'éveil** : les ondes traversent les anneaux, jusqu'à 56 sprites ajoutent
   les gerbes et les scintillements.
5. **LUMA** : une lumière grandit jusqu'à couvrir l'écran entier. Un portrait
   du héros de 352 × 440 pixels se lève à gauche ; le titre LUMA grandit à
   droite. Trois anneaux tournent derrière le titre, avec lumières mobiles et
   étoiles devant et derrière le portrait. La carte finale reste animée avant
   la reprise automatique de l'aventure.

La suite utilise les **commandes matérielles V1** : copies RGB565, triangles
texturés, interpolation de perspective, Z16, éclairage Gouraud, alpha uniforme
et addition des lumières. Les halos dynamiques sont des éventails de triangles
Gouraud additifs, pas des images d'explosions préenregistrées. Le décor indexé,
les personnages et l'interface restent issus des ressources Luma originales.
Le corps de la suite emploie un framebuffer RGB565 **400 × 240 agrandi ×2**
par le GPU. Les sprites, le portrait, le titre et l'interface sont composés
ensuite en **800 × 480 natif**. Deux surfaces alternent au retour vertical ;
le fond est restauré chaque image. Pendant la croissance de la lumière,
seules les bandes extérieures à un rectangle intérieur garanti opaque sont
copiées : la lumière réécrit entièrement le reste. Une recherche directe
vers une phase quelconque reste ainsi déterministe, même après le grand final.
L'éclairage d'ambiance fixe est calculé une fois par le GPU au démarrage.

Le chargement R2 démarre directement sur la nouvelle séquence pour la rendre
visible immédiatement ; après le grand final, l'aventure entière recommence.
Le nombre de phases passe de 5 600 à **8 320**, dont 3 200 pour les effets.
La cadence réelle et les résultats sur carte sont à lire dans la fiche de test,
pas à déduire du nombre de phases.

Le modèle hôte réexécute le flux de commandes préparé par le même code C
`luma_fx_scene.h` avec la référence indépendante `TESTS/test_gpu_v1.py`.
Les tests comparent le CRC32 de tout le framebuffer RGB565 et la somme des
couleurs réellement composées pour le LCD. Les petites facettes vues par la
tranche, de moins de huit pixels d'aire après projection entière, sont éliminées
avant de préparer des gradients Z non représentables ; aucune grande face ni
origine Z n'est écrêtée pour masquer une erreur.

Pour une modification du programme seule, sans changement du paquet de
ressources déjà chargé :

```sh
python3 tools/load_luma.py --firmware-only --out TESTS/luma_rechargement_unique
```

Ce chemin a été testé sur R1 (2,8 secondes). Les fichiers `luma_fw.bin` et
`firmware.json` doivent correspondre au paquet présent en DDR ; le CRC de
l'application vérifie aussi cette correspondance à chaque lancement.

Le portrait final est produit par l’outil intégré imagegen, avec la feuille du
héros comme référence d’identité. Le prompt exact et le chemin de la source
transparente figurent dans `prompts.md`. Les tailles du logo sont calculées
depuis la typographie DejaVu ; il ne s’agit pas de nouvelles images générées.
