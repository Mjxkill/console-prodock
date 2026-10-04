# L13–L15 : RGB565, alpha, textures et Z16

3 octobre 2026. **R3 validé en simulation, sur carte et visuellement.**
L'utilisateur confirme les deux cubes en rotation et les motifs noirs de
la texture. Le défaut de faces disparues de r2 est corrigé ; les preuves
historiques r1/r2 sont conservées ci-dessous. Le résultat final est résumé
dans la dernière section et dans `gpu_l1315_20261003/r3/result.json`.
`gpu_l1315_r1`, refusé pour une divergence après synthèse du calcul
d'adresse d'affichage, est conservé comme preuve du défaut corrigé.

## Périmètre implémenté

- L13 : mélange RGB565 par composante, alpha uniforme 0..256 par commande,
  source opaque ou texture, zéro transparent optionnel. Mélange dans le
  moteur de dessin ; le compositeur indexé conserve son contrat historique.
- L14 : triangles texturés RGB565, interpolation affine, cache source
  128 × 128 maximum, rejet/répétition/clamp par axe, plus proche voisin.
  Correction de perspective et filtrage bilinéaire restent des extensions.
- L15 : profondeur 16 bits en DDR, interpolation de plan écran, comparaison
  stricte LESS, écriture indépendante du test, effacement natif accéléré.
- Framebuffer RGB565 800 × 480, format et page appliqués au retour vertical.
  Les modes indexés, 16 couches, sprites, tuiles et affines sont conservés.

Contrat : [GPU_L13_L15_RGB_DEPTH.md](../ARCHI/GPU_L13_L15_RGB_DEPTH.md).
Commandes firmware : `a` vérifie quatre poses, `b` anime, `c` met en pause.

## Simulations

- 604 commandes historiques : mêmes pixels et gardes, équivalence du blitter
  sur 2 081 517 cycles, DMA natif identique sur 2 081 518 cycles, décalage zéro.
  Référence : sources figées de `gpu_l12_usb_hs33_idle_r3`.
- Première campagne indépendante Python : 321 commandes RGB/depth,
  11 refus attendus, pages couleur/Z/source et toutes leurs gardes exactes.
  Alpha extrême/intermédiaire, intersections, profondeur égale, transparence,
  textures impaires/non carrées, modes d'adressage, coefficients extrêmes,
  cache avant dessin dans la même page, adresses de page haute.
- Campagne étendue : **341 commandes**, dont deux fenêtres présentant les
  mêmes triangles croisés dans les deux ordres de soumission. Couleur et
  profondeur identiques, pages et gardes exactes, 11 refus attendus.
- Les quatre listes de commandes réelles du firmware passent également
  contre le modèle C à demi-plans : 125, 125, 117, 125 commandes (chargement
  de texture inclus). Chaque pixel de couleur/profondeur est comparé, avec
  les octets inutilisés des emplacements de 1 Mio. Accès CPU et affichage
  concurrents, latences DDR variables, FIFO AHB pleine et masques natifs.
- Préparation CPU et référence : balayage des 256 angles sous UBSan, PASS.
- Affichage : RGB565/palette, pixels, dimensions, checksum, permutation de
  page/format au retour vertical, sous-alimentation délibérée et reprise,
  accès CPU concurrents ; les deux formats de départ passent en 64 × 4.
- 800 × 480 : 16 surfaces, sprites, tuiles, alignements, commits et reprise
  DDR passent sur la charge de référence `TILES=7`.
- Affichage RGB565 **800 × 480** : chaque pixel vérifié, checksum exact,
  changement RGB565/palette au retour vertical, sous-alimentation et
  récupération, 2 974 808 lectures CPU concurrentes ; PASS.

Le test `TILES=8` avait été indiqué à tort dans CLAUDE.md. Il dépasse la
capacité par ligne : l'ancien bitstream figé et le nouveau RTL échouent
exactement au pixel (0,3) de la pose 8, à 581717312000 ps. Ce résultat n'est
pas masqué ; les deux journaux sont conservés. Le test documenté dans L11
emploie bien `TILES=7`, qui passe. CLAUDE.md est corrigé.

Les journaux et images de référence sont dans `gpu_l1315_20261003/`.

## Compilation et matériel

Firmware initial complet : 64 160 octets ITCM (code + données initiales),
29 096 octets BSS. Toutes les anciennes démonstrations restent présentes.
Fréquences conservées : cœur 800 MHz, bus 80 MHz, DDR/GPU 75 MHz, LCD 35 MHz.
USB conservé en HS, contrôleur 3.3 et PHY 3.5 Advance régénérés avec les
mêmes options que la version chargée. Aucun essai FS.

### Premier chargement : divergence de synthèse identifiée

