# Accélérations G22r0 et LUMA3D — audit du 24 octobre 2026

Cet audit porte sur le GPU **réellement chargé sur Pro Dock**, ses sources figées et le noyau candidat actif. Il ne qualifie pas Neo, ne remplace pas G22r0/R17 et ne représente pas un audit de tous les périphériques USB, SD ou audio. Aucun accès carte n’a été effectué pour cette revue.

Identités examinées :

| Élément | Identité |
|---|---|
| FPGA G22r0 | SHA-256 `fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f` ; [référence conservée](../../../tang/boards/prodock/reference.json) |
| Sources GPU | [snapshot G22r0](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/) ; `gpu_geometry.v` SHA `9bb0231c332306e68b89ed6b74b549a9e7b0f47e099cd5089758c9874dfb61fc` |
| Noyau actif | `6.12.112-prodock-luma3d-g3d1-r1`, [pilote exact du candidat](../build-kernel/prodock_g3d1_20261024_r1/source/drivers/prodock/prodock-gpu.c) ; ABI1 conservée, extension G3D1 additive |
| LUMA3D R1 mesuré | ELF SHA `216623767b298d0c13e3b35bfccdc088ca042c97d1ebc33beece415cea525951` ; [manifeste de l’essai](hardware/valley_20261024_r1/game_manifest.json) |
| LUMA3D R2 préparé | ELF SHA `05b64630c267e364fa2bda14b64406cfa2eb1ae8c78ba58bc2b9ed4e053053f5` ; [manifeste figé](../build/frozen_20261024_r2/manifest.json). Qualification matérielle encore en attente au moment de cet audit. |

Le renderer courant correspond à R2 ; les constats R1 ci-dessous se rapportent à son manifeste et à ses [captures figées](../build/frozen_20261024_r1/). Le noyau partagé de développement a évolué depuis : pour les restrictions effectivement actives, les liens pointent vers la copie du candidat.

