# Qualification de l'accélération 3D G3D1 — 10 octobre 2026

## Statut provisoire

Les tests logiciels et RTL décrits ci-dessous passent. La compilation FPGA
`gpu_geometry_g2` a échoué au routage avec 72 connexions non routées ; elle
n'a pas de bitstream qualifié. G4 a été refusé par le placeur : le mode
lecture avant écriture de la RAM double port n'est pas supporté sur ce FPGA.
G5 utilise le mode écriture traversante ; G6 ajoute l'accélération exacte des
coordonnées de texture sur 12 bits. G7 raccourcit le chemin des pixels opaques
et recharge les lignes du cache en une écriture. G8 ajoute les codes de
frustum par sommet, le cache 8 Kio, l'avance des pixels pendant leur écriture
et la correction des intersections partagées. G3, G5, G6 et G8 sont routés
mais refusés au timing. G9 sépare la sélection
des sommets du calcul de leurs attributs. G10 ajoute le cache 32 Kio ; la
source courante correspond à G21 (voir corrections ci-dessous). G13, G14 et
G15 sont routés mais refusés au timing. G16/G16r/G16p4/G17/G18/G18a1 ont
échoué au routage avec respectivement 504/152/146/1/91/15 648 connexions
non routées. G19, G20 et G21 sont en compilation physique ; aucun prototype
antérieur n'est qualifié pour la carte.
Aucun résultat sur carte ni timing
positif du nouveau bloc n'est encore revendiqué. Le FPGA C37 et ASTRILLA R18
restent la référence de repli.

## Changement testé

Nouveau frontal de géométrie devant le rasteriseur GPU V1 : maillages indexés
lus en DDR, transformations 3×4, cache des sommets, découpage six plans,
projection perspective, éclairage plat, élimination arrière, calcul des
gradients et émission des commandes raster internes. L'ABI précédente et
le résultat du rasteriseur sont conservés. Le diviseur des coordonnées de
texture gagne un chemin exact sur 12 bits, le cache recharge un burst entier
et les pixels opaques évitent les étapes de mélange inutiles. Le détail est dans
`ARCHI/GPU_GEOMETRY.md`.

Deux applications utilisent le même pilote : ASTRILLA avec ses maillages
existants et un monde à caméra modifiable en direct, sans cache d'images.

## Preuves locales

| Vérification | Résultat / preuve |
|---|---|
| Diviseur signé | 2 007 cas, division par zéro, dépassement signé, annulation par reset : `gpu_geometry_20261010/div_test.log` |
| API C | UBSan et contrôle de conversions flottantes, rejet atomique de NaN/infini/plages invalides : `test_gpu_geometry_api.py` |
| Régression V1 | 751 commandes, 22 rejets attendus, 31 250 pixels validés : `gpu_geometry_20261010/legacy_v1/result.json` |
| RTL géométrie, délais DDR prolongés | 57 commandes, 6 rejets attendus, 99 sommets, 36 triangles, 69 intersections ; `gpu_geometry_20261010/rtl_bounds/result.json` |
| RTL erreurs et triangles minces | 62 commandes, 7 rejets attendus, 111 sommets, 38 triangles, 69 intersections, 2 approximations explicitement comptées ; `gpu_geometry_20261010/rtl_restore_final/result.json` |
| Monde 3D, sources finales | 927 commandes CPU, 5 385 commandes raster internes, 2 676 sommets, 834 triangles ; `gpu_geometry_20261010/rtl_world_final/result.json` |
| Diviseurs radix 4 | Les mêmes 2 007 cas signés et annulation par reset : `gpu_geometry_20261010/div_r2/simulation.log` |
| RTL courant avec RAM | Les mêmes résultats exacts et sept rejets : `gpu_geometry_20261010/rtl_ram/result.json` |
| Monde RTL courant avec RAM | 927 commandes CPU, 5 385 commandes raster, 2 676 sommets, 834 triangles, 482 intersections, zéro approximation : `gpu_geometry_20261010/rtl_world_ram/result.json` |
| RAM en mode supporté par GW5AST | Mêmes commandes et pixels exacts : `gpu_geometry_20261010/rtl_world_write_through/result.json` |
| Division perspective 12 bits | 2 468 couples signés, frontières 255/256 et 4095/4096, reset, Q nul/négatif ; 109 cas du nouveau chemin : `gpu_geometry_20261010/perspective_uv12/simulation.log` |
| Anciennes primitives avec UV12 | 751 commandes et 31 250 pixels exacts : `gpu_geometry_20261010/legacy_uv12_fixed/result.json` |
| Monde avec UV12 | Mêmes 927 commandes et 3 145 728 octets exacts : `gpu_geometry_20261010/rtl_world_uv12_fixed/result.json` |
| Pixels opaques et cache à recharge parallèle | 751 anciennes commandes et 927 commandes du monde restent exactes : `gpu_geometry_20261010/legacy_burstcache/result.json`, `gpu_geometry_20261010/rtl_world_burstcache/result.json` |
| Erreurs avec délais DDR longs et cache parallèle | Sept rejets et deux approximations attendus ; reprise et gardes exactes : `gpu_geometry_20261010/rtl_burstcache_bounds/result.json` |
| Cache de sommets complet | Indice 255 réellement utilisé, 367 sommets, 63 commandes, sept rejets : `gpu_geometry_20261010/rtl_cache256/result.json` |
| G8, erreurs et arête partagée | 64 commandes, 324 commandes raster, 371 sommets, 49 triangles, 85 intersections, sept rejets et deux approximations attendus ; `gpu_geometry_20261010/rtl_seam_after/result.json` |
| G8, monde avec délais DDR | 927 commandes, 5 385 commandes raster, 2 676 sommets, 834 triangles, 482 intersections, zéro approximation ; `gpu_geometry_20261010/rtl_world_seam/result.json` |
| G8, rasteriseur V1 | 751 commandes, 22 rejets attendus, 31 250 pixels exacts ; `gpu_geometry_20261010/legacy_cache8k/result.json` |
| Ancien rasteriseur 14–21 | 785 commandes, 18 rejets attendus et toutes les gardes exactes ; `gpu_geometry_20261010/legacy_raster_rerun.log` |
| Anciennes primitives 2D/affines | 604 commandes, pixels et gardes exacts ; `gpu_geometry_20261010/legacy_affine_rerun.log` |
| Caméra libre C | 6 600 états automatiques et 45 états invalides sous sanitizers ; `gpu_geometry_20261010/world_reference/sweep.json` |
| Images ASTRILLA matériel | 158 poses, jusqu'à 311 sommets et 183 triangles par pose, zéro approximation d'attribut ; `gpu_geometry_20261010/astrilla_full_reference/expected.json` |
| Chargeur existant | 7 tests d'identification et pause : `test_load_identity.py` |

La simulation matérielle inclut la file AHB, les deux horloges, le blitter,
la géométrie, le rasteriseur et l'arbitre DDR, avec demandes concurrentes CPU
et scanout. Elle compare chaque commande raster interne au modèle entier
Python indépendant puis les 3 145 728 octets de mémoire, gardes comprises.
Comparer aussi les commandes internes empêche un dessin ultérieur de cacher
une erreur de calcul dans une image antérieure.