`gpu_l1315_r1` respecte le timing (+0,144 ns), se recharge en SRAM et
s'énumère à 480 Mbit/s. Vingt tours d'échos passent, puis le contrôle G1
échoue : checksum attendu `c5c4fc70`, affichage `95cc3524`. Le test DDR CPU
complet avait passé. En lançant séparément la pose 0 L13–L15, **tous les
pixels couleur et Z et leurs gardes passent la comparaison CPU**, mais le
checksum de l'affichage vaut `d653efd9` au lieu de `75e7c579`.

Le calcul `active_base + ligne*800*(rgb565 ? 2 : 1)` a conduit Gowin à
absorber des registres de deux domaines dans le DSP `n2874_s` de
`gpu_scanout`. Le rapport officiel de synthèse montre :

- entrée C = `shadow_base`, horloges `{vid_hclk,lcd_clk_d}` ;
- C_IREG = CLK0/CE0 : validation pixel au retour vertical ;
- C_PREG = CLK1/CE1 : écriture AHB de la boîte aux lettres.

Ces deux étapes sont inversées par rapport au RTL, qui capture d'abord
la boîte aux lettres sur AHB, puis la base active sur l'horloge pixel.
Le résultat pour les lignes 1..479 utilise donc l'ancienne page ; la ligne
0 utilise bien la nouvelle page, par le chemin séparé `next_base`.

Confirmation physique : après la pose 0 RGB565, une commutation vers la
page 7 préremplie de `a5a5` donne exactement `7bf0ca99`, soit :

```text
75e7c579 - 400*10831083 + 400*a5a5a5a5 = 7bf0ca99 (modulo 2^32)
```

C'est la scène précédente avec uniquement sa première ligne remplacée.
Une seconde validation sur la même page, en indexé, donne alors le
checksum uniforme exact `a5a4b300`. Le défaut ne vient pas du rasteriseur.

Correction r2 : le choix ×1/×2 est exprimé par un multiplexage et un
décalage de bits, séparés de l'addition d'adresse. Le résultat de synthèse
ne contient plus ce DSP à deux horloges ; la multiplication constante
par 800 conserve un DSP combinatoire. Le banc complet RGB565/indexé
800 × 480 passe à nouveau, avec 2 974 808 lectures CPU concurrentes.

`tools/check_gpu_scanout_synthesis.py` refuse r1 et accepte r2 ; il vérifie
uniquement le module ouvert `gpu_scanout`, sans modification de netlist.
Ce contrôle est ajouté aux prochains builds avant publication du SHA du
bitstream. Pour r2, déjà en cours lors de cet ajout, le même contrôle est
exécuté séparément. Il complète la simulation RTL et les essais physiques,
sans constituer une preuve générale d'équivalence de synthèse.

### R2 : correction sur carte et mesure

La première campagne r2 passe G0–G6, FAST, L11, L12 et les quatre poses
L13–L15. Les empreintes couleur sont `75e7c579`, `1e0551c0`, `e933afc6`,
`7ed45f20`, avec comparaison intégrale des pages Z et des gardes mémoire.
L'animation atteint 54,84 à 55,01 images/s ; le dessin le plus long observé
sur cette campagne prend 8 251 737 cycles CPU, soit 10,315 ms à 800 MHz.
Les accès DDR CPU concurrents passent, sans sous-alimentation de l'affichage.

Le premier test hôte de pause lisait le checksum immédiatement après
l'acquittement : le nouveau framebuffer venait d'être validé au retour
vertical, mais son checksum est publié après la dernière ligne. Deux
lectures pouvaient donc légitimement voir l'ancienne puis la nouvelle image.
Le test attend maintenant 120 ms avant la première lecture, comme les tests
G1 et L12, puis contrôle la stabilité pendant que les trames continuent.
Cette correction ne modifie ni RTL ni firmware ni seuil de performance.
La campagne finale reprend deux rechargements et la suite complète.

Ressources **du design complet** après routage r2 :

| Ressource | Utilisation | Pourcentage exact arrondi |
|---|---:|---:|
| Logique (LUT + ALU) | 42 929 / 138 240 | 31,1 % |
| Registres | 31 979 / 139 140 | 23,0 % |
| BSRAM | 223 / 340 | 65,6 % |
| DSP | 49 / 298 | 16,4 % |
| Horloges PRIMARY | 8 / 8 | 100 % |

Par rapport à `gpu_l12_usb_hs33_idle_r3` : +8 978 éléments logiques,
+4 618 registres, +16 BSRAM et +24 DSP. Il s'agit d'une différence entre
deux designs complets routés, pas d'un chiffre isolé attribué à l'IP vidéo.
Timing : 110 chemins détaillés, minimum **+0,144 ns**, aucun chemin
setup/hold en échec. Le SDC conserve son SHA-256
`c9367c2d390554345db5bcc5dbb115a8c348b955dd5013e99e1ecade80c8f64b`.
Audit des pointeurs Gray après routage : 12 trajets pont DDR, maximum
1,538 ns ; 18 trajets observateur USB, maximum 1,282 ns. Ces mesures ne
sont pas une simulation analogique de métastabilité.

