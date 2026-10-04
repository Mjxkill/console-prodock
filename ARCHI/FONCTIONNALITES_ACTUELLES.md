# Fonctionnalités actuelles de la console

Inventaire du 4 octobre 2026, build **`gpu_v1_r31`** chargé sur la Pro Dock.
Il passe les simulations, le timing, deux rechargements SRAM avec USB HS et
la suite graphique complète, incluant les douze poses V1 couleur/Z et LCD.
L'endurance passe également : **30 minutes, 58 680 images, zéro erreur
détectée**, avec échos USB et références revérifiées à la fin. R31 est la
[référence archivée](../bitstreams/console_gpu_v1_800.md). Voir le
[contrat GPU V1](GPU_V1.md) et [ses preuves de qualification](../TESTS/TESTS_GPU_V1.md).
Les trois nouvelles scènes sont également confirmées correctes visuellement
par l'utilisateur le 4 octobre.

## Affichage et mémoire

| Fonction | Capacité actuelle |
|---|---|
| Écran | LCD 800 × 480, cadence nominale 55,04 Hz |
| Images indexées | 256 couleurs dans une palette programmable RGB666 |
| Images directes | RGB565 : 65 536 couleurs, conversion vers le LCD RGB666 |
| Résolution réduite | Cible RGB565 400 × 240 agrandie ×2 ; couches, sprites et HUD restent en 800 × 480 |
| Mémoire | DDR3 partagée entre CPU, dessin et affichage ; transferts GPU de 256 bits |
| Pages | 16 emplacements espacés de 1 Mio ; 384 000 octets utiles en indexé, 768 000 en RGB565 ou Z16 |
| Cibles de dessin V1 | Dimensions 1…1024 × 1…512, couleur RGB565 et Z16 disjoints, pas indépendants ; bases et pas alignés sur 32 octets |
| Présentation | Double tampon ; échange au retour vertical pour éviter les déchirures |
| Composition | Tables de couches et de sprites appliquées ensemble au retour vertical |

Une page est une image en mémoire ; une couche choisit quelle partie d'une
image ou d'un décor afficher ; un sprite est un petit objet du compositeur.
Ces capacités ne se multiplient pas : les pages couleur, profondeur et
ressources se partagent les emplacements mémoire.
Les 16 pages sont la convention du pilote historique. L'ABI V1 adresse des
surfaces allouées par l'application dans le premier Gio de DDR ; seules les
tailles 800 × 480 et 400 × 240 sont directement présentables au LCD.

## Couches, sprites et décors

| Fonction | Capacité actuelle |
|---|---|
| Couches | 16 couches superposables ; chaque couche est une surface ou un décor en tuiles |
| Position et fenêtre | Position, recadrage et dimensions indépendants par couche |
| Défilement | Horizontal et vertical au pixel ; plusieurs vitesses permettent la parallaxe |
| Priorités | Couches ordonnées de 0 à 15 ; sprites insérés entre les couches |
| Transparence | Clé de couleur index zéro, activable par couche ; systématique pour les sprites |
| Sprites | 64 sprites matériels de 1 à 32 pixels par axe |
| Retournements | Horizontal et vertical pour les sprites et pour chaque case de tuile |
| Cache des sprites | 64 Kio en BSRAM, ressources actives rechargées pendant le retour vertical |
| Tuiles | 8 × 8, 16 × 16 ou 32 × 32 pixels, taille choisie par couche |
| Jeu de tuiles | Jusqu'à 8 192 motifs différents par atlas |
| Grilles | Largeur 16 à 4 096 cases, hauteur 1 à 4 096, puissances de deux ; étendue limitée à 32 768 pixels par axe |
| Répétition des décors | Bouclage indépendant en X et Y ou arrêt au bord |
| Coût du défilement | Changement des descripteurs, sans redessiner le décor dans une page |

Les 16 couches et les 64 sprites sont les capacités des tables. La scène doit
respecter le budget mémoire de chaque ligne : toutes les combinaisons de
couches plein écran, petites tuiles et sprites ne tiennent pas nécessairement
ensemble. Le matériel compte les dépassements.
La palette est commune aux couches et aux sprites ; sa mise à jour n'appartient
pas à la transaction atomique des descripteurs.

## Dessin 2D accéléré