Les six rejets RTL couvrent un débordement de transformation, une ligne de
matrice invalide, une adresse non alignée, plus de 256 sommets, une caméra
invalide et un DRAW sans caméra valide. Un DRAW valide après rétablissement
de CAMERA doit fonctionner. Les accès hors surface sont fatals dans le
modèle DDR du banc de simulation.

Les images de référence sont des rendus du modèle, pas des captures LCD.
Elles ne constituent pas à elles seules une preuve de fonctionnement du FPGA
routé. Le monde utilise une orientation des vaisseaux cohérente avec leurs
tangentes ; le test RTL final inclut ces orientations.

## Défauts trouvés pendant le développement et corrigés

1. Le calcul de projection mélangeait signe et non-signe, ramenant certaines
   coordonnées négatives sur le mauvais bord : calculs intermédiaires signés
   explicites, puis comparaison exacte des images.
2. L'adresse du port DDR devait être exprimée en mots de 32 bits, pas en mots
   de 64 bits : conversion `adresse_octet >> 2`, vérifiée par l'arbitre réel.
3. Une intersection exactement sur un plan pouvait dupliquer un sommet :
   création d'intersection uniquement pour deux distances strictement de
   signes opposés.
4. Les UV sans perspective nécessitaient un facteur Q16.16 : correction de
   l'émission des plans dans le RTL et sa spécification indépendante.
5. Une face invalide après une face valide interrompait le DRAW sans restaurer
   le matériau du demandeur. `rtl_restore_before` reproduit l'absence de la
   commande de restauration. Le chemin FAIL d'un DRAW accepté passe désormais
   par RESTORE ; `rtl_restore_final` vérifie le flux entier et les gardes.
   Le premier essai `rtl_restore_after` utilisait encore l'ancien oracle pour
   l'autre erreur, un débordement de transformation avant la première face ;
   l'oracle final exige la restauration pour ces deux chemins.
6. Deux triangles parcourant une arête partagée en sens opposés obtenaient
   des intersections différentes après arrondi Q16.16. Le cas
   A=(10 ; 0 ; 3,25), B=(-12,5 ; 0 ; -3,5), near=0,25 donnait respectivement
   (2,0,16384) et (-20,0,16378) en coordonnées Q16.16, ce qui projette X à
   80 ou 79 pixels. `rtl_seam_before` échoue explicitement sur ce second
   point. L'interpolation est désormais toujours orientée intérieur vers
   extérieur : `rtl_seam_after` exige deux fois (2,0,16384), indépendamment
   de l'oracle de pixels. Les nouvelles références complètes sont dans
   `astrilla_reference_seam` (158 poses, seule la pose 7169 change de CRC)
   et `world_reference_seam` (14 vues). Aucun compteur d'approximation n'y
   apparaît dans les scènes normales.

Pour la pose de combat 7400, les commandes CPU de scène passent de 1 265 dans
la référence R18 à 400 avec G3D1, pour 267 sommets et 157 triangles produits
par le matériel. C'est une mesure du flux de commandes, pas encore un gain
de FPS sur carte.

## Construction isolée

La compilation copie le snapshot C37 et remplace uniquement le frontal vidéo,
le dispatch de commandes et les diagnostics associés. Les horloges, le PHY
USB, le contrôleur DDR, le câblage et le firmware d'initialisation C37 sont
conservés. Aucun processus Gowin d'une autre session n'est arrêté ni relancé.

La synthèse g2 annonce 84 607 éléments logiques et 56 900 registres. Ce sont
des valeurs de synthèse ; le rapport physique final prévaut. Ne pas comparer
des comptes BSRAM de synthèse aux comptes physiques du routage.

Le rapport physique g2, **non routé**, indique 85 250 éléments logiques,
56 900 registres, 60 220/69 120 CLS (88 % affichés), 261/340 BSRAM et
191/298 DSP. Le routeur a terminé sans pouvoir connecter 72 nets ; ce résultat
ne peut pas être chargé et ne fournit pas de timing final valide.

G3 conserve la même arithmétique mais sépare les différences, produits,
sommes et corrections de signe par des registres ; le diviseur utilise trois
soustractions parallèles par paire de bits. Les tests `rtl_pipeline2` et
`rtl_world_pipeline` restent exacts. G4 remplace les cinq banques de registres
de découpage et leurs multiplexeurs par une RAM 32×160 bits à deux ports
synchrones. L'inférence de `polygon` est confirmée dans son journal Gowin.
Les nouveaux tests `rtl_ram` et `rtl_world_ram` restent exacts.

Le rapport de synthèse G5 contient 77 519 éléments logiques, dont 58 871 LUT,
et 53 104 registres. La RAM de découpage économise 7 212 LUT et 5 120 registres
par rapport à G3 ; les nombres physiques après placement restent à vérifier.
Le mode écriture traversante ne change pas le résultat : le port écrit n'est
pas utilisé par le calcul pendant ces cycles, et les lectures suivantes
conservent leur étape synchrone.

G6 réduit de 28 à 9 cycles la division perspective pour les quotients absolus
de 256 à 4095. Le chemin existant pour les quotients inférieurs à 256 est
conservé. Les quotients plus grands conservent les 50 bits de calcul. Le test
compare aussi les restes non nuls, les signes opposés et les tailles U/V
différentes : il ne s'agit ni d'une approximation ni d'une réduction des UV.

G7 ajoute un chemin opaque pour les pixels RGB565/solides, alpha 256, sans
brouillard ni addition. La modulation garde le même arrondi ; les matériaux
ARGB4444 et les mélanges gardent le chemin général. Une RAM de cache plus
large conserve ses 2 Kio utiles mais recharge les seize texels simultanément.
Le comptage de hits/misses, les pixels et la profondeur restent identiques.

Profilage RTL du monde, horloge mémoire 75 MHz, délais DDR minimum trois
cycles et trafic concurrent CPU/scanout. Ces chiffres sont des cycles de
simulation, **pas des FPS mesurés sur la carte** :

| Vue | UV12 seul | + chemin opaque | + recharge parallèle du cache |
|---|---:|---:|---:|
| Caméra automatique, phase 0 | 1 761 493 | 1 583 431 | 1 461 012 |
| Caméra très proche du vaisseau | 3 046 628 | 2 655 903 | 2 594 877 |
| Caméra arbitraire décalée | 1 815 638 | 1 636 497 | 1 511 254 |

Preuves : `rtl_world_profile/simulation.log`, `rtl_world_opaque/simulation.log`
et `rtl_world_burstcache/simulation.log` dans `gpu_geometry_20261010`.
Le gain de 17,1 % sur la première vue ne repose sur aucune réduction de scène.

G8 conserve un code de frustum pour chacun des 256 sommets. L'acceptation
directe des triangles complètement intérieurs réduit la géométrie de la
première vue de 296 039 à 219 953 cycles (`rtl_world_boundsfast`). Le cache
de texture passe ensuite de 64 à 256 lignes (8 Kio) ; les registres du pixel
suivant avancent pendant l'écriture du pixel courant. Avant la correction
d'arête, `rtl_world_cache8k` mesure 1 286 691 / 2 422 284 / 1 326 828 cycles
pour les trois mêmes vues, et 12 490 défauts de cache au lieu de 20 508.
Le test final `rtl_world_seam` utilise des délais DDR plus longs (minimum
11 cycles), donc son temps ne doit pas être comparé directement à ce tableau.

