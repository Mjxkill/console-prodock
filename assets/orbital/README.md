# Orbital — Station Aurora

Démo de tir à la première personne **entièrement automatique**, dans l'esprit
des opéras spatiaux sur console, pour le LCD 800 × 480 de la Tang Mega 138K
Pro Dock. Aucun bouton ni contrôleur. La boucle dure **4 minutes** (13 200
phases à 55 images/s) et traverse sept lieux de la station Aurora :

1. **Sas d'amarrage** : couloir vitré sur un monde-anneau, premiers drones.
2. **Baie d'observation** : plate-forme à ciel ouvert, tour d'accès.
3. **Monte-charge** : descente de 900 unités devant une verrière panoramique.
4. **Salle du réacteur** : piliers, cœur lumineux qui pulse et éclaire le décor.
5. **Le Gardien** : grande machine de guerre avec jauge et escortes.
6. **Alerte** : éclairage rouge, explosions en chaîne, course vers la sortie.
7. **Pont extérieur** : derniers drones, renforts, lever de lumière et titre.

Il s'agit d'une **mise en scène** : déplacements, tirs et destructions sont
scriptés (32 ennemis de quatre sortes) ; ce n'est pas un jeu jouable. Il n'y a
pas de son. Les mesures et preuves vérifiées sur carte sont dans
`TESTS/TESTS_ORBITAL.md`.

## Ce que la démo montre du GPU

La référence initiale est R31. La version GPU/SD/USB qualifiée le 9 octobre
utilise le FPGA C37 avec les mêmes ressources et le même programme R6 :
51 poses exactes et 54,81 images/s sur 520,8 s, sans erreur.
Les preuves et limites figurent dans `TESTS/CORRECTIONS_REVUE_20261008.md`.
L'inscription « R31 » de l'application n'identifie pas le FPGA chargé.

- Rendu RGB565 400 × 240 agrandi ×2 par le matériel, double tampon, tampon
  de profondeur Z16 ; salles reliées par des portes coulissantes, hauteur de
  caméra variable, caméra en précision fine.
- Effacements rectangle couleur + profondeur (sols, plafonds, murs), copies
  RGB565 (deux ciels, illustration d'ouverture).
- Textures en perspective, ennemis ARGB4444 avec transparence, additif,
  Gouraud, brouillard matériel, alpha global.
- **Mipmaps** (emblème 512 de la baie), **répétition et clé de couleur**
  (poutrelles du monte-charge), **rotation** de quads (éclaireurs).
- **Rendu dans une texture** et **texte GPU** : écrans muraux calculés à
  chaque image.
- **Moteur 2D indexé** : la page d'interface (détecteur de mouvement avec
  balayage, compteurs, horloge, bouclier en dégradé) est dessinée par
  disques, cercles, lignes, texte, dégradé et aplats, sans pixel écrit par
  le processeur.
