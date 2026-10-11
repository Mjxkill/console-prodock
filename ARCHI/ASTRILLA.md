# ASTRILLA — démonstration autonome et géométrie matérielle R19

ASTRILLA est une démonstration autonome de 300 secondes pour la Tang Mega 138K
Pro Dock, avec le cœur AE350 à 800 MHz. Elle recommence en boucle.
Le programme et les ressources sont chargés en mémoire volatile. Aucune carte
SD n’est nécessaire pour son fonctionnement.

La version R19 utilise le moteur de géométrie **G3D1**, sur le FPGA expérimental
**G22r0** déjà sélectionné pour les essais. Elle ajoute des astéroïdes en volume,
des portails métalliques, des anneaux et cristaux en mouvement indépendant,
des arches de pierre dans la poursuite et une floraison cristalline après
l'atterrissage. Les poses et matrices sont calculées en direct ; le FPGA traite
les sommets, le clipping, la projection, l'éclairage et la rasterisation.
Le [compte rendu R19](../TESTS/ASTRILLA_R19_20261011.md) décrit les ajouts,
les preuves et les limites. G22r0 reste non qualifié en timing ; la validation
fonctionnelle de la démo ne change pas ce statut. Le pack C37/R18 est conservé.

## Déroulement

| Temps | Séquence | Mise en scène |
|---|---|---|
| 0–35 s | Le grand départ | Cinq plans de sept secondes : géante gazeuse, flotte, astéroïdes, éclipse et duo planétaire ; approches, demi-tours et éloignements en 3D |
| 35–70 s | Galaxies | Cinq cadrages et trajets propres : débris proches, comète, onde lumineuse, météores et convergence des rayons |
| 70–100 s | Trou noir | Approche accélérée, ciel déformé, disque et anneau lumineux ; l’autre monde grandit au centre pendant la plongée |
| 100–125 s | Passage multidimensionnel | Décor ondulant, portails et géométrie lumineuse |
| 125–130 s | Vitesse lumière | Cinq secondes de stries radiales, anneaux et accélération vers le combat |
| 130–160 s | Bataille | Station armée, vaisseau amiral, sept chasseurs et héros en 3D ; croisements et courbes rapides, traînées, tirs et explosions |
| 160–190 s | Descente sur Elysia | Vue aérienne, entrée dans les canyons, montagnes et survol du relief |
| 190–225 s | Sous la canopée | Intercepteur ennemi, poursuite parmi les plantes géantes et les cascades |
| 225–260 s | Poursuite et sortie | Nouvelle traversée du relief, tir décisif à 245 s, explosion et débris ; découverte de la clairière à 250 s |
| 260–285 s | Atterrissage | Descente, ombre, attitude stable et moteurs éteints au contact ; fougères, lucioles et oiseaux |
| 285–300 s | Fin paisible | Rapprochement de cinq secondes, vaisseau ancré au sol, végétation animée et titre ASTRILLA |

Les plans de descente et de poursuite changent toutes les dix secondes jusqu’à
250 s. Des rochers et arbres en volume passent au premier plan ; des oiseaux
s’envolent pendant les virages en forêt.

Le combat spatial dure exactement trente secondes. La poursuite terrestre
ajoute une autre séquence d’action. Après 160 s, tous les fonds appartiennent
à la planète : aucun retour aux anciens plans de planètes ou de galaxies.
Le temps est déterminé par le compteur CPU et non par le nombre d’images produites.

## Trajectoires et raccords

Les trajectoires partent maintenant de coordonnées **X/Y/Z**, avant toute
projection. Les parcours spatiaux sont des B-splines cubiques fermées, avec
continuité de position, vitesse et accélération. Les appareils parcourent des
boucles et des croisements, passent près de la caméra, repartent au loin et
se présentent de face ou de dos. Deux parcours, des phases, des amplitudes,
des altitudes et des périodes différentes décalent leurs manœuvres. Les appareils
de la flotte suivent un temps absolu continu à l’intérieur de chaque plan.