Les anciens scripts de régression et le rendu RTL V1 incluent désormais
les deux nouveaux modules. Les premiers lancements 2D/raster ont révélé un
problème de chemin relatif du banc, avant exécution du simulateur ; les
scripts résolvent maintenant leur dossier de sortie et les relances passent.

### Premier rapport physique : G3 refusé

G3 termine le routage mais comporte 7 302 endpoints en défaut setup et aucun
défaut hold. Le pire slack est −9,643 ns : sélection dans les anciennes
banques de registres du polygone puis multiplication. Cette sélection est
déjà remplacée par la RAM synchrone à partir de G5. Les 200 chemins publiés
font également apparaître `fan` vers `value[2]`, avec jusqu'à −5,560 ns :
lecture parmi douze sommets puis produit UV×Q dans le même cycle. G9 capture
les attributs des trois sommets pendant TRI_INIT, avant ces produits.
`rtl_attributes` et `rtl_world_attributes` gardent les résultats et les cycles
de G8 exactement identiques. G3 n'est jamais autorisé au chargement.

Ses ressources physiques sont 85 379 éléments logiques, 58 224 registres,
60 564/69 120 CLS, 261/340 BSRAM. Ce ne sont pas les ressources de G9.

G8i/G8p réutilisent exactement la netlist synthétisée G8, avec vérification de
tous les SHA de sources et de la netlist. La référence de placement C37 n'a
que 68,97 % de correspondance, sous le seuil Gowin de 80 % : G8i revient au
placement normal. G8p utilise le placement du prototype G7. Aucun de ces
essais ne modifie une contrainte d'horloge ou une exception de timing.

### Couverture du parcours complet et cache 32 Kio

Le premier passage des 6 600 poses a révélé quatre dépassements de gradient
int32 de profondeur, aux phases 4099, 4101, 4102 et 4104. Ils concernent la
même face du vaisseau vue par la tranche, avec une aire projetée de 0,5 pixel.
L'analyse de la couverture selon la règle du rasteriseur donne **zéro pixel**
pour chacune de ces faces. Aucun pixel visible n'est donc approximé dans ce
parcours. Le résultat initial FAIL est conservé (`world_full_geometry`).
Le contrôle détaillé `world_full_geometry_coverage` vérifie ces quatre cas
exacts et leur couverture nulle ; tout cas supplémentaire provoque un échec.
Les 18 références image incluent maintenant ces quatre poses. Le banc RTL
`rtl_world_sliver` vérifie toute la mémoire couleur/profondeur et le compteur.

Cette vue charge fortement le cache : 24 240 défauts avec 8 Kio. Le cache de
32 Kio descend à 2 206 défauts, avec les mêmes pixels, profondeur et commandes.
À délais DDR minimum 11 cycles, le temps simulé passe de 1 791 623 à 1 322 469
cycles, soit −26,2 %. Preuve : `rtl_world_cache32k/simulation.log`. La régression
V1 de 751 commandes passe aussi (`legacy_cache32k`). Le coût physique et le
timing du cache élargi restent à qualifier après routage.

Le parcours entier ASTRILLA (`astrilla_full_geometry`) vérifie les 16 500
positions : au maximum 443 sommets, 257 triangles émis et 180 intersections
par image ; aucune approximation d’attribut. Ce test contrôle les commandes
C et la géométrie entière, sans calculer tous les pixels et sans mesurer
les performances FPGA. Les 158 images de référence restent complémentaires.

### Rejet des champs réservés des maillages

La revue a relevé deux vérifications manquantes : les cinq mots réservés du
sommet et les 16 bits hauts du mot 5 de face. Le test `rtl_reserved_before`
reproduit leur acceptation incorrecte ; `rtl_reserved_after` passe après
ajout des rejets. Il contrôle 66 commandes, 9 rejets attendus, 380 sommets,
49 triangles et 3 145 728 octets, ainsi que la restauration du matériau après
abandon. Le contrat précise également que le maillage reste immuable jusqu'à
la fence, sans chevauchement avec les cibles GPU ; le frontal ne contrôle pas
ce dernier chevauchement, qui reste à la charge de l'appelant.

La synthèse G10 (avant ces deux contrôles) utilise 81 984 éléments logiques
(62 496 LUT + 19 488 ALU), 54 212 registres et 208 BSRAM logiques. Ce rapport
de synthèse ne remplace pas les ressources physiques après placement.

### Sélection des coefficients et validation des commandes

Le regroupement des chemins G3 par source/destination a également isolé
`row` vers les multiplicateurs (−6,770 ns) et la file de commandes vers la
validation des adresses (−6,381 ns). G12 enregistre les quatre coefficients
de la ligne suivante pendant le stockage de la ligne courante, sans cycle
supplémentaire. Il capture la commande et les deux fins de plages DDR avant
leur validation ; cela ajoute un cycle de 75 MHz par commande.

Les tests `rtl_command_coeff`, `rtl_world_command_coeff` et
`legacy_command_coeff` passent : mêmes commandes shader et pixels pour les
maillages valides, rejets explicites des champs réservés invalides. Le nouvel
outil `tools/check_geometry_timing.py` regroupe les chemins physiques et ne
peut écrire `bitstream.sha256` que lorsque tous les groupes setup/hold sont
sans défaut et le build complet. Son analyse retrouve G3 en FAIL et C37 en PASS.

### Résultats physiques intermédiaires et fermeture du timing

| Build | Résultat physique | Pire slack | Endpoints setup / hold |
|---|---|---:|---:|
| G3 | Routé, refusé | −9,643 ns | 7 302 / 0 |
| G5 | Routé, refusé | −8,142 ns | 2 091 / 0 |
| G6 | Routé, refusé | −6,733 ns | 1 255 / 0 |
| G8 / G8i | Routé, refusé | −7,099 ns | 1 565 / 0 |
| G13 | Routé, refusé | −5,449 ns | 466 / 0 |
| G14 | Routé, refusé | −4,879 ns | 196 / 0 |

G7, G8p, G9, G10 et G11 ont des connexions non routées. La réutilisation
du placement d'un autre prototype n'a pas aidé ; G13–G15 emploient un
placement normal. G12 échoue avant placement sur une ancienne contrainte
littérale `vid_hready_s2`, devenue obsolète avec la nouvelle netlist. Les
deux placements `vid_hready_s0/s2` sont retirés ; aucune fréquence, broche
ou exception de timing n'est modifiée.

G8 occupe physiquement 80 390 éléments logiques, 53 696 registres,
58 004/69 120 CLS, 286/340 BSRAM et 191/298 DSP. Ces ressources concernent
le cache 8 Kio et ne préjugent pas de celles de G15.

G13 sépare la lecture RAM des produits de projection, puis enregistre les
coordonnées normalisées après contrôle de plage avant le produit par la
focale. Il réduit ce dernier produit de 64×32 à 32×32 bits sans troncature
de valeur valide, au prix d'un cycle par sommet projeté. Les trois produits
d'éclairage signés 16×16 sont séparés ; leur somme reste sur 34 bits. La
fraction d'intersection garde exactement 0..65 536 dans un opérande signé
de 18 bits. Les tests `rtl_projection_pipe` et `rtl_world_projection_pipe`
comparent les commandes internes et toute la mémoire aux mêmes références.