### Campagne finale et artefacts

**PASS** : deux rechargements SRAM consécutifs, chacun avec nouvelle
énumération USB **480 Mbit/s** et 20 tours d'échos, puis suite complète
G0–G6/FAST/L11/L12/L13–L15 après le dernier chargement. Les 217 640 octets
des échos de cette campagne sont exacts. En incluant la première campagne
r2, trois chargements HS et 326 460 octets d'échos sont vérifiés.
Le défaut historique d'instabilité USB n'est pas déclaré définitivement
expliqué par ces tests.

Les quatre poses couleur/Z passent, ainsi que les gardes, la pause, la
progression des trames pendant la pause, les accès DDR CPU concurrents et
le retour au rendu indexé avec les cinq checksums de pages exacts. La démo
est ensuite relancée en RGB565. **Aucun underflow** sur l'ensemble.
Mesures finales sur trois fenêtres de 120 images :

| Fenêtre | Cadence | Rendu moyen | Rendu maximal |
|---|---:|---:|---:|
| 1 | 54,99 images/s | 9,718 ms | 10,233 ms |
| 2 | 54,84 images/s | 9,510 ms | 10,322 ms |
| 3, après activité DDR CPU | 55,01 images/s | 9,653 ms | 10,228 ms |

Mesures pour cette scène, à 800 MHz CPU : le rendu inclut préparation et
soumission CPU, puis attente de fin GPU. Le temps complet d'une image inclut
la présentation au retour vertical. Des maxima de 25,93 ms apparaissent
dans les fenêtres comprenant des échanges de diagnostic ; la cadence
moyenne ne constitue donc pas une garantie de latence maximale générale.

Ancien bitstream r2, conservé localement dans
`tang/impl/gpu_l1315_r2/impl/pnr/console_gpu_l1315_r2.fs`. Il est remplacé
par r3 dans l'archive de livraison. SHA-256 historique :

```text
108b00c3faaed8636349179f7559bbc9ef19e5e6d47bde76d93ed34bdf765080
```

- 105 sources figées, contrôlées par SHA avant chargement ; manifeste r2 dans
  `gpu_l1315_20261003/r2.sources.json`.
- Preuve finale : `gpu_l1315_20261003/r2_board/result.json` et `gpu.log`.
- Première campagne r2 et erreur de temporisation du test hôte :
  `gpu_l1315_20261003/r2_initial_board/`.
- Ancien r1 refusé : `gpu_l1315_20261003/r1_board/` et audit de synthèse r1.
- Timing, ressources, audits Gray et synthèse : `gpu_l1315_20261003/r2.*`
  et `r2_*json`. Références de scène et journaux de simulation dans le même
  dossier ; empreintes des outils de test dans `test_sources.json`.
- Sources FPGA et firmware inchangées entre les trois chargements r2.
  Seule l'attente de publication du checksum a changé dans le test hôte.

Les fonctionnalités livrées sont le mélange **dans le moteur de dessin**,
la texture **affine au plus proche voisin** et le Z16. Alpha par pixel,
alpha du compositeur 16 couches, correction de perspective et filtrage
bilinéaire restent des extensions distinctes.

## R3 : défaut géométrique signalé par l'utilisateur

L'utilisateur signale une face qui disparaît brusquement et des panneaux
entremêlés plutôt que deux cubes lisibles. Son observation révèle une lacune
de la validation r2 : le modèle de pixels indépendant et le matériel
consommaient tous deux une liste de commandes préparée par le même code C.
Une face omise par cette préparation était donc absente des deux images.

Le préparateur bornait l'origine Z du plan à la plage non signée 32 bits
Q16.16. Cette origine est la profondeur **extrapolée à (0,0)**, pas celle
d'un sommet. Elle peut être négative ou dépasser 65535 pour une face dont
tous les sommets sont devant la caméra et dans la plage Z16. Le préparateur
retournait silencieusement sans émettre le triangle. L'instrumentation de
l'ancien code est conservée dans `r3/r2_missing_planes.txt` ; elle montre
notamment des faces d'aire non négligeable supprimées dès l'angle 0.

Corrections :

- Origines U/V/Z signées sur 48 bits, format étendu explicite au mot 4 des
  commandes PLANE ; ancien format accepté inchangé. Accumulateurs 49 bits
  avec garde ; plage Z16 contrôlée au pixel, après interpolation.
- Une erreur de préparation est désormais remontée par `raster_scene`,
  puis signalée par `RASTER FAIL PLANES`, au lieu d'être invisible.