Le nez anticipe la tangente de 0,34 s dans l’espace et de 0,26 s en poursuite :
le vaisseau commence à pivoter alors que son déplacement conserve encore sa
direction précédente. Cela donne un dérapage pendant le virage. L’accélération
latérale commande le roulis ; une seconde B-spline lisse cette demande pour
éviter une inversion brutale d’inclinaison. Le roulis peut approcher la verticale,
tout en gardant des limites de vitesse et d’accélération vérifiées. Une ligne
droite donne un roulis nul. Cette animation cinématique est évaluée sur le
processeur à partir du temps ; elle n’intègre pas des forces ou une masse.

La poursuite partage un monde avançant à 12 unités/s. Le héros suit l’ennemi
avec 0,48 s de retard et sa propre correction latérale. La caméra suit ce monde,
se place derrière, devant ou sur le côté selon des plans de dix secondes, et
conserve une légère variation de distance et d’angle. Les obstacles proches
sont des objets statiques de ce même monde. Leur position, les positions des
vaisseaux et les directions des coques passent par la même transformation caméra.
Le calcul de vitesse apparente inclut la translation et la rotation de la caméra.
Les traînées et les envols d’oiseaux gardent leur cadence de trois secondes,
indépendamment de la durée du plan.

Les tailles apparentes viennent de la distance et de l’échelle physique des
objets. Leurs profondeurs GPU restent comparables même quand leurs échelles
diffèrent. Les tirs, les jets moteurs et les traînées suivent les appareils.
Les paysages lointains restent des panoramas illustrés en cache ; les vaisseaux
et les obstacles proches sont des maillages réellement projetés et rendus en 3D.

Le repère des ailes conserve une verticale de référence. Le plongeon et le départ
à vitesse lumière gardent les ailes à plat ; l’attitude reste identique avant et
après le contact au sol. Aucun changement d’image ne simule les rotations.
L’intercepteur disparaît au tir décisif et ne revient pas avant le prochain
cycle. L’explosion reste attachée à son point dans le décor.

Le trou noir utilise une lentille radiale non affine. Son rayon augmente sans
retour arrière ; la caméra ne tourne pas. Dès la seconde moitié de l’approche,
l’intérieur révèle le monde suivant. Son ouverture et son échelle augmentent
jusqu’à remplir le cadre. Le dernier fond de la plongée est identique au fond
intérieur correspondant : aucune coupure noire à ce raccord. La géométrie
multidimensionnelle apparaît progressivement pendant le passage.

Le vaisseau posé, l’ombre et les fougères partagent les coordonnées du terrain.
Le point de contact est (440, 270) dans la texture de clairière 800 × 400.
Le zoom final déplace et agrandit ensemble le décor et ces objets. Les fougères
oscillent autour de leur pied ; les lucioles ont seize phases lumineuses ;
les oiseaux sont de petites géométries avec ailes et queues animées.

## Répartition du rendu

Le framebuffer RGB565 400 × 240 est doublé sur le LCD 800 × 480. Le GPU dessine
les vaisseaux 3D, les rochers et arbres proches, les armes de la station,
les planètes maillées, les cristaux, le feuillage
avec alpha, les ombres, les faisceaux, les ondes et les oiseaux. Les planètes
et cristaux emploient de la géométrie, des textures et de l’éclairage. Les
nouveaux cristaux G3D1 utilisent la profondeur et des facettes émissives.

Les couches indexées natives accueillent les textes,
les grandes explosions et les plantes proches pendant la poursuite. Jusqu’à
48 sprites natifs portent les particules ou les lucioles, dont seize particules
dans le passage multidimensionnel de R19. Les couches 12 et 13 servent aux
courts raccords entre plans ; 14 et 15 portent les bandeaux de mesures.

