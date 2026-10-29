# Complément art3 — GPU réellement utilisé le 25 octobre 2026

L’[audit historique R1/R2](G22R0_FEATURE_AUDIT.md) reste inchangé. Ce complément
porte sur [art3 figée](../build/valley_living_20261024_art3/manifest.json), ELF
`7fa1062373664d977c26bf6df2a4a5075d64061b967fc3d6d9b831a841302882`, laissé sur
Pro Dock par [l’essai vl2](hardware/living_20261024_vl2/REPORT.txt). Aucun accès
carte supplémentaire n’a été effectué pour cette analyse. Neo n’est pas qualifiée
par les résultats Pro Dock.

## Fonctions effectivement employées

| Fonction | Usage art3 et source |
|---|---|
| G3D1 | Matrices, caméra, projection, lumière, clipping, culling et DRAW dans [render.c](../build/valley_living_20261024_art3/source/games/luma3d/src/render.c). Les poses sont calculées en temps réel. |
| Z16, perspective, cache texture | Matériau texturé `1|2|4|16`, alpha 256, RGB565 ; le raster rejette la profondeur avant le fetch texture. Cache 32 KiB automatique, décrit dans l’audit historique. |
| Voie opaque courte | Fog retiré lorsque toute la sphère de l’objet est avant le début de brume avec marge 5 m. Le matériau proche permet `PIX_OPAQUE` du G22r0. |
| CLEAR et COPY | Ciel Gouraud calculé une fois à 6 MiB, COPY matériel vers les pages couleur alternées ; CLEAR de Z seul. COPY invalide le cache texture, coût toujours présent. |
| LOD | Niveaux de maillage sélectionnés selon la distance. Pas de simplification supplémentaire dans art3 par rapport à sa base de campagne. |
| Couches HUD | Une ou deux couches indexées, aux offsets 20/21 MiB. Les textes sont calculés seulement quand leur contenu change, avec cache distinct par page. [hud.c](../build/valley_living_20261024_art3/source/games/luma3d/src/hud.c). |
| Animation | Matrices G3D pour corps articulés, moulin et arbres ; UV d’eau/cascade mis à jour dans une banque alternée ; oiseaux en un DRAW de neuf faces. 2 880 octets dynamiques écrits par image. |
| Cache logiciel des états | Six slots : trois lignes MATRIX, LIGHT, MATERIAL, TEXTURE. Les commandes identiques sont omises ; invalidation conservée après TARGET. |
| Mesure | Compteurs géométrie par fenêtres de 5 s et fin de benchmark, deltas feed/wait/cache/present ; tableaux de commandes et oracles exacts. |

## Fonctions disponibles mais non utilisées ici

- Zéro sprite 2D de composition et zéro billboard 3D. Les anciens candidats de
  billboards ont été conservés ; leur réduction de triangles n’a pas donné le
  gain matériel demandé. Les oiseaux d’art3 sont de vrais petits maillages.
- Matériau alpha 256 : aucun mélange alpha ou additif. L’eau est opaque avec UV
  animés ; ses mouvements ne prouvent pas un effet de transparence.
- Textures toujours à mip 0. Le GPU accepte un niveau explicite, pas un choix
  automatique par dérivées. Préparer des mips changerait le rendu et doit être
  comparé séparément. Les textures 128/256² d’art3 sont effectivement chargées.
- Aucun blitter historique pour le paysage ; les couches d’interface évitent
  déjà de rasteriser chaque lettre en triangles 3D.
- Les 16 couches ne sont pas une cible d’occupation : Linux réserve 12..15 et
  utiliser davantage de couches ne rendrait pas le paysage 3D plus rapide.

## Coûts mesurés et limites

[Résultat brut vl2](hardware/living_20261024_vl2/trial/result.json), pose initiale,
30 images après 3 de chauffe ; la scène art3 est enrichie, donc cette comparaison
avec R3 n’isole pas un changement de renderer :

| Mesure par image | R3 | Art3 |
|---|---:|---:|
| Débit | 8,74 FPS | 7,31 FPS |
| Temps | 114,4 ms | 136,8 ms |
| Commandes |356|419|
| Lots synchrones de 64 maximum |6|7|
| DRAW |81|93|
| Sommets transformés |1590|1956|
| Triangles raster |936|1088|
| Cycles G3D |4,202M|5,259M|
| Driver feed |22,38ms|29,00ms|
| Driver wait |44,29ms|52,50ms|
| Driver cache SUBMIT |4,40ms|4,96ms|
| Driver present |17,88ms|19,15ms|

Les temps driver sont imbriqués dans les ioctls ; ne pas les additionner à la
mesure utilisateur. `feed` comprend la contre-pression FIFO et `wait` le GPU et
l’ordonnancement. Le cache de PRESENT n’est pas inclus dans `cache_us` SUBMIT.
Le [pilote figé](../build-kernel/prodock_g3d1_20261024_r1/source/drivers/prodock/prodock-gpu.c)
reste synchrone et impose une publication de cache avant/après chaque lot ;
il n’existe pas de soumission asynchrone ou DMA de listes dans cette ABI.
Le retrait hypothétique de tout le cache SUBMIT ne suffirait donc pas à 30 FPS.

Les six poses art3 donnent 7,31–12,82 FPS. Le parcours total donne 7,45 FPS, avec des
fenêtres globales 1,96–12,52 FPS incluant les commandes UART avant/après la fenêtre
silencieuse. Ces chiffres ne sont pas des percentiles d’images. Erreurs et
underflows sont nuls ; un sliver est rejeté pendant le mouvement.

## Pistes séparées, sans promesse de gain

1. Trier les surfaces opaques pour éviter des lectures texture masquées, tout
   en gardant les états partagés et l’ordre des égalités de profondeur.
2. Réduire l’usage inutile de fog avec une borne plus précise, en conservant
   la même marge et en comparant les pixels.
3. Optimiser culling et calculs CPU conservateurs ; mesurer leur coût AE350.
4. Mipmaps, LOD ou billboards éloignés seulement comme candidats visuels
   explicitement différents, avec nombre de commandes et coût raster mesurés.
5. Aucun changement de FPGA, pilote ou noyau pour ce lot logiciel.