| Fonction | Capacité actuelle |
|---|---|
| Primitives | Pixel, ligne, rectangle plein, cercle, disque, triangle plein ou contour |
| Découpage | Dessin limité aux bords de l'écran, coordonnées signées |
| Dégradés | Horizontaux, verticaux et diagonaux dans les pages indexées |
| Copies | Copie de rectangles, y compris les chevauchements prévus par le contrat du blitter |
| Texte | Police programmable de 256 glyphes 8 × 16, échelles ×1 et ×2, fond opaque ou transparent |
| Zoom | Agrandissement/réduction, source jusqu'à 128 × 128, index zéro transparent |
| Transformations affines | Rotation, translation, retournement, échelles X/Y distinctes et cisaillement |
| Cache affine | Source indexée jusqu'à 128 × 128, 16 Kio ; capture avant dessin, même en cas de recouvrement source/destination |
| Aplats rapides | Rectangles, disques et triangles regroupés en écritures DDR de 32 pixels indexés |

Zoom et rotation dessinent dans une page. Ils ne tournent pas directement
les 64 sprites matériels pendant l'affichage. L'échantillonnage est au plus
proche voisin ; il n'y a pas de filtrage bilinéaire ni d'anticrénelage.
Ces primitives 2D travaillent dans les pages indexées. Le moteur RGB565
dispose maintenant d'une API dédiée : rectangles et effacements partiels,
copies entre surfaces avec traitement du recouvrement, texte par atlas
ARGB4444, images et quadrilatères pour zoom/rotation. Ces opérations utilisent
les nouveaux moteurs V1 ; les anciennes commandes indexées gardent leur
format et leurs résultats. Le viewport logiciel et le scissor matériel
limitent le dessin dans les nouvelles cibles.

## Dessin RGB565 et première 3D

| Fonction | Capacité actuelle |
|---|---|
| Géométrie | Transformations et projection sur l'AE350 ; découpage proche, élimination des faces arrière et tri logiciel disponibles |
| Filaire | Arêtes dessinées par les lignes accélérées |
| Faces unies | Rasterisation matérielle de triangles, règle de couverture haut/gauche |
| Textures V1 | RGB565 ou ARGB4444 jusqu'à 512 × 512 en DDR, interpolation affine ou corrigée en perspective ; l'ancien moteur 128 × 128 reste disponible |
| Cache de textures | 2 Kio, 64 blocs de 32 octets, réutilisés entre dessins et niveaux ; invalidation explicite après modification des ressources |
| Bords de texture | Rejet, répétition ou limitation au bord, indépendamment en U et V ; répétition pour tailles puissance de deux |
| Transparence de texture | Couleur zéro utilisée comme clé si demandée |
| Alpha | Alpha ARGB4444 par texel combiné à un alpha global 0…256 ; mélange normal ou additif saturé |
| Couleur et éclairage | Modulation RGB ; interpolation de gains par sommet (Gouraud), éclairage préparé par le CPU |
| Distance | Brouillard linéaire selon Z ; mipmaps précalculées par l'outil PC, niveau sélectionné explicitement |
| Profondeur | Z-buffer 16 bits en DDR3, comparaison LESS, écriture activable séparément |
| Effacement | Effacement matériel complet ou partiel des cibles couleur et profondeur, avec scissor |
| Ordre de dessin | Le Z-buffer résout les intersections opaques ; les surfaces translucides demandent encore une gestion d'ordre adaptée |

Le calcul des sommets reste logiciel ; le GPU effectue le dessin des pixels.
Il n'y a pas de shaders programmables, de transformation matérielle des
sommets, de filtrage bilinéaire/trilinéaire, de sélection automatique du LOD,
ni de mélange alpha dans le compositeur des 16 couches. L'alpha et les effets
évolués sont calculés pendant le dessin dans la cible RGB565.

## Perspective et composition sur RGB565

Ces deux fonctions passent les simulations, le timing et leurs références
couleur/profondeur et LCD sur la Pro Dock :

- **Correction de perspective des textures** : interpolation des plans
  UQ, VQ et Q, division matérielle exacte par pixel ; Z16 et alpha conservés.
- **Composition 2D sur fond RGB565** : fond couleur directe derrière les
  16 couches indexées, tuiles et 64 sprites. Texte et interface peuvent ainsi
  rester indépendants d'une scène 3D. Le fond ne consomme pas de couche.
- Présentation atomique du fond et des tables au retour vertical.
- Empreinte de l'image LCD composée et mesure du temps total par ligne.