Les paysages lointains restent des illustrations. Les vaisseaux et les obstacles
proches sont de vrais maillages 3D : projection perspective, profondeur, faces
cachées, matériaux texturés et éclairage directionnel. Les anciennes images de
vaisseaux sont encore conservées dans le pack, mais ne sont plus dessinées.
La lentille
est une approximation artistique, pas un calcul de relativité générale.
La coque de la station lointaine est intégrée au panorama de bataille, avec
un filtrage bilinéaire de couleur et d’alpha prémultiplié. Elle reste attachée
au décor pendant le travelling ; sa charge lumineuse et son faisceau sont
animés en direct par le GPU. Ce partage évite de relire et mélanger une grande
texture transparente à chaque image de bataille.

Les fonds filtrés sont préparés au démarrage ; la géométrie, les objets,
les lumières et la composition continuent à évoluer pendant l’animation.
Le filtrage bilinéaire n’a pas été ajouté au rasteriseur FPGA.

## Écran de chargement

Le programme affiche **LOADING** et une progression sur une surface dédiée
(page GPU 7) avant de préparer les fonds. Cette surface reste indépendante des
pages 0 et 1 où les images de scène sont rendues. Le cache se prépare sans
faire défiler ses images sur le LCD.

La commande `L` permet également les tests hors écran : chaque pose est dessinée
et son CRC RGB565 est vérifié pendant que le LCD conserve LOADING. Le contrôle
vérifie alors la somme LCD du texte et de la barre, et non celle de la scène
cachée. L’option `--show-poses` reste disponible pour un diagnostic visuel
explicite. La lecture automatique restaure l’affichage normal.

## Cache de caméras et mémoire

Le stockage de tous les travellings sous forme d’images complètes dépasserait
la DDR. R15 conserve deux formes de cache :

- **1 045 images 400 × 240** : 660 pour la plongée et son ouverture sur l’autre
  monde, 110 pour une période de déformation du passage, 275 pour le zoom final.
- **26 panoramas 576 × 320**, chacun décliné en seize phases de filtrage au
  quart de pixel horizontal et vertical. Chaque plan a ses propres cadrage,
  échelle, inclinaison et trajectoire. Le GPU recopie une fenêtre 400 × 240
  du panorama, avec un pas apparent de 0,25 pixel logique.

Les 1 461 entrées ont deux tailles différentes. Leur adresse, leur pas de
ligne et la fenêtre recopiée sont explicitement décrits. Le modèle hôte vérifie
que la fenêtre du panorama est identique au rendu direct de sa caméra.
Le cache représente des fonds réutilisables, pas un film de 16 500 images finales.

| Usage | Adresse | Taille |
|---|---|---|
| Programme | `0xa0000000`, ILM | moins de 64 Kio |
| Données et pile | `0xa0200000`, DLM | moins de 32 Kio |
| Pages GPU | à partir de `0x00800000` | surfaces et profondeur |
| Ressources | `0x04000000` | taille et SHA-256 dans le manifeste |
| Transfert USB temporaire | `0x08000000` | disque DDR de 32 Mio |
| Métadonnées du cache | `0x09fff000` | une ligne publiée de 32 octets |
| Cache de fonds | `0x0a000000` à `0x1f198600` exclu | 353 994 240 octets, soit 337,595 Mio |

Des assertions contrôlent les séparations et la limite de 512 Mio. Le cache
est invalidé avant préparation. Son identité dépend du CRC des ressources,
de la version du calcul et des onze mots de paramètres de chaque caméra
canonique, y compris la lentille et l’ouverture du portail. Les écritures CPU
sont publiées avant utilisation par le GPU. Les rechargements compatibles
peuvent réutiliser le cache ; une coupure d’alimentation impose sa reconstruction.

## Maillages 3D

`tools/build_astrilla_meshes.py` génère des sommets, normales et indices de
triangles. Les appareils détaillés ont 78 triangles, les chasseurs lointains
18, les rochers 18 et les arbres 48. R19 ajoute des portails de 72 triangles,
des cristaux de 12 triangles et des arches de 60 triangles. En mode G3D1,
le processeur transmet une matrice par instance et le FPGA transforme,
éclaire, découpe et projette les sommets avant le rendu. La profondeur est
commune à tous les maillages de la scène.

