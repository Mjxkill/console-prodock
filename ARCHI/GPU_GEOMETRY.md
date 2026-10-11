# Géométrie 3D matérielle G3D1

Travail commencé le 10 octobre 2026. Le statut de qualification et les résultats
sur carte doivent être lus dans `TESTS/GPU_GEOMETRY_20261010.md`.

## Répartition des calculs

Le FPGA lit les maillages en DDR, transforme leurs sommets par une matrice
affine 3×4, découpe les triangles contre les six plans de la caméra, calcule
la projection perspective, élimine les faces arrière, calcule l'éclairage
directionnel et les plans d'interpolation. Il transmet ensuite ces triangles
au rasteriseur GPU V1 existant : textures, perspective par pixel, profondeur,
transparence et écriture RGB565 restent matériels.

Le processeur AE350 calcule la logique du jeu, la physique, la caméra et les
matrices des objets. Il prépare les ressources et envoie les commandes.
Il ne transforme plus chaque sommet et ne calcule plus les gradients de
chaque triangle. Une commande DRAW référence un maillage entier. Les matrices
peuvent changer à chaque image en fonction des entrées du joueur.

Le cache des sommets contient 256 positions transformées. Les faces partagent
ces résultats pendant un DRAW ; plusieurs DRAW peuvent réutiliser le même
maillage source en DDR avec des matrices et matériaux différents. Deux
diviseurs signés 64 bits travaillent en parallèle pour les gradients X/Y.
Chacun traite deux bits de quotient par itération avec trois soustractions
parallèles (radix 4), pendant 32 itérations, plus les étapes de préparation
et de signe. Les différences, multiplications et additions des attributs sont
séparées par des registres. Les deux banques de découpage sont conservées
dans une RAM interne double port de 32×160 bits, avec lecture synchrone.
Le moteur fonctionne dans le domaine mémoire existant, sans nouvelle horloge.

Les coefficients de matrice, les attributs des trois sommets et les données
de projection sont enregistrés avant les produits DSP. La normalisation
de projection contrôle la plage signée avant d'utiliser des produits
32×32 ; l'éclairage utilise trois produits signés 16×16 et une somme sur
34 bits. Ces étapes visent le timing physique sans réduire les formats
publics ni les fréquences.

La lecture de Z et la préparation du diviseur de projection sont également
séparées. Les produits des gradients possèdent quatre registres dédiés :
différences écran signées sur 12/11 bits pour X/Y, différences d'attributs
sur 41 bits et produits sur 53 bits. Ces largeurs couvrent le viewport maximal
1024×512 ; les sommes et divisions restent sur 64 bits.

Les sommets projetés d'un polygone sont conservés dans une RAM synchrone
16×104 bits. Les trois sommets de chaque triangle sont lus successivement,
ce qui remplace les sélections larges entre banques de registres. Les résultats
et prédicats de validité des divisions passent également par un étage de
registres avant d'être consommés ; les formats numériques restent identiques.
Les produits U×Q et V×Q sont enregistrés par sommet avant le calcul des plans,
avec une échelle affine de 65536 lorsque la perspective est désactivée.

Chaque sommet conserve aussi ses six bits de position par rapport au frustum.
Un triangle dont les trois sommets sont dans le champ passe directement à la
projection. Les autres triangles gardent le découpage complet. Pour une arête
partagée, l'intersection est toujours interpolée du sommet intérieur vers le
sommet extérieur : le sens de parcours du triangle ne change plus l'arrondi
des coordonnées. Cela évite une fissure d'un pixel au plan proche.

Les sprites 3D sont des quadrilatères texturés partageant un maillage. Ils
acceptent position en profondeur, taille, rotation dans le plan, transparence
et occultation par la scène. Ils utilisent ce pipeline ; ils sont distincts
des 64 sprites natifs du compositeur 2D. Leur quantité est limitée par le
budget de rendu, pas par les 64 emplacements du compositeur.

## Intégration

- RTL : `tang/rtl/video/gpu_geometry.v`, `gpu_geom_div.v`.
- File d'entrée, arbitrage DDR et fence : ceux du GPU existant.
- Moteur de pixels : `gpu_v1.v`, avec un chemin opaque plus court, sans
  modification des résultats RGB565, de la profondeur ou des matériaux.