Voir le [contrat de cette extension](GPU_PERSPECTIVE_COMPOSITION.md).
Sur le précédent build r10, la scène combinée mesure **54,84–55,18 images/s**, un temps maximal de dessin
de **12,881 ms** et zéro ligne manquante. Ces mesures ne garantissent pas
la même cadence pour toute combinaison de couches et de triangles.

## Charges graphiques V1 mesurées sur R31

Les trois nouvelles scènes sont des références graphiques, pas des jeux
jouables. Mode 400 × 240, pas 832, HUD natif ; 240 images mesurées par scène
pendant la suite complète, avant l'endurance avec échos USB.

| Scène | Cadence mesurée | Dessin moyen | Dessin maximal | Intervalle maximal entre présentations |
|---|---:|---:|---:|---:|
| Aventure vue de dessus | 27,40–27,51 images/s | 19,93 ms | 19,995 ms | 54,504 ms |
| Couloir 3D | 27,40 images/s | 29,60 ms | 30,524 ms | 54,503 ms |
| Route | 54,58 images/s | 13,31 ms | 13,370 ms | 36,336 ms |

Le temps de dessin inclut préparation/soumission CPU et attente GPU. Le LCD
continue à rafraîchir à environ 55,04 Hz ; une image rendue peut occuper
plusieurs rafraîchissements. Aucun underflow ni refus ; maximum de composition
496/2556 cycles par ligne dans cette mesure. Le dessin comparatif de
changement de résolution prend 28,464 ms en 400 × 240 contre 102,228 ms en
800 × 480, soit **3,59 fois moins de temps**. Cela ne garantit pas la même
accélération pour toutes les scènes.

## Console, jeu et diagnostic

| Fonction | État actuel |
|---|---|
| Processeur | AE350 RISC-V à 800 MHz, programme C embarqué dans l'ITCM |
| Horloges | Bus 80 MHz, GPU/DDR 75 MHz, LCD 35 MHz |
| Liaison PC | Console de commandes USB CDC, USB High-Speed 480 Mbit/s ; 480 Mbit/s est la vitesse du lien, pas le débit utile garanti |
| API C | ABI V1 documentée, cibles/matériaux/textures et géométrie, commandes ordonnées, publication des caches, attente du dessin et de la présentation |
| Outils de ressources | Conversion PNG vers `.gtex` RGB565/ARGB4444 avec mipmaps, manifeste et SHA-256 ; validation du conteneur dans le pilote |
| Démonstrations | Primitives, couches, sprites, tuiles, transformations affines, cubes filaires/unis/texturés, alpha, perspective et interface 2D superposée |
| Contrôles | Compteurs de commandes, erreurs, refus, fragments, lignes manquantes et charge mémoire ; empreintes d'images et benchmarks |
| Validation | Références de pixels sur hôte, simulations RTL avec attentes DDR et concurrence CPU/affichage, tests USB et tests sur carte |

Le jeu **Mega Coast** dispose d'une route à deux voies, de virages, de
bordures, de cinq voitures en sens inverse, d'arbres, de balises et de
montagnes. Il gère accélération jusqu'à 180 km/h, freinage, inertie,
dérive en virage, ralentissement sur l'herbe, collisions, protection après
choc, parcours de 6 km, chronomètre, arrivée et redémarrage. La simulation
du jeu utilise un pas fixe de 20 ms. Les commandes passent par une manette
Web locale (clavier/souris/toucher) ou une fenêtre native Tk, avec relâchement
automatique en cas de perte des commandes.

Le jeu de course conserve son rendu pseudo-3D existant : l'ajout du moteur
de triangles texturés ne le transforme pas automatiquement en nouveau jeu 3D.
Le son, les ADS1115, les manettes physiques et le chargeur de jeux complet
restent des lots distincts de la [feuille de route](FEUILLE_DE_ROUTE_CONSOLE.md).

## Occupation du build complet

Le build `gpu_v1_r31`, incluant vidéo, DDR et USB, utilise 65 812
éléments logiques (**47,61 %**), 43 754 registres (**31,45 %**), 242 BSRAM
(**71,18 %**) et 83 DSP (**27,85 %**). Les huit horloges PRIMARY sont utilisées.
Ce sont les chiffres de l'ensemble FPGA, pas ceux de la seule IP vidéo.
Le firmware de diagnostic occupe 63 832/65 536 octets d'ITCM et 29 184 octets
de BSS ; un runtime multijeux devra tenir compte de cette place restante.