G13 introduit aussi `video_bus_stage.v` dans le domaine bus 80 MHz. Il
capture l'adresse, puis les données de la phase d'écriture, émet une seule
transaction vers les périphériques et enregistre la réponse. Cela coupe
le long aller-retour combinatoire entre la validation vidéo, HREADY et les
périphériques USB. Le protocole USB et ses horloges ne changent pas. Le coût
est de quelques cycles par accès registre CPU.

G14 enregistre l'état actif d'écriture du DMA du blitter au lieu de laisser
le reset et le décodage d'état traverser le chemin de sélection de sa RAM.
`legacy_dma_ready` vérifie 604 commandes, les pixels, les gardes et
**2 081 518 cycles d'interface DMA identiques à C37**, hors reset commun.

G15 fait passer l'ancien rasteriseur (opcodes 14–21) par l'étage DDR
enregistré déjà utilisé par V1 et la géométrie. Son interface n'est plus
directement dépendante de l'arbitrage scanout. `legacy_registered_ddr`
vérifie 785 commandes et 18 rejets attendus avec des réponses mémoire dès
un cycle. `rtl_mixed_registered_ddr` alterne géométrie, ancien rasteriseur
texturé, puis géométrie : 72 commandes, 9 rejets attendus, 357 commandes
shader et 3 145 728 octets exacts, gardes comprises.

Autres preuves du bus enregistré :

- `video_bus_stage_resets` : 2 160 transactions pipelinées, quatre fenêtres
  périphériques, 0 à 16 cycles d'attente, reset dans cinq phases, sans rejeu.
- `msc_bus_stage` : trois couples de périodes/phases USB/bus indépendantes,
  arrêt d'horloge, purge et reset pendant transmission ; à chaque passage,
  228 paquets IN, 28 OUT, 24 377 mots émis et 2 151 reçus. Ce test numérique
  ne qualifie pas à lui seul le PHY USB physique.
- `rtl_geometry_bus` et `rtl_world_bus` : calcul 3D et mémoire exacte avec
  les transactions CPU traversant le nouveau bus.

### Descripteurs refusés et décodage de l'automate

`rtl_descriptors_before` reproduit un défaut du frontal : son contrôle
partiel du matériau permettait de reprendre une teinte refusée par V1.
L'application de l'éclairage pouvait alors la ramener dans la plage valide.
G16 attend le verdict complet du moteur V1 avant de rendre le matériau
utilisable par DRAW. Il invalide aussi les dimensions mémorisées d'une cible
refusée, empêchant CAMERA d'accepter cette cible.

`rtl_descriptors_after` vérifie huit matériaux invalides (teinte, bits
réservés, couleur, brouillard, en-tête, combinaison de flags et alpha),
deux cibles invalides, les DRAW/CAMERA qui suivent et la reprise valide.
Résultat : 98 commandes CPU, 21 rejets géométriques et dix rejets V1
attendus, 400 commandes shader, 398 sommets et 59 triangles ; toute la
mémoire reste exacte. L'alternance avec l'ancien rasteriseur est incluse.

Le rapport G8 montre également un bit d'état de géométrie distribué vers
654 charges, avec six niveaux de logique et un slack de −3,279 ns vers
`shader_start`. G16 remplace le codage binaire par un bit par état, comme
le moteur V1 existant. `rtl_onehot` retrouve les résultats et cycles de
`rtl_descriptors_after` exactement ; `rtl_world_onehot` vérifie les trois
vues à délais DDR minimum 11 cycles : 1 337 143 / 2 559 002 / 1 377 688
cycles, 927 commandes et toute la mémoire exacte. Le gain de timing reste
à établir par placement/routage, sans déduire une qualification physique
de ces simulations.

`legacy_onehot` conserve les 751 commandes V1, 22 rejets et 31 250 pixels
exacts, avec des réponses DDR dès un cycle. `rtl_reset_phases` interrompt
le frontal pendant sept phases : lecture d'un sommet, transformation,
division de découpage, projection, gradient, rasterisation et restauration
du matériau. Le DDR et son arbitre continuent de fonctionner pendant le
reset CPU/GPU ; leurs files de réponses ne sont pas effacées par le banc.
Après drainage, aucune ancienne commande ne reprend et un DRAW sans
reconfiguration est refusé. Le banc reconfigure ensuite le GPU et rejoue
les 98 commandes, avec les 3 145 728 octets finaux exacts. Les délais mémoire
de ce test restent ceux du modèle (minimum 11 cycles, contention CPU/LCD),
pas une preuve contre un contrôleur DDR qui cesserait de répondre.

G16r et G16p4 réutilisent la netlist G16, sans nouvelle synthèse, après
vérification des SHA de toutes les sources et de la netlist. La duplication
physique des ressources à forte charge est autorisée ; G16p4 utilise
l'algorithme de placement 4 au lieu de 3. Ces options sont celles décrites
par SUG1220-1.0E, sections `place_option` et `replicate_resources`. Les
contraintes de timing restent identiques. La netlist G16 utilise à la
synthèse 84 161 éléments logiques (64 931 LUT + 19 230 ALU), 53 959
registres et 208 BSRAM logiques ; attendre les ressources physiques pour
calculer l'occupation réelle.

Un banc complémentaire `test_gpu_geometry_netlist.py` extrait le frontal
et ses deux diviseurs de la netlist G16. Les primitives officielles Gowin
restent inchangées et sont simulées avec Icarus. Le moteur de pixels est
remplacé par une réponse de fin de commande retardée ; chaque commande
raster émise est comparée à l'oracle du monde. Ce banc ne valide donc ni
les pixels après synthèse, ni le timing, ni l'ensemble de la puce.

Les premiers essais de ce banc ont rencontré des limites du simulateur
(Verilator ne supporte pas `deassign` du modèle DFFRE), des dépendances
de primitives manquantes dans l'extraction, puis deux bits d'opcode
supprimés par synthèse car constants pour toutes les commandes shader.
Le banc courant conserve également le cône de deux LUT de contrôle que
Gowin a déplacé dans la hiérarchie du moteur de pixels. Les bits supprimés
sont reconstruits à zéro, après vérification que toutes les références les
ont à zéro ; les autres bits sont comparés exactement, y compris les X/Z.
`netlist_g16_first_mesh` passe sur le premier maillage : 11 commandes CPU,
36 commandes shader, quatre sommets, cinq triangles, 14 intersections et
six lectures DDR. Les commandes correspondent bit à bit au modèle entier.
Le contrôle complet `netlist_g16_boundary` passe ensuite sur les trois vues :
927 commandes CPU, 5 385 commandes shader comparées exactement et
5 130 lectures DDR. Les compteurs finaux sont également conformes :
2 676 sommets, 834 triangles, 1 715 éliminations, 482 intersections et zéro
approximation. Le temps simulé est de 9 055 441 032 ps. Le moteur de pixels
reste remplacé par la réponse retardée décrite ci-dessus : ce PASS ne vaut
pas validation des pixels après synthèse ni du timing physique.