- Cache de texture : `gpu_texture_cache.v`, 32 Kio, recharge une
  ligne DDR complète en une écriture RAM interne. Il utilise davantage de
  largeur mémoire interne pour supprimer quinze cycles par défaut de cache,
  et conserve 1 024 lignes DDR, soit une texture RGB565 128×128 entière.
- Division perspective : `gpu_perspective.v`, chemin exact sur 12 bits pour
  les UV répétés entre 256 et 4095 ; les autres plages restent exactes.
- API : `fw_console/gpu_geometry.h` et `.c`.
- Adaptateur des maillages ASTRILLA : `fw_console/astrilla_geometry.h`.
- Monde sans cache d'images de caméra : `world3d_scene.h`, `world3d_main.c`.
- Modèle entier indépendant : `tools/gpu_geometry_model.py`.

L'accès CPU aux registres vidéo et aux deux fenêtres USB passe par
`video_bus_stage.v`, entièrement dans le domaine bus 80 MHz. Cet étage
sérialise la transaction et enregistre sa réponse, y compris les attentes
et les accès consécutifs. La réinitialisation commune annule une transaction
en cours. Les FIFO et domaines d'horloge USB restent ceux du projet.
La lecture d'un registre du GPU insère aussi une attente AHB : la réponse
est enregistrée près du GPU avant son trajet vers le pont. Les écritures
conservent leur protocole et leur débit. Le signal USB de restitution après
abandon est enregistré en parallèle du compteur ; sa durée reste exactement
celle du test `handback != 0`, sans cycle de purge ajouté ou supprimé.

Les deux rasteriseurs partagent un étage de demande/réponse DDR enregistré.
Le choix du moteur reste stable jusqu'à sa fin de commande ; une fence ne
termine qu'après les écritures. L'ancien rasteriseur gagne quelques cycles
de latence de transaction, sans changement de ses commandes ou résultats.

L'affichage dispose d'une file synchrone de deux demandes devant l'arbitre
DDR. L'acceptation côté affichage signifie entrée dans cette file, tandis
que les réponses restent ordonnées et que les seize tags de lectures DDR
sont comptés à l'émission réelle. Cette file coupe le retour combinatoire
depuis la DDR vers le multiplexeur des lecteurs et conserve un débit d'une
demande par cycle lorsque la DDR accepte continuellement.

Les commandes 22 à 30 et les registres GPU V1 conservent leur ABI. Le registre
de capacités V1 reste `0x1ff`. Il faut vérifier séparément la signature G3D1
avant d'utiliser les nouvelles commandes. Aucun repli logiciel automatique
n'est effectué si le matériel manque.

## ABI des commandes

Une commande contient huit mots de 32 bits. L'opcode occupe les bits 31:24 du
mot 0 ; ses 24 bits inférieurs doivent être nuls. Les mots réservés sont nuls.
Les adresses sont des adresses physiques DDR en octets.

| Opcode | Commande | Mots utiles |
|---|---|---|
| 31 | MATRIX | w1 : ligne 0..2 ; w2..w5 : quatre coefficients signés Q16.16 |
| 32 | CAMERA | w1 : near ; w2 : far ; w3/w4 : focales X/Y Q16.16 ; w5 : centre X/Y ; w6 : largeur/hauteur |
| 33 | LIGHT | w1 : direction X/Y Q1.15 ; w2 : Z Q1.15 dans les 16 bits bas ; w3 : ambiant/diffus |
| 34 | DRAW | w1 : sommets ; w2 : faces ; w3 : nombre de sommets/faces ; w4 : élimination arrière 0 ou 1 |

Pour les couples X/Y et largeur/hauteur, le premier champ occupe les 16 bits
hauts. Dans LIGHT w3, ambiant occupe les 16 bits bas, diffus les 16 bits hauts.
Les deux gains sont dans 0..256.

Le repère caméra a X vers la droite, Y vers le bas et Z vers l'avant. Une face
avant a une aire projetée signée négative. La matrice comprend déjà la vue de
la caméra : `model_view = view × model`. Il faut écrire ses trois lignes avant
le premier DRAW après reset.