Dans l'ancien chemin CPU de référence, le processeur calcule les transformations,
la projection et la lumière ; le GPU rasterise avec correction perspective des
textures et tampon de profondeur. Les faces hors écran ou tournées à l’opposé
sont éliminées. Les faces projetées sur un pixel au plus conservent leur
couverture avec des attributs moyens, afin d’éviter des gradients numériques
non représentables sur les triangles vus par la tranche.

## Construction et chargement

Pour **R19/G3D1**, utiliser le pack séparé et les commandes du
[compte rendu R19](../TESTS/ASTRILLA_R19_20261011.md). Les rendus de référence
doivent recevoir `--hardware-geometry`. Les instructions C37 ci-dessous
documentent le chemin CPU antérieur et ne chargent pas les nouveaux effets G3D1.

```sh
python3 tools/build_astrilla.py
python3 TESTS/test_astrilla_motion.py
python3 tools/render_astrilla.py --sweep --fast --out TESTS/astrilla_reference
```

La chaîne est Gowin GMD 2025.01, RV32IMAFDC/ILP32D, avec `-ffp-contract=off`
pour conserver les mêmes arrondis sur le PC et le RISC-V. Les fichiers produits
sont dans `assets/astrilla/packed/`. Les manifestes enregistrent les empreintes
du programme, des ressources, des sources et du FPGA C37 de référence.

Sur ax15, avec C37 et le programme de transfert USBDISK R4/C4b actifs :

```sh
python3 tools/load_astrilla.py --out TESTS/astrilla_load
```

Le chargeur vérifie l’identité de la carte, l’USB à 480 Mbit/s et la sélection
du disque DDR. Il relit intégralement les ressources transférées, puis charge
et vérifie l’ILM par J-Link sans reset FPGA. L’interface MSC reste détachée
pendant la démonstration. Il n’écrit pas sur la SD physique.

Pour remplacer uniquement le programme avec le même pack déjà résident :

```sh
python3 tools/load_astrilla.py --firmware-only --out TESTS/astrilla_reload
```

Commandes série : `?` identité, `P` pause, `L` chargement/tests hors écran,
`G` reprise, `R` recommencer,
`S` mesures, `T` + entier 16 bits little-endian pour une étape fixe,
`E` + longueur 16 bits + données pour un écho. `C` et `B` servent aux diagnostics.

## Limite actuelle pour un jeu à caméra libre

Les parcours et maillages sont définis dans les ressources et le code ; les
positions, attitudes et matrices des vaisseaux sont évaluées par l’AE350 à
chaque image. Avec G3D1, le FPGA effectue également les transformations des
sommets, le clipping et la projection, puis rasterise les triangles avec
textures, perspective, profondeur et mélange. Ces objets ne sont pas des vidéos
ni des listes de coordonnées animées précalculées.

En revanche, les panoramas et leur cache de vues sont adaptés au scénario de
caméra. Cette partie ne constitue pas un monde 3D librement navigable. La démo
met surtout en valeur le moteur de triangles et exploite peu les tuiles, couches
et sprites natifs, pourtant utiles aux jeux 2D et aux scènes composites.

L'API d'objets maillés instanciables, la caméra libre et les billboards sont
maintenant disponibles dans [G3D1/WORLD3D](GPU_GEOMETRY.md). ASTRILLA R19 utilise
ce moteur pour ses instances animées tout en conservant ses fonds cinématiques.
La qualification du timing FPGA et les performances de WORLD3D restent des
sujets distincts de la validation d'ASTRILLA.

## Bandeaux et compteurs R18

Le titre du chapitre reste affiché en haut (800 × 36). Le bandeau du bas
(800 × 32) indique `FPS`, `SPRITES x/64`, `GPU CMD/S` et `LAYERS x/16+FB`.
Les deux bandeaux occupent les couches natives 14 et 15 ; titres centraux et
iris utilisent 11, 12 et 13. Les particules du combat passent à la priorité 10
pour rester sous l’iris. Les autres objets conservent leur ordre relatif.