L'essai complet doublé avec progression `netlist_g16_progress` atteint sa
limite murale de 1 800 secondes : aucun écart n'est signalé avant cet arrêt,
mais ce n'est pas un PASS. L'essai `netlist_g16_boundary`, lancé plus tôt,
termine normalement comme indiqué ci-dessus. Le banc conserve ses watchdogs en cycles ; la limite murale des
lancements futurs est portée à 7 200 secondes, car les modèles officiels
ne simulent ici que quelques centaines de cycles par seconde.

### Chemins arithmétiques et placement G17

G13 utilise physiquement 82 552/138 240 éléments logiques,
55 032/139 140 registres, 58 408/69 120 CLS, 281/340 BSRAM et 178/298 DSP.
G14 utilise respectivement 82 541, 55 033, 58 598, 281 et 178 ressources.
Ce sont des prototypes refusés ; ces chiffres ne constituent pas une
qualification ni l'occupation définitive de la version à charger.

Le pire chemin G14 part de `u_rgb_reader/fetch_valid` vers l'ancien
rasteriseur : −4,879 ns. L'étage DDR ajouté dans G15 vise ce chemin.
Le rapport expose aussi la RAM des polygones vers le diviseur de projection
(−1,660 ns), et les produits de gradient partagés. G17 capture d'abord Z,
puis applique la borne proche et lance le diviseur un cycle plus tard.
Les quatre produits de gradient possèdent désormais leurs propres
registres, au lieu de traverser le multiplexeur des produits partagés.
Les différences écran sont signées sur 12 bits en X et 11 bits en Y,
ce qui couvre exactement le viewport maximal 1024×512. Les différences
d'attributs restent sur 41 bits, les produits sur 53 bits et leurs sommes
sur 64 bits. Aucun cycle de gradient n'est ajouté.

L'ancre physique `u_accel/u_raster/texture_row_24_s4` à R76C118[3][A]
est libérée : le rapport G13 montre un détour à −3,913 ns depuis
`load_y`, et G14 retrouve −2,983 ns. Ce changement complète le retrait
des deux anciennes ancres HREADY ; les broches, fréquences et exceptions
de timing restent identiques. G17 utilise placement 4 et duplication
physique des ressources à forte charge.

- `rtl_gradient_pipe` : 98 commandes CPU, 400 commandes shader,
  sept resets pendant un DRAW, puis reprise et mémoire exacte.
- `rtl_viewport_extrema` : 105 commandes CPU et 417 commandes shader,
  viewport 1024×512, plan proche minimal et UV −32768..32767. Le scissor
  vide du cas extrême évite d'écraser les images précédentes, mais tous les
  coefficients transmis au rasteriseur sont comparés à l'oracle.
- `rtl_world_gradient_pipe` : 927 commandes CPU, 5 385 commandes shader,
  2 676 sommets, 834 triangles et 482 intersections. Les 3 145 728 octets
  comparés restent exacts, avec délais DDR minimum 11 cycles.

`netlist_g17_first_mesh` retrouve après synthèse les 11 commandes CPU,
36 commandes shader et six lectures de maillage du contrôle G16.
Les mêmes primitives officielles Gowin et la même limitation de périmètre
(moteur de pixels remplacé par une réponse de fin) s'appliquent.

### Commande des accès natifs DDR G18

G14 expose un chemin de −3,368 ns entre l'état d'écriture couleur V1 et
l'activation du registre `native_valid` : cinq niveaux logiques, deux réseaux
à 298 et 277 charges, avec 13,991 ns de trajet. G18 exprime directement
l'émission, puis le maintien de VALID jusqu'à l'acceptation. Ce registre
n'hérite plus du grand multiplexeur d'activation de l'automate. Aucune
latence ni transaction n'est ajoutée.

`native_valid_equivalence` compare le GPU courant au snapshot G17 :
751 commandes CPU, 1 119 552 cycles AHB et 1 049 683 cycles DDR,
86 800 transactions identiques au cycle près ; les pages et gardes sont
exactes, avec 22 rejets attendus et 31 250 pixels. Le premier lancement
du banc demandait par erreur une image mémoire initiale externe absente ;
le binaire déjà compilé a été exécuté avec le motif déterministe du banc,
comme dans `test_gpu_v1.py` (`rgbinit=0`).

`rtl_world_native_valid` vérifie aussi les trois vues et 5 385 commandes
shader avec des réponses DDR dès un cycle. `rtl_native_valid_resets`
reprend les sept interruptions, les descripteurs invalides et l'alternance
des moteurs : 98 commandes CPU, 400 commandes shader et mémoire exacte.

`g18_test_sources.json` conserve les SHA des RTL correspondants et vérifie
leur identité avec le snapshot G18. `netlist_g18_first_mesh` passe aussi
après synthèse avec les mêmes 36 commandes shader. G18a1 reprend la netlist
G18 vérifiée avec le même placement 4 et l'algorithme de routage 1 au lieu
de 2 (`route_option`, SUG1220-1.0E p. 30) ; aucune différence fonctionnelle
ni de contrainte temporelle n'est introduite par cette variante.

### Relecture des largeurs arithmétiques

`new_block_warnings.json` conserve les 110 avertissements des trois nouveaux
blocs dans le build Verilator G18 : 68 extensions et 42 réductions de largeur,
sans avertissement de latch, de pilotes multiples ou de boucle combinatoire
pour ces blocs. Les réductions principales reposent sur les bornes suivantes :

- Une intersection est une interpolation de fraction 0..65 536 entre deux
  entiers signés 32 bits ; son résultat reste entre ces deux extrémités.
- La somme de trois produits de normales/lumière signés 16×16 tient sur
  34 bits ; après décalage de 15 bits, elle tient sur 18 bits signés.
- Deux gains 0..256 donnent, après arrondi et division par 256, un résultat
  0..256 : neuf bits suffisent.
- Après clamp au viewport, les différences écran restent dans ±1024 et
  ±512. L'aire et les différences d'attributs ont les marges décrites dans
  l'architecture ; les UV extrêmes et le plan proche minimal sont testés.
- Les indices de projection restent inférieurs à 12, ceux d'attribut de
  triangle à 3 et ceux de pente caméra à 4 avant chaque accès de tableau.
- Les adresses de maillage sont validées sur 33 bits avant conversion en
  mots DDR ; les deux plages doivent tenir dans les 512 Mio.

Les expressions booléennes sur plusieurs bits sont des tests de nullité.
Cette relecture ne supprime pas globalement les avertissements et ne remplace
pas les comparaisons de calcul, les gardes mémoire ou l'analyse physique.

La qualification physique conserve aussi les SHA du Tcl exécuté, des
contraintes résolues, de la netlist, des métadonnées de compilation et de
la copie de police lue par `readmemh`. Cette dernière doit être identique
au fichier canonique du snapshot. Une netlist réutilisée doit conserver le
SHA de son parent. L'analyse retrouve toujours C37 en PASS (+0,071 ns)
et G14 en FAIL (−4,879 ns) ; aucune qualification de prototype n'est créée
sur la seule base de ces contrôles de provenance.

### Point de suivi au 11 octobre, 01 h 03 (Europe/Rome)