CAMERA doit suivre le dernier TARGET. Son viewport doit être identique à la
cible, de taille au plus 1024×512. `near >= 1/16`, `far > near`, focales entre
1 et 4096 pixels ; chaque pente du frustum est au plus 8. Changer TARGET
invalide CAMERA. Le centre peut être situé sur les bords du viewport.

Les trois coordonnées et les coefficients sont en Q16.16 signé. Un débordement
de position transformée est signalé comme erreur, jamais rabattu modulo 32 bits.
La projection conserve une réciproque fixe ; la quantification finale est au
pixel du framebuffer. Les fonds et HUD natifs peuvent rester en 800×480.

## Ressources des maillages

Les deux bases sont alignées à 32 octets. Un DRAW accepte 1..256 sommets et
1..65535 faces ; les deux plages doivent rester dans les 512 Mio de DDR.
Les grands objets doivent être découpés en sous-maillages.

Les maillages doivent rester immuables jusqu'à la fence, y compris vis-à-vis
des écritures GPU : leurs plages ne doivent pas chevaucher les cibles couleur
ou profondeur utilisées pendant leur dessin. Le frontal valide les bornes DDR
et les descripteurs, mais ne vérifie pas ces chevauchements entre ressources.

Un sommet occupe 32 octets : X, Y et Z int32 Q16.16 puis cinq mots réservés
nuls. Une face occupe également 32 octets :

| Mot | Contenu |
|---|---|
| 0 | indices A/B/C sur les octets bas ; drapeaux sur l'octet haut |
| 1..3 | U dans les 16 bits hauts, V dans les 16 bits bas, int16 en texels |
| 4 | normale X/Y Q1.15 |
| 5 | normale Z Q1.15 dans les 16 bits bas |
| 6 | gains R, G, B de 9 bits, positions 0, 9 et 18, chacun 0..256 |
| 7 | réservé, zéro |

Drapeaux : bit 0 émissif (éclairage à 256), bit 1 double face. Les autres bits
sont réservés. Un indice hors plage ou un gain invalide provoque une erreur.
Le dessin n'est pas transactionnel : une face invalide découverte après des
faces valides peut laisser un résultat partiel. Ne présenter une image que
lorsque la fence est passée et les compteurs d'erreurs sont restés nuls.

La validité d'un matériau ou d'une cible est celle du contrôle complet du
moteur V1. Le frontal attend sa fin de commande avant de l'accepter pour
DRAW/CAMERA. Un descripteur refusé ne peut pas être rendu valide par la
modulation d'éclairage, et une cible refusée ne conserve pas ses dimensions
comme configuration caméra utilisable.

L'éclairage Lambert est plat par face. La direction de lumière est exprimée
dans le repère de l'objet. Cela convient aux rotations et échelles uniformes.
Pour une échelle non uniforme, fournir des normales corrigées ou utiliser un
matériau non éclairé. L'ABI de géométrie n'accepte pas le drapeau Gouraud ;
l'ancienne API raster Gouraud reste disponible.

DRAW utilise la texture et le matériau V1 courants. Il restaure le matériau à
la fin, y compris après une erreur de maillage, mais modifie les plans d'interpolation ; reconfigurer ceux-ci avant
de mélanger du raster bas niveau. Les sprites translucides doivent être
dessinés après les objets opaques, triés du fond vers l'avant, avec test Z
actif et écriture Z désactivée. Ce tri relève du moteur de scène.

Un triangle extrêmement mince peut produire un gradient hors int32. Le bloc
utilise alors la moyenne constante de cet attribut et incrémente `slivers`.
Ce cas est observable ; ce n'est ni un débordement silencieux ni une garantie
de qualité pour tous les maillages. La qualification vérifie les compteurs
contre les références de chaque vue. Sur les 6 600 poses du monde de test,
quatre faces déclenchent ce cas pour la profondeur ; leur couverture est
nulle selon la règle du rasteriseur, donc aucun pixel n'est approximé.

## Registres de diagnostic

Base AHB : `0xe9001000`. Les compteurs sont cumulatifs modulo 2³², synchronisés
vers le domaine AHB ; lire les différences après la fence du GPU.