Les FPS comptent les présentations terminées, mesurées avec le compteur CPU
64 bits à 800 MHz. Les débits sont recalculés après chaque fenêtre d’au moins
0,5 seconde. Ils ne sont ni le taux théorique de 55 Hz ni la moyenne des cinq
minutes. Une pause ou une pose de diagnostic remet les débits à zéro.

`GPU CMD/S` compte chaque commande de 32 octets effectivement envoyée par
le programme au moteur graphique : copies, états, plans, triangles et dessin
du bandeau compris. Cela ne compte ni les instructions RISC-V, ni les mots
MMIO individuellement, ni les écritures des descripteurs de composition.
Le compteur de commandes terminées du GPU sert de contrôle indépendant.

Les sprites et couches sont les descripteurs activés pour l’image courante,
y compris ceux partiellement ou totalement hors écran. Les maillages 3D ne
sont pas des sprites. Le nombre de couches inclut les deux bandeaux ; `+FB`
désigne le framebuffer RGB565 de base, indépendant des 16 couches natives.
Ces deux nombres changent à chaque image, contrairement aux deux débits
actualisés deux fois par seconde.

Le texte est dessiné par les opérations GPU FILL/TEXT, avec la police native
8 × 16 réinitialisée explicitement (ASCII 32 à 90). Six commandes supplémentaires
suffisent aux valeurs usuelles. Deux surfaces indexées, pages GPU 8 et 9
(adresses `0x01000000` et `0x01100000`), alternent avec le framebuffer pour
éviter d’écrire dans le bandeau en cours de lecture. Seuls leurs 25 600 premiers
octets sont utilisés. Les fonds, ressources, cache de caméra et FPGA C37
restent inchangés. L’écran LOADING masque toujours les poses de vérification.

Le statut série ajoute les valeurs affichées, les commandes de la dernière
image, le cumul 64 bits en deux champs 32 bits (`gpu_cmd_total`, `gpu_cmd_hi`),
`gpu_done`, `layers`, `sprites` et `hud_crc`. Le `printf` embarqué ne prend
pas en charge `%llu`. Le vérificateur Python reconstitue le cumul 64 bits.
`hud_crc` est calculé seulement pour les poses fixes, après invalidation du
cache CPU ; en lecture normale, il vaut zéro.

## Vérification

Le balayage UBSan couvre les 16 500 étapes, les fenêtres des panoramas et les
bornes mémoire. Le calcul de fond C est comparé à un calcul NumPy indépendant ;
le modèle vectorisé de pixels est comparé au modèle scalaire. Les tests de
mouvement couvrent aussi le raccord du portail, le point d’appui au sol,
l’absence de retour dans l’espace et la disparition définitive de l’intercepteur.

Sur le matériel, `tools/check_astrilla.py` compare le CRC RGB565 et la somme LCD
de LOADING (ou de la scène avec `--show-poses`),
puis suit une boucle complète avec des échos USB. Le plafond de rendu est
13,7 millions de cycles CPU ; l’objectif est au moins 54,5 images/s pendant
les diagnostics, sur un LCD d’environ 55 Hz.

```sh
python3 tools/check_astrilla.py --expected TESTS/astrilla_reference/expected.json \
  --out TESTS/astrilla_board --seconds 305
```

Les vidéos de `tools/render_astrilla_movie.py` sont des aperçus logiciels,
sans son ; elles ne constituent pas des captures du LCD ni des mesures de débit.
Le [compte rendu R17](../TESTS/ASTRILLA_R17_20261009.md) donne les preuves des parcours 3D et ses résultats de qualification.
Le [rapport R16](../TESTS/ASTRILLA_R16_20261009.md) conserve la qualification des virages larges précédents.
Le [rapport R15](../TESTS/ASTRILLA_R15_20261009.md) conserve la qualification initiale des maillages 3D.
Le [rapport R14](../TESTS/ASTRILLA_R14_20261009.md) conserve la qualification précédente.

Le [compte rendu R18](../TESTS/ASTRILLA_R18_20261009.md) décrit les compteurs et leur validation.