G15, G16, G16r, G16p4, G17, G18 et G18a1 sont encore en routage ;
aucun nouveau rapport temporel ni bitstream qualifié n'est disponible.
Le contrôle complet de la netlist G18 a été lancé dans
`netlist_g18_full`, avec les trois vues de `rtl_world_native_valid`.
Il a comparé les 420 premières commandes shader sans différence, mais
ce résultat partiel ne constitue pas un PASS. Comme pour G16, ce banc
vérifie la géométrie synthétisée avec un moteur de pixels simulé par une
réponse de fin, sans valider le timing physique.

Aucun rechargement FPGA ni changement de firmware sur la Pro Dock n'a
été effectué pendant ce suivi ; la version sur carte reste C37 / ASTRILLA R18.

### Corrections du 11 octobre : G19 / G20

La vérification complète après synthèse de G18 est passée :
`gpu_geometry_20261010/netlist_g18_full/result.json`, 927 commandes CPU,
5 385 commandes shader et compteurs exacts. Cela ne qualifie pas son routage,
qui a échoué. Les résultats physiques précédents sont archivés dans
`gpu_geometry_20261011/previous_physical_results.json`.

G19 remplace les tableaux de sommets projetés, auparavant en registres avec
sélection variable, par une RAM synchrone 16×104 bits. Les trois sommets d'un
triangle sont lus successivement avant les mêmes calculs ; trois cycles sont
ajoutés par triangle du polygone découpé. Les valeurs, les formats et les
fréquences sont inchangés. L'objectif est de réduire les multiplexeurs et la
pression de routage ; G17 utilisait 60 552/69 120 CLS (88 %).

G20 ajoute une file de deux demandes de lecture entre l'affichage et
l'arbitre DDR. L'acceptation côté affichage signifie désormais entrée dans
cette file ; l'émission DDR conserve la priorité et l'ordre des lectures.
L'acceptation ne dépend plus du READY de la DDR. La file peut transmettre
une demande par cycle tant qu'elle n'est pas pleine et que la DDR accepte.
Les seize tags de lectures DDR restent bornés indépendamment de ces deux
emplacements de demandes. Les producteurs de tuiles et de sprites conservent
leurs propres limites de demandes en vol ; le lecteur RGB utilise les
réponses dans l'ordre.

Preuves locales sous `gpu_geometry_20261011/` :

- `rtl_projected_ram` : sept resets, descripteurs invalides, viewport extrême,
  anciens/nouveaux moteurs ; 105 commandes CPU, 417 commandes shader et
  3 145 728 octets exacts.
- `rtl_world_scan_stage` : trois vues, 927 commandes CPU, 5 385 commandes
  shader, mêmes pixels et compteurs, réponses DDR à partir d'un cycle.
- `rtl_scan_stage_resets` : mêmes 105 commandes et sept resets avec le nouvel
  arbitre et des délais DDR d'au moins onze cycles.
- `ddr_scan_stage_long` : scoreboard des commandes acceptées côté clients,
  1 108 lectures, 162 écritures, trois clients, file de tags pleine, deux
  demandes d'affichage retenues, attentes indépendantes et annulation des
  deux demandes lors du reset commun de l'arbitre/contrôleur. Le premier
  essai de 250 cycles n'atteignait pas tous les seuils de couverture des
  clients ; l'essai de 2 000 cycles conserve ces seuils et passe.
- `scanout_stage_rgb0` et `scanout_stage_rgb1` : tous les pixels 800×480,
  palette/RGB565 et changement de format au retour vertical, sommes exactes,
  blocage de la DDR pendant plusieurs trames puis reprise ; respectivement
  2 953 184 et 2 941 968 lectures CPU concurrentes.

La file ajoutée est synchrone au domaine DDR existant ; elle n'ajoute aucun
passage de domaine d'horloge. Aucune écriture de SD ni aucun chargement de
prototype sur la carte n'a été effectué pour ces vérifications.

La synthèse confirme le remplacement de la table projetée par une RAM :
G18 utilisait 64 817 LUT et 54 200 registres ; G19 en utilise 63 370 et
52 955. Le compteur logique de BSRAM passe de 208 à 211, à ne pas confondre
avec le décompte physique après placement. G20 ajoute 63 LUT et 60 registres
pour la file de demandes. Les régressions `legacy_v1_scan_stage` (751
commandes) et `legacy_affine_scan_stage` (604 commandes) passent également.

G21 enregistre les résultats et prédicats de validité des deux diviseurs
avant leur consommation par l'automate : un cycle supplémentaire par
division, sans changement d'arrondi ni de plage. La validation d'une face
intervient après sa capture depuis la DDR. Les paramètres privés de caméra,
de DRAW et de sommet sont capturés indépendamment des grands tests de
validité ; seule la branche valide lance les calculs/lectures ou valide la
caméra. Cela vise les chemins G15 du quotient vers les registres à −3,56 ns,
des commandes caméra vers leurs registres à −3,23 ns et de la réponse DDR
vers les positions à −2,55 ns.

`rtl_validation_pipeline` passe les 105 commandes, sept resets et
descripteurs invalides ; `rtl_world_validation_pipeline` passe les trois
vues et 5 385 commandes shader avec délais DDR d'au moins onze cycles.
Pour accélérer la vérification des primitives synthétisées, le script
`gpu_geometry_20261011/prepare_netlist_views.py` reconstruit trois références
indépendantes de 309 commandes CPU. Leur concaténation reproduit exactement
la trace shader complète et tous ses compteurs : 2 083, 1 201 et 2 101
commandes shader par vue. Une comparaison après synthèse reste distincte
du résultat RTL et de la qualification physique.

### G21 : résultat physique, puis corrections G22

G21 est entièrement routé, mais échoue au timing : **147 endpoints setup,
zéro hold, minimum −2,292 ns**. Les groupes concernés sont USB PHY, DDR/GPU,
bus 80 MHz et sclk. Le décompte physique est 83 541/138 240 ressources
logiques, 53 391/139 140 registres, 58 289/69 120 CLS, 287/340 BSRAM et
177/298 DSP. Ce résultat n'autorise pas un chargement sur carte.
Preuve : `gpu_geometry_20261011/timing_g21.json` ; familles de chemins
détaillées dans `g21_paths.txt`.

Les trois simulations de primitives synthétisées G21 passent séparément
(`netlist_g21_view0`, `view1`, `view2`) : 927 commandes CPU et 5 385 commandes
shader exactes au total. Le test séquentiel complet G19 passe également
(`netlist_g19_full`). Ces comparaisons vérifient la géométrie synthétisée avec
un moteur de pixels remplacé par un acquittement ; elles ne remplacent ni
le test RTL des pixels ni l'analyse physique.

G22 corrige les chemins identifiés sans modifier les fréquences :

- L'état de restitution USB est enregistré en parallèle du compteur de
  63 cycles. Une assertion vérifie `handback_active == (handback != 0)`
  à chaque cycle USB actif. Aucun changement de durée de purge.
- Les produits U×Q et V×Q ont des registres dédiés ; le choix affine ou
  perspective est fait lors de la lecture des sommets. Aucun cycle ajouté.
- Le décalage des pixels du lecteur de lignes est réparti sur deux puis
  trois bits entre les deux étages existants, au lieu d'un puis quatre.
- Les lectures CSR GPU ont une réponse enregistrée et un cycle d'attente
  AHB. Les écritures conservent leur séquencement.