| Offset | Valeur |
|---|---|
| 0x48 | signature `0x47334431` (`G3D1`) |
| 0x4c | erreurs de géométrie |
| 0x50 | sommets transformés |
| 0x54 | triangles transmis au rasteriseur |
| 0x58 | faces/triangles éliminés ou dégénérés |
| 0x5c | intersections créées pendant le découpage |
| 0x60 | approximations d'attributs sur triangles minces |
| 0x64 | cycles d'activité du bloc de géométrie |

Les cycles d'activité incluent l'attente du rasteriseur pendant un DRAW.
Ils ne mesurent donc pas uniquement les opérations arithmétiques. Le compteur
V1 `rejected` agrège les rejets de géométrie et de pixels. Les compteurs de
commandes du HUD mesurent les commandes envoyées par le CPU : les nombreuses
commandes raster internes générées par un DRAW n'y sont pas comptées.

## API minimale

```c
gpu_v1_context gpu;
gpu_v1_init(&gpu, gpu_submit);
/* Configurer TARGET, SCISSOR, texture et matériau avec gpu_v1_*. */
if (!gpu_geom_supported()) return FAIL;
if (!gpu_geom_set_camera(&gpu, &camera)) return FAIL;
/* Après modification des ressources par le CPU : */
gpu_publish_surface(mesh.vertices, mesh.vertex_count * 32);
gpu_publish_surface(mesh.faces, mesh.face_count * 32);
if (!gpu_geom_instance(&gpu, &mesh, &model_view, &object_light, 1)) return FAIL;
if (!gpu_wait() || gpu_v1_rejected()) return FAIL;
/* La ressource peut maintenant être réutilisée ou modifiée. */
```

`gpu_geom_fixed` refuse NaN, infini et dépassement de Q16.16.
`gpu_geom_instance` valide toute la requête avant d'envoyer sa première
commande. La protection de propriété des buffers reste à la charge de
l'application : aucune écriture CPU ou disque ne doit modifier un maillage
pendant sa lecture par le GPU.

## Monde à caméra libre

La scène de test dessine un sol, 12 arbres/rochers, quatre vaisseaux et
24 sprites lumineux. Les maillages sont chargés à `0x06000000` ; aucune image
de caméra n'est mise en cache. Le mode automatique calcule une vue à chaque
image. La commande USB `V` fournit directement une autre caméra et un objet,
ce qui permet de tester une situation impossible à obtenir en rejouant
uniquement une cinématique préétablie.

Le paquet `V` contient neuf float32 little-endian (36 octets) suivis du CRC32
des 36 octets : caméra X/Y/Z, yaw/pitch, acteur X/Y/Z, orientation de l'acteur.
Les angles sont en tours/256. Les valeurs sont bornées à ±512 ; pitch est
borné à ±56. La réception est limitée à 200 ms pour le paquet entier. Une
erreur CRC, une valeur invalide ou un paquet incomplet ne remplace pas l'état.
`T` + uint16 little-endian rend une phase en pause ; `R` relance l'automatisme ;
`G` reprend avec la caméra courante ; `P` met en pause ; `S` lit les mesures.

ASTRILLA utilise le même bloc pour ses objets 3D. Ses fonds de cinématique
conservent leur préparation existante : l'intégration géométrique ne les
transforme pas implicitement en univers 3D. Le monde à caméra libre sert à
valider séparément ce dernier usage.

## Construction et tests

`tools/build_gpu_geometry.py --name <nom_neuf>` crée une compilation isolée
depuis le snapshot C37, avec les nouveaux RTL vidéo. Les sources USB, horloges,
DDR et IP ne sont pas régénérées. Chaque compilation conserve son manifeste
SHA256. Ne charger aucun résultat avant vérification du timing setup/hold
et de ses ressources physiques.

Tests : `test_gpu_geometry.py`, `test_gpu_geometry.py --world`,
`test_gpu_geometry_api.py`, `rtl/gpu_geom_div_tb.sv`, régression
`test_gpu_v1.py`, références `render_world3d.py` et
`render_astrilla.py --hardware-geometry --fast`.