| Fonction | État dans R1 / exposition | Limites et preuve dans le RTL chargé |
|---|---|---|
| Transformations, caméra, lumière, DRAW G3D1 | **Utilisé**, exposé par le candidat Linux | Matrice affine Q16.16, six plans de clipping, projection, culling et éclairage directionnel plat. [Décodage](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_geometry.v#L198). |
| Sprites 3D / billboards | **Disponibles, inutilisés dans R1/R2** | Un quad partagé, une matrice par objet et DRAW : perspective, clipping, profondeur et couleur-clé/alpha passent par G3D1 et le raster. [API `gpu_geom_billboard_transform` et `gpu_geom_instance`](../../../fw_console/gpu_geometry.h#L31). Le helper prépare la matrice sur CPU ; les sommets sont transformés sur FPGA. Ce n'est pas le tableau des 64 sprites 2D, ni une commande de dessin multi-instance. Les billboards peuvent remplacer les LOD éloignés pour réduire la géométrie ; leur coût pixel reste à mesurer. |
| Cache de sommets et setup des triangles | **Utilisé** | Maximum 256 sommets et 65 535 faces par DRAW ; indices 8 bits vérifiés par le matériel. Tous les sommets du DRAW sont transformés ; le cache n’est pas une réutilisation persistante entre DRAW. UVQ/Z calculés matériellement. [DRAW](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_geometry.v#L229), [setup](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_geometry.v#L479). |
| Raster RGB565 et profondeur Z16 | **Utilisé** | Cible jusqu’à 1024×512, stride et scissor ; R1 rend en 400×240 puis affiche ×2. Test Z strict, écriture Z, perspective, fog. [Raster](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_v1.v#L434). |
| Rejet par profondeur avant texture | **Utilisé automatiquement**, ordre des objets améliorable | Le Z peut éviter le fetch texture et le shading, mais le résultat perspective est attendu avant ce rejet. Ce n’est pas du HiZ ou un rejet de tuiles. [Ordre exact](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_v1.v#L453). |
| Voie opaque sans lecture de couleur destination | **Déjà utilisée**, même avec fog | Alpha 256, absence d’additif et de texture ARGB suffisent à éviter cette lecture. [need_background](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_v1.v#L111). |
| Voie de shading opaque courte | **Disponible, sous-utilisée** dans R1 ; activée près de la caméra en R2 | Le flag fog désactive cette voie même si son facteur final vaut zéro. Sans fog et avec alpha 256, RGB565 évite plusieurs états de modulation/mélange. [Sélection](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_v1.v#L370), [exécution](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_v1.v#L498). |
| Cache texture | **Utilisé automatiquement** | **32 KiB**, 1 024 lignes de 32 octets, tags physiques et index direct haché. Les anciennes mentions de 2 KiB ne décrivent pas G22r0. Pas de snooping CPU. [Implémentation](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_texture_cache.v#L1). |
| Mipmaps explicites et formats texture | **Disponibles, inutilisés en partie** | RGB565/ARGB4444 jusqu’à 512², LOD explicite 0..9, nearest, repeat/clamp/rejet. R1 charge huit textures 128² et utilise mip0 uniquement. Pas de sélection automatique par dérivées, de bilinéaire/trilinéaire ou de textures compressées. [TEXTURE et LOD](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_v1.v#L361). |
| Perspective rapide | **Utilisée automatiquement** | Deux unités se chevauchent sur deux pixels ; quotient court pour petites coordonnées, division plus longue sinon. Ce n’est pas deux rasterizers. [Unité](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_perspective.v#L1). |
| Alpha, additif, keyzero, modulation, Gouraud | **Disponibles** ; Gouraud utilisé pour le ciel | Fonctions du pixel engine. G3D1 refuse le matériau Gouraud et utilise sa lumière par face ; ne pas confondre les deux interfaces. [Matériau G3D1](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_geometry.v#L241). |
| COPY RGB565 et CLEAR couleur/Z indépendants | **Disponibles, inutilisés par R1**, utilisés par R2 | COPY transfère des blocs 256 bits, gère masques/clipping et chevauchement compatible ; pas d’alpha ou de copie Z. **Chaque COPY invalide le cache texture.** [Copieur](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_copy565.v#L113), [invalidation](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_v1.v#L403). |
| Blitter indexé historique | **Disponible, inutilisé par R1** | Fills, gradients, ligne, cercle/disque, copie, texte, triangle, zoom et affine ; chemins constants par blocs. Ce n’est pas un second accélérateur 3D concurrent. [Opcodes](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/blitter.v#L7). |
| 16 couches bitmap/tilemap | **Disponibles**, aucune couche activée par R1 | Tuiles 8/16/32, flips, défilement, palette ; le noyau actif réserve 12..15 : **12 couches utilisables par le jeu**. [Tuiles](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_tile_row.v#L1), [réservations Linux](../build-kernel/prodock_g3d1_20261024_r1/source/drivers/prodock/prodock-gpu.c#L235). |
| 64 sprites | **Disponibles**, aucun activé par R1 | Indexés, 1..32², flips, transparence de l’index zéro et priorité. Linux permet les 64, avec priorités 0..11 ; palette 240..255 réservée. Pas de Z, rotation ou perspective des sprites de composition. [Cache sprites](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_sprite_cache.v#L1). |
| Composition et lecture DDR | **Utilisées** pour le fond RGB565 ×2 | Les couches/sprites conviennent à un HUD, pas aux objets 3D devant subir profondeur et projection. Scanout prioritaire et ressources DDR partagées ; 16 couches/64 sprites ne garantissent pas leur coût maximum simultané. [Arbitre](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/board/ddr_gpu_arb.v#L1). |
| Compteurs G3D1 | **Exposés, partiellement journalisés dans R1** | Signature, erreurs, sommets, triangles, culls, intersections, slivers, cycles. R1 ne journalisait pas les cycles ; R2 ajoute des deltas périodiques. [ioctl](../build-kernel/prodock_g3d1_20261024_r1/source/drivers/prodock/prodock-gpu.c#L266). |
| Compteurs raster/cache | **Présents mais non exposés par ce noyau** | MMIO 0x38 fragments, 0x3c passés, 0x40 hits, 0x44 misses. `/dev/mem` désactivé : un ioctl additionnel serait nécessaire pour les lire proprement. [Registres](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_accel.v#L127). |
| Batching et fences | **Batch synchrone de 64 commandes utilisé** | FIFO matérielles de mots ; une commande occupe huit mots de 32 bits. Les 24 bits bas du premier mot sont du payload/réservé, pas un format compact 24 bits. Pas d’API Linux async/fence ni de DMA de listes. [Soumission Linux](../build-kernel/prodock_g3d1_20261024_r1/source/drivers/prodock/prodock-gpu.c#L130). |
| Géométrie et raster concurrents | **Absents de cette architecture** | TRI_WAIT attend shader_done avant le triangle suivant. Blitter, ancien raster et G3D1 partagent un ordre de commandes et les transactions DDR. [Attente raster](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_geometry.v#L520), [propriétaire unique](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_accel.v#L225). |
| Fonctions d’un GPU moderne | **Absentes** | Pas de HiZ, occlusion query, instancing, skinning matériel, shaders programmables, MSAA ou texture filtering avancé. Animation, culling de scène, choix des LOD et matrices restent à la charge du CPU. |

Ce noyau propose les ioctls spécifiques `prodock-*`, la mémoire GPU bornée et l’extension G3D1. Il ne fournit pas un autre backend Linux 3D de type OpenGL/Vulkan. Son espace GPU va de `0x00800000` sur `0x05600000` octets ; R1 n’en mappe que 32 MiB. Ne pas remplacer ces bornes par les limites physiques, plus larges, du RTL.

Les [mesures R1](hardware/valley_20261024_r1/performance.json) donnent :

| Mesure | Valeur | Interprétation |
|---|---:|---|
| Images / durée | 672 / 147,414 s | 4,56 FPS moyens ; pas une garantie de cadence stable |
| Commandes / batches | 331 084 / 5 505 | Nombre important de frontières SUBMIT synchrones |
| SUBMIT vu du jeu | 115,451 s | Toute la durée de l’ioctl, pas seulement l’envoi CPU |
| PRESENT vu du jeu | 9,731 s | 14,48 ms/image en moyenne |
| Temps restant | 22,232 s | 33,08 ms/image ; préparation, simulation et autres coûts, pas une mesure CPU exclusive |
| Driver feed / wait | 39,692 / 44,093 s | feed comprend la contre-pression FIFO ; wait comprend GPU et ordonnancement |
| Driver cache | 3,991 s | SUBMIT seulement ; le cache de PRESENT est inclus dans present_us |

Les compteurs driver couvrent aussi le lancement et le travail console après arrêt. Ils sont imbriqués dans les temps utilisateur : **ne pas les additionner** pour reconstruire la durée du jeu. Les 120 secondes silencieuses sont incluses dans les 147,414 secondes. Retirer tout le coût cache SUBMIT mesuré ne ferait gagner que 2,7 % du temps total ; cela ne résoudrait pas seul l’objectif de 30 FPS.

La première image native a été comparée à l’oracle indépendant : 96 000 pixels exacts, compteurs d’erreur nuls. Cela prouve cette image, pas une cadence ni toutes les poses. Les captures modèle R1 donnent :

| Pose | Commandes | DRAW | Faces entrantes | Triangles raster | Intersections de clipping | Fragments du modèle |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 1 168 | 252 | 6 687 | 2 541 | 1 402 | 304 226 |
| 700 | 593 | 137 | 4 791 | 1 730 | 1 672 | 407 178 |
| 1 600 | 316 | 66 | 2 848 | 1 018 | 1 228 | 285 903 |
| 2 200 | 794 | 170 | 5 117 | 1 855 | 1 420 | 299 093 |

Chaque capture est une première image après `--advance` ; son INVALIDATE initial ne prouve donc pas une invalidation explicite à chaque image d’une animation. Le ciel R1 représente 96 000 fragments par image.

Les pistes suivantes sont classées par priorité et demandent des mesures, pas une promesse de facteur d’accélération :

1. **Mesurer R2**, qui prépare une fois le ciel par les mêmes triangles GPU, le copie ensuite et supprime le fog inefficace des objets proches. [Quatre poses sont strictement identiques](../build/render_opaque_copy_r2/comparison.json). Le [contrat r5](../build/render_contract_20261024_r5/result.json) passe sous ASan/UBSan sur 600 états 800×480 et 400 états 1280×720 : scratch à 6 MiB disjoint de Z/assets, COPY bornée, PRESENT uniquement pages 0/1 et aucun PRESENT après erreur. Ces tests ne mesurent pas le matériel. Le coût de l’invalidation texture par COPY doit rester visible dans la mesure.
2. **Trier les objets opaques de l’avant vers l’arrière**, avec stabilité des surfaces coplanaires : le test Z peut éviter texture/shading. Comparer tous les pixels sur des poses fixes ; le test Z strict rend l’ordre des égalités observable. Le tri par texture poursuit un autre objectif et doit être confronté au coût d’overdraw.
3. **Éviter les états identiques et les calculs CPU répétés.** Pose0 R1 contient 129 MATERIAL, 76 LIGHT, 36 TEXTURE et 10 lignes MATRIX identiques à l’état précédent : 251/1 168 commandes potentiellement omissibles, 19→15 batches théoriques. DRAW restaure son matériau de base ; TARGET invalide la caméra. Préserver ces règles. Réduire le double culling, les trigonométries et bornes statiques peut aussi aider ; aucune mesure isolée de leur coût n’est encore disponible.
4. **Mips, LOD et regroupement spatial**, sous contrôle visuel. Réduire les nombreux petits triangles et les intersections de clipping ; conserver au plus 256 sommets par groupe, les silhouettes et les raccords. Le regroupement réduit les DRAW mais peut dégrader la précision du culling. Ces changements ne promettent plus des pixels identiques.
5. **Exploiter les couches/sprites pour l’interface future**, sans remplacer les paysages ou personnages 3D. Cela enrichit le jeu sans rasteriser tout le HUD par triangles ; R1 n’a actuellement aucun coût de HUD à supprimer. Mesurer les cycles de ligne et les underflows.
6. **Envisager une extension de soumission additive seulement après profilage** : moins de fences pour des ressources immuables peut aider. Ne pas changer la taille de l’ABI1, supprimer la publication mémoire ou présenter une image après une faute. Rien de cela n’est déjà une fonction asynchrone disponible.

Pour le diagnostic, le compteur G3D `cycles` est un compteur 32 bits qui inclut les attentes du raster pendant les DRAW : [condition d’incrément](../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_geometry.v#L196). Il exclut l’état PASS des commandes directes V1 : l’attente du ciel Gouraud, de CLEAR et de COPY ne constitue donc pas des cycles G3D, hormis le petit coût de décodage. Ce n’est pas le temps occupé de l’ensemble du GPU. À 75 MHz, il reboucle après environ 57,27 secondes actives. Des deltas toutes les cinq secondes sont adaptés ; un delta unique après deux minutes peut être faux. Les captures fixes et les fenêtres de mesure doivent correspondre aux mêmes poses/états : une moyenne R2 sur 30 secondes au début du parcours n’est pas un A/B contrôlé contre la moyenne R1 de 147 secondes.