- L'ancienne ancre du registre d'état des triangles est libérée : elle
  imposait un trajet de 7,919 ns entre R98C134 et un diviseur proche de R14C9.
  Les broches et exceptions de timing restent inchangées. Le placement
  autorise également la réplication physique des ressources.

Résultats locaux G22 sous `gpu_geometry_20261011/` :

- `rtl_g22` : 105 commandes CPU, 417 shader, sept resets, 21 commandes
  invalides et 3 145 728 octets exacts, réponse DDR à partir d'un cycle.
- `rtl_world_g22` : 927 commandes CPU, 5 385 shader, trois images complètes
  exactes avec délai DDR minimal de onze cycles.
- `usb_g22` : trois couples d'horloges/phases, reprise après horloge arrêtée,
  reset TX en attente et bouclage du compteur à 68 097 octets ; les trois cas
  passent avec contrôle de l'invariant de purge.
- `reader_g22` : équivalence du lecteur de lignes sur **77 670 746 cycles**,
  16 couches, 64 sprites, tuiles 8/16/32, alignements, clipping et attentes
  DDR. Le cas volontairement surchargé est toujours signalé.
- `csr_g22` : pour chacun des accès direct et via le pont, **1 357 lectures
  et 384 écritures consécutives**, adresses non alignées/trous, annulation par
  reset ; réponses exactes, aucune commande GPU ni perte de FIFO induite.
- `legacy_v1_g22` : 751 commandes, 22 rejets attendus, 31 250 pixels.
- `legacy_affine_g22` : 604 commandes ; pages et gardes exactes.

À ce stade G22 est en compilation, et la carte reste sur C37 / ASTRILLA R18.
Les nouveaux résultats RTL ne sont pas des mesures de FPS sur carte.

La synthèse G22 a terminé : 63 383 LUT, 19 260 ALU et 53 303 registres,
211 BSRAM logiques. Le premier lancement physique s'est arrêté avant le
placement sur une ancre absente : `u_usb_fifo/ep1_reset_s2`, ancien décodage
de reset modifié par l'enregistrement de `handback_active`. G22r retire
uniquement cette ancre supplémentaire et réutilise la netlist G22, SHA-256
`88f5e695a9002dd6906f653497fd2d1898f9c66c8eb99ddf5321f45fc69f9c75`.
`g22_reuse.json` vérifie l'identité du RTL, des données, du SDC et de la
netlist ; seuls des enregistrements INS_LOC/commentaires du CST diffèrent.
La réutilisation refuse toute différence de broches, banques ou horloges.

Les contrôles structurels de synthèse `scanout_synthesis_g22.json` et
`copy_synthesis_g22.json` passent : pas d'absorption DSP à horloges mixtes
dans le scanout, ni de double registre C à activations indépendantes dans
les blocs de copie/V1. Ces contrôles ciblés ne constituent pas une preuve
d'équivalence générale de toute la puce.

Les trois simulations de primitives officielles G22 passent également :
`netlist_g22_view0`, `netlist_g22_view1`, `netlist_g22_view2`, chacune avec
309 commandes CPU et 1 710 lectures de maillage, respectivement 2 083,
1 201 et 2 101 commandes shader exactes. Les compteurs géométriques
correspondent à leurs références. G22r et G22r0 réutilisent cette même
netlist ; ils diffèrent uniquement par l'autorisation de réplication
physique au placement, activée pour G22r et désactivée pour G22r0.

## Historique des compilations géométriques — relevé du 11 octobre, mis à jour à 16 h 10

Périmètre : FPGA complet avec le nouveau moteur G3D1. La marge minimale doit être positive ou nulle et aucun endpoint setup/hold ne doit être en violation. Tous les rapports terminés ci-dessous comptent zéro violation hold. Une absence de rapport ne vaut pas validation. Les nombres setup sont des endpoints, pas un nombre de chemins distincts.

| Version | Marge minimale (ns) | Endpoints setup en violation | Résultat |
|---|---:|---:|---|
| G1 | — | — | Licence bloquée par le bac à sable (AF_NETLINK/hostid) |
| G2 | — | — | 72 connexions non routées |
| G3 | -9.643 | 7302 | Timing non respecté |
| G4 | — | — | Mode d’écriture BSRAM DPX9B non pris en charge |
| G5 | -8.142 | 2091 | Timing non respecté |
| G6 | -6.733 | 1255 | Timing non respecté |
| G7 | — | — | 63 connexions non routées |
| G8 | -7.099 | 1565 | Timing non respecté |
| G8I | -7.099 | 1565 | Timing non respecté |
| G8P | — | — | 3688 connexions non routées |
| G9 | — | — | 6335 connexions non routées |
| G10 | — | — | 1158 connexions non routées |
| G11 | — | — | 5066 connexions non routées |
| G12 | — | — | Ancre vid_hready_s2 absente |
| G13 | -5.449 | 466 | Timing non respecté |
| G14 | -4.879 | 196 | Timing non respecté |
| G15 | -5.598 | 1086 | Timing non respecté |
| G16 | — | — | 504 connexions non routées |
| G16P4 | — | — | 146 connexions non routées |
| G16R | — | — | 152 connexions non routées |
| G17 | — | — | 1 connexions non routées |
| G18 | — | — | 91 connexions non routées |
| G18A1 | — | — | 15648 connexions non routées |
| G19 | -4.669 | 936 | Timing non respecté |
| G20 | — | — | 201 connexions non routées |
| G21 | -2.292 | 147 | Timing non respecté |
| G22 | — | — | Synthèse réussie ; ancre ep1_reset_s2 absente |
| G22R | — | — | 235 connexions non routées ; réplication physique activée |
| G22R0 | -0.564 | 9 | Timing non respecté ; réplication physique désactivée |

Source détaillée : [gpu_geometry_20261011/build_history.json](gpu_geometry_20261011/build_history.json). G22R0 est le meilleur timing terminé à cette date, mais reste impropre au chargement. G19 a terminé après G21 et régresse sur les chemins du diviseur ; la numérotation des variantes ne préjuge pas de leur heure de fin ni de leur qualité physique. La carte conserve C37/ASTRILLA R18.

### Fréquences maximales estimées après routage

Valeurs Gowin du FPGA complet, en MHz ; ce sont des estimations de timing statique, pas des fréquences appliquées sur carte. Les fréquences configurées restent GPU/DDR ≈75, bus 80, PHY 60 et sclk USB ≈120 MHz. Les durées ci-dessous couvrent uniquement le placement/routage, hors synthèse et tests.

| Version | GPU/DDR (75) | Bus (80) | PHY USB (60) | sclk USB (120) | Durée placement/routage |
|---|---:|---:|---:|---:|---|
| G3 | 43.524 | 75.671 | 68.360 | 103.778 | 0h 56m 44s |
| G5 | 47.022 | 48.444 | 57.431 | 134.194 | 2h 25m 27s |
| G6 | 49.836 | 57.527 | 60.646 | 130.410 | 3h 51m 44s |
| G8 | 48.942 | 55.251 | 63.324 | 110.345 | 2h 53m 30s |
| G8I | 48.942 | 55.251 | 63.324 | 110.345 | 2h 53m 3s |
| G13 | 53.244 | 70.707 | 57.273 | 134.488 | 0h 42m 29s |
| G14 | 54.910 | 76.221 | 56.936 | 119.412 | 0h 42m 42s |
| G15 | 52.824 | 76.849 | 55.443 | 91.528 | 2h 52m 20s |
| G19 | 55.549 | 64.399 | 59.391 | 121.710 | 2h 30m 48s |
| G21 | 65.432 | 70.890 | 52.746 | 114.662 | 0h 39m 37s |
| G22R0 | 71.957 | 87.470 | 64.532 | 126.718 | 0h 46m 44s |