- **Décor en tuiles** défilé par le compositeur (bandeau d'alerte, tuiles
  retournées), **palette animée** (interface rouge pendant l'alerte),
  sprites retournés, 11 couches natives 800 × 480.
- **Le fusil vise** : 17 images pré-tournées ; il se tourne vers la cible
  avant de tirer, recule, et ses tirs voyagent jusqu'à elle.
- Éclairage dynamique calculé par le processeur : éclair de tir, lueur des
  explosions, lumière du cœur, alerte rouge, brume, lever de lumière final.

Le comptage des commandes par fonction est dans `TESTS/TESTS_ORBITAL.md`.

## Pourquoi le sol et les murs sont tracés en rectangles

Mesuré sur la carte, R31 remplit un rectangle « effacé » (opcode 28, couleur
et profondeur) environ vingt fois plus vite qu'un triangle : 5,5 cycles CPU
par pixel contre 93 à 190. La caméra d'Orbital ne fait que tourner autour de
l'axe vertical : chaque ligne d'écran d'un sol ou d'un plafond a une seule
profondeur, et chaque colonne d'un mur vertical aussi. La scène trace donc :

1. les murs en barres verticales, larges près de la caméra, qui débordent un
   peu de leurs bords inclinés ;
2. le ciel des baies vitrées et de la cloison ouverte, ligne par ligne ;
3. le sol et le plafond ligne par ligne, avec l'éclairage et la profondeur
   exacts de la ligne : ces lignes recoupent exactement les bords des murs ;
4. en triangles, tout le reste (panneaux, montants, drones, lumières).

Le premier essai entièrement en triangles tournait à 27 images/s dans le
couloir ; cette version tient la cadence du LCD. Détails et chiffres dans la
fiche de test.

Le niveau est une suite de **salles convexes alignées en profondeur**
(`orb_cells`). On dessine d'abord le ciel des salles ouvertes, puis les salles
de la plus lointaine à la plus proche, chacune restreinte au rectangle d'écran
que laissent voir les portes qui la précèdent : les murs et sols plus proches
recouvrent simplement ce qui est derrière. Les objets isolés (piliers,
caisses) sont des blocs tracés après le sol de leur salle ; drones et effets
passent en dernier avec le test de profondeur.

## Ressources et fabrication

`source/` contient les trois images de la première session (ciel, arme,
feuille de quatre poses de drone, outil `image_gen.imagegen`). `source/gen/`
contient les images produites ensuite sur le ComfyUI local de gx10-1 par
`tools/orbital_art.py` (Qwen-Image et Qwen-Image-Edit, description dans
`art.json`) : le Gardien, l'élite et l'éclaireur en quatre poses chacun, le
ciel d'aube du niveau inférieur, l'illustration d'ouverture et cinq textures
de décor. Tous les prompts sont dans `prompts.md`. Ce sont des créations pour
Orbital, sans élément repris d'un jeu existant.

`tools/build_orbital_assets.py` convertit le tout :

- Fusil : 17 images tournées autour d'un pivot du bord inférieur, sur une
  toile de 512 × 320, avec la position de la bouche du canon pour chacune.
- Ennemis : détourage du fond vert, cadrage commun aux quatre poses, ARGB4444
  en 128 × 128 (256 × 256 pour le Gardien), masque 8 × 8 des cellules non vides.
- Deux ciels 512 × 256 et l'illustration 400 × 197 en RGB565.
- Textures de décor 128 × 128 en RGB565.
- Interface (détecteur, chiffres, jauge, titres en DejaVu Sans) : procédurale,
  indexée sur une palette de 256 couleurs.

`packed/orbital.bin` (5,8 Mo) : en-tête de 1 024 octets (signature `ORBI`, version 1,
taille, CRC32), puis les régions alignées sur 32 octets décrites dans
`packed/manifest.json`. Le firmware exige le CRC exact avant d'afficher.

## Construire et voir les références

```sh
python3 tools/build_orbital.py
python3 tools/render_orbital.py --sweep --prove --animation
```

`fw_console/orbital_scene.h` est partagé entre l'AE350 et le PC. `--sweep`
exécute les 13 200 phases sous UBSan (table de sinus, présence de la station,
64 sprites au plus). `--prove` vérifie que chaque phase est identique, octet
pour octet, à la même phase rendue avec une copie de ciel plein écran depuis
une mémoire empoisonnée : aucun pixel ne dépend d'une image précédente. Les
poses sont rendues par le modèle indépendant de `TESTS/test_gpu_v1.py`.
L'aperçu MP4 représente les pixels attendus, **pas une capture du LCD**.

## Charger sur ax15

Copier `assets/orbital/packed`, `tools/load_orbital.py`, `tools/load_ilm.py` et
`tools/check_orbital.py` dans `/home/michael/console-validation-20261001`, puis :

```sh
python3 tools/load_orbital.py --fast --out TESTS/orbital_chargement
python3 tools/check_orbital.py --expected TESTS/orbital_20261005/reference_r6/expected.json --out TESTS/orbital_controle
```

Le nom du dossier de preuve doit être neuf. Ces commandes conservent le
FPGA déjà chargé et nécessitent les 51 références R6 sur ax15. Leur copie
dans ce dépôt est `TESTS/orbital_20261005/reference_r6/expected.json`.
`--reload` recharge spécifiquement l'ancienne référence R31 en SRAM puis
charge ressources et programme par J-Link : ne pas utiliser cette option
pour conserver C37. Tous ces chargements sont volatiles, flash intacte.
`--firmware-only` ne recharge que le programme (5 secondes) quand les
ressources sont déjà en DDR. Le chargement complet prend 5 à 9 minutes par
J-Link (20 ko/s ; 332 s avec `--fast`) ; pendant ce temps le processeur est
arrêté et **l'écran reste figé, ce n'est pas un plantage**. `--fast` supprime
la relecture J-Link (le programme vérifie de toute façon le CRC32 des
ressources avant d'afficher). Le contrôle exige les poses exactes, puis
54,5 images/s au moins et un temps de dessin maximal de 13,7 M cycles CPU
(17,1 ms) pendant l'endurance, tous compteurs d'erreur à zéro.

Commandes UART du programme : `?` identité, `S` état, `P` pause, `G` reprise,
`T` + phase (pose exacte), `E` écho binaire, `B` et `M` bancs de mesure du
temps de dessin (sans effet sur la démo).