- Culling également après projection entière : les triangles presque vus
  par la tranche peuvent être inversés par l'arrondi des sommets.
- Texture de démonstration en clamp. Une valeur interpolée comme
  `v=-0,000961` sur une arête commune prenait auparavant l'échantillon -1
  et pouvait ouvrir un trou d'un pixel ; elle prend maintenant le texel
  de bord. Les trois modes de texture restent disponibles et testés.
- Boucle sur **512 phases**, comme l'exige la seconde rotation à angle/2.
  La boucle précédente sur 256 phases faisait sauter cette rotation.
- Deux cubes séparés et bordures blanches ; panneaux translucides fixes
  en dessous. Référence animée dans `r3/expected_animation.webp`.

Nouvelles preuves avant compilation :

- **359 commandes** RTL/DDR, pages et gardes exactes, **13 refus attendus** :
  ancien format, origines étendues positives/négatives, valeurs extrêmes
  sur 48 bits, pas de débordement dans la plage Z visible, bits réservés.
- Quatre listes firmware réelles comparées au modèle de pixels :
  133, 133, 133 et 141 commandes, chargement de texture inclus.
- Test géométrique indépendant `TESTS/test_gpu_raster_geometry.py` :
  enveloppe convexe des huit sommets projetés de chaque cube, indépendante
  des triangles soumis. **22 905 121 pixels intérieurs** ont une profondeur
  écrite sur les 512 phases (plus la phase de fermeture), sans aucune face
  refusée. Une marge d'un pixel au contour tolère la quantification écran.
- Même liste de commandes à 0 et 512, déplacement continu des sommets
  entre phases, y compris au bouclage ; calculs sous UBSan.

La comparaison couleur/Z seule n'est plus utilisée comme preuve de
complétude de la géométrie. Le firmware r3 occupe **64 488 octets ITCM**,
BSS 29 104 octets.

### Résultat final R3

**PASS** sur Pro Dock : deux rechargements SRAM avec nouvelle énumération
HS 480 Mbit/s, 40 tours d'échos soit **217 640 octets exacts**, puis toute la
suite G0–G6/FAST/L11/L12/L13–L15. Les quatre images RGB565, profondeurs,
gardes mémoire et checksums affichés sont exacts :
`5c621648`, `acabdcd1`, `56021377`, `25d5618a`.

**600 images d'animation** couvrent un tour complet de 512 phases et son
bouclage. Aucun underflow. Pause stable avec trames toujours actives,
accès DDR CPU concurrents, retour au mode indexé avec cinq checksums de
pages exacts, puis animation RGB565 relancée. Le test hôte exact est copié
avec son SHA dans le dossier de résultats avant son exécution.

| Mesure finale | Résultat |
|---|---|
| Cadence, cinq fenêtres de 120 images | 54,99 / 54,84 / 54,84 / 54,84 / 54,55 images/s |
| Rendu moyen par fenêtre | 11,68 à 12,04 ms |
| Rendu maximal observé | **12,518 ms**, 10 014 691 cycles à 800 MHz |
| Temps complet maximal, échanges de diagnostic inclus | 29,851 ms |
| Timing | **+0,143 ns** minimum, 110 chemins détaillés, aucun échec setup/hold |
| Logique du design complet | **42 974 / 138 240 = 31,1 %** |
| Registres | 32 041 / 139 140 = 23,0 % |
| BSRAM | 223 / 340 = 65,6 % |
| DSP | 49 / 298 = 16,4 % |
| Horloges PRIMARY | 8 / 8, aucune nouvelle horloge |

Fréquences et SDC inchangés. Audit Gray après routage : 12 trajets du pont
DDR, maximum 1,060 ns ; 18 trajets de l'observateur USB, maximum 1,263 ns.
La lecture de la synthèse confirme l'absence de DSP à registres de deux
horloges dans le calcul d'adresse de `gpu_scanout`.

Confirmation utilisateur : « Oui 2 cube qui tourne sur chaque face il y a
des diagonal de petit cubes noir ? ». Ces carrés noirs diagonaux font
volontairement partie de la texture ; ils sont opaques sur les cubes.
Les trois panneaux du bas utilisent le noir comme clé de transparence.

Livraison : [bitstream SRAM](../bitstreams/console_gpu_l1315_800.fs),
[notice](../bitstreams/console_gpu_l1315_800.md), 106 sources figées.
SHA-256 final :

```text
35ddb9d920a292052afed94f7daa8d75aa224c74caa57ce561c33ae6de3659c2
```

Journaux, rapports, références et résultats finaux dans
`gpu_l1315_20261003/r3/`. L'[animation de référence](gpu_l1315_20261003/r3/expected_animation.webp)
est reproductible avec `tools/render_gpu_raster.py --out DOSSIER --animation --sweep`.