La référence C37 actuellement chargée, sans G3D1, affiche une marge minimale de +0,071 ns et zéro violation setup/hold. Son rapport donne GPU/DDR 76,507 MHz, bus 80,458 MHz, PHY USB 60,328 MHz et sclk 122,231 MHz.

### G22r0 : neuf violations résiduelles

Routage complet, marge minimale **−0,564 ns**, neuf endpoints setup, zéro
hold. Tous les groupes autres que DDR/GPU respectent le timing, notamment
bus 80 MHz et les deux domaines USB. Deux familles résiduelles :

- `v1_select` vers l’activation des coordonnées U du raster historique :
  huit endpoints, jusqu’à −0,564 ns ; fanout 487, dont 11,702 ns de routage
  dans le pire trajet. La variante G22r en cours autorise la réplication.
- Validation LIGHT, depuis le bit 255 de la commande capturée vers
  l’activation du DSP d’éclairage : un endpoint à −0,091 ns.

Preuves : `gpu_geometry_20261011/timing_g22r0.json` et `g22r0_paths.txt`.
Aucun chargement : la marge reste négative.

## Validation sur carte prévue

1. Refuser le chargement tant qu'un groupe setup/hold a du slack négatif.
2. Identifier exclusivement la Pro Dock FTDI `2023112818`, recharger en SRAM,
   exiger une nouvelle énumération USB à 480 Mbit/s.
3. Rejouer la qualification USB et les anciennes primitives graphiques.
4. Charger les ressources par le disque DDR volatil, avec relecture intégrale,
   puis les applications par J-Link avec vérification binaire. Aucune écriture
   sur carte SD physique.
5. Comparer les CRC RGB565 des poses ASTRILLA et du monde à caméra libre,
   ainsi que les compteurs matériels sommets/triangles/intersections.
6. Envoyer des positions et orientations nouvelles, puis des paquets à CRC
   erroné, NaN, hors plage et incomplets ; vérifier que l'état reste inchangé
   après rejet et que le rendu continue après une requête valide.
7. Mesurer l'endurance, les FPS, les délais de rendu, les sous-débordements
   LCD et des échos USB binaires pendant l'animation. Rétablir une démo
   autonome à la fin.

## Essai expérimental G22r0 demandé le 11 octobre

Après présentation des neuf violations setup et de la marge −0,564 ns,
l’utilisateur demande explicitement : « ok on teste celui la ». L’essai
porte sur G22r0, en SRAM uniquement. Il ne remplace pas la qualification
physique : les outils habituels et leur refus du timing négatif restent
inchangés. Aucun fichier `physical_qualification.json` ou `bitstream.sha256`
de qualification n’est créé pour cette version.

Le dossier `gpu_geometry_20261011/g22r0_trial_pack` contient le manifeste
expérimental, le rapport de timing non conforme, les empreintes de toutes
les sources figées et des fichiers transférés, ainsi que les applications
WORLD3D et ASTRILLA G3D1 correspondant aux binaires préparés auparavant.
Le bitstream testé a le SHA-256
`fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f`.

Les scripts dédiés `prepare_g22r0_trial.py` et `load_g22r0_trial.py`
conservent `timing_qualified=false` dans les preuves et n’effectuent aucun
changement de fréquence, aucune programmation flash ni écriture SD.
Le chargement identifie le FTDI 2023112818, vérifie l’absence de média
console monté, exige l’acquittement de pause du programme précédent,
puis exige une nouvelle énumération USB à 480 Mbit/s.

À 18 h 15 : chargement SRAM réussi, adresse USB passée de 66 à 68 sur
3-7, 100 séries d’échos binaires exacts (544 100 octets). Suite GPU en cours.

Résultats intermédiaires de l’essai :

- Suite graphique historique complète : PASS, DDR partagée, 16 couches,
  sprites, tuiles, affine, raster RGB565/Z, perspective, overlays et V1.
- WORLD3D : 18 références exactes, quatre paquets invalides rejetés sans
  modification de l’état, 25 échantillons d’animation sans erreur ni
  sous-débordement. **ÉCHEC du seuil de débit : 27,4017 FPS pour 50 requis.**
  La scène utilise 17 objets, 24 billboards et 892 sommets par image. Le
  rendu maximal observé coûte 18 634 106 cycles CPU (23,293 ms à 800 MHz).
- ASTRILLA : 158 références exactes, compteurs géométriques et HUD inclus ;
  test d’endurance complet encore en cours.

Le premier appel de `load_ilm.py` pour USBDISK a utilisé un marqueur
d’attente erroné (`USBDISK R4` au lieu de `USBDISK READY R4`). Le programme
avait bien été vérifié et démarré par J-Link ; une interrogation `?` a
confirmé `USBDISK R4 CDC + MSC BOT_GUARD=1 SD_STATUS=1`. Le résultat du
chargement conserve cet échec de vérification du marqueur et la réponse
positive d’identification. Aucun rechargement supplémentaire n’a été fait.

Les deux autres compilations ont terminé en échec de routage : G20 avec
201 connexions non routées, G22r avec 235. Elles n’ont pas été chargées.

### Résultat final de l’essai G22r0 sur carte

**ASTRILLA G3D1 : PASS**, 158 poses exactes et dix chapitres parcourus.
Mesure : 16 907 images en 308,688641 s, soit **54,770399 FPS**, sans changer
les seuils du test. Rendu maximal 12 332 499 cycles à 800 MHz, soit
**15,415624 ms** ; scanout maximal 853 cycles sur 2 556 disponibles.
Zéro erreur, rejet GPU, descripteur invalide et sous-débordement LCD.
Les 1 216 octets d’écho USB envoyés pendant cette boucle sont exacts.
Les compteurs de commandes émises et terminées correspondent. La lecture
automatique a été rétablie et son acquittement enregistré.

L’utilisateur confirme sur le LCD : **« Oui, correcte et fluide »**.

La carte reste sur **G22r0 + ASTRILLA G3D1 matériel**, chargés en mémoire
volatile. Aucun retour à C37, aucune programmation flash ni écriture SD.
Le bilan est un essai fonctionnel avec limites, pas une qualification
globale : le timing reste non conforme et WORLD3D reste sous 50 FPS.

Preuves locales :

- `gpu_geometry_20261011/g22r0_board_summary.json` : synthèse et empreintes.
- `board_g22r0_trial/` : chargement SRAM, USB, suite GPU historique.
- `world_check_g22r0/` : 18 poses, paquets invalides, débit insuffisant.
- `astrilla_load_g22r0/` : binaire ILM vérifié et démarrage G3D1.
- `astrilla_check_g22r0/` : poses, endurance, CRC et compteurs, reprise.
