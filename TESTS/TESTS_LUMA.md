# Luma : aventure automatique sur Pro Dock

Développement du 4 octobre 2026. Demande : une démo d'aventure soignée,
inspirée des aventures vues de dessus, **qui joue toute seule**. Le programme
embarqué pilote le déplacement, la caméra, les combats, les effets et la boucle.
Les personnages et le décor sont originaux, générés pour ce projet.

## Périmètre matériel et mémoire

Le FPGA reste exactement **R31**, archive `bitstreams/console_gpu_v1_800.fs`,
SHA-256 `60806fa2e988641e5b67ddcc5b13873c5b39c87621d5f1a23bbcf5e80b6d6aee`.
Il n'y a aucune modification RTL/netlist/contrainte ni nouvelle synthèse :
les mesures de timing et d'occupation de `TESTS_GPU_V1.md` restent celles du
circuit utilisé. Les fréquences restent CPU 800 MHz, bus 80 MHz, GPU 75 MHz,
LCD 35 MHz. La console négocie toujours **480 Mbit/s**, sur la branche directe 3-7.

Contrairement au firmware diagnostic incorporé à l'ITCM, Luma est une
application téléchargée dans l'ILM, avec données/pile dans le DLM. Cette
méthode a été essayée sur la carte réelle ; il ne s'agit pas d'un changement
du firmware incorporé au `.fs`. R31 a d'abord été rechargé en SRAM. J-Link
charge ensuite l'application sans réinitialiser la DDR ou le contrôleur USB.
Le PC ne diffuse aucune image pendant la démo.

| Région | Taille / usage |
|---|---|
| Programme à `0xa0000000`, entrée `0xa000000c` | 17 808 octets : texte 16 448, données initiales 1 360 |
| BSS en DLM | 3 016 octets ; assertion du linker réservant au moins 16 Kio à la pile |
| Ressources à `0x04000000` | 1 954 720 octets, alignements de 32 octets |
| CRC32 des ressources hors en-tête | `f5f9f450` |
| SHA-256 ressources | `69517baf121eb36459b183d1bd568b5f3630910c0c7ac6929058e071957bf3e9` |
| SHA-256 programme | `88aab6b33d5898090c4206da83214afbf88e59a7e7d2f8568798594a6487e388` |

Le chargeur sélectionne les séries FTDI **2023112818**, J-Link **506005083**
et CDC **11252024**. Il vérifie les SHA-256 locaux et relit les deux blocs
chargés (`Verify successful`). Le firmware publie le cache DDR, puis vérifie
son en-tête et le CRC32 avant d'activer l'affichage. Le chargement complet,
avec relecture des 1,95 Mo, a pris environ **196 secondes** via J-Link ; ce
n'est pas un débit de transfert USB CDC mesuré.

## Validation sur hôte

Commande :

```sh
python3 tools/render_luma.py --sweep --animation
```

- Les **5 600 phases** de la boucle s'exécutent sous UBSan, avec vérification
  des bornes de caméra, adresses et dimensions des sprites.
- Maximum de **42 sprites 32 × 32 visibles** simultanément (un personnage
  64 × 64 en utilise quatre), sur les 64 disponibles.
- Treize phases couvrent titre, défilement, pont, trois combats, gardien,
  escalier, cristal et fondu final.
- Les pixels du compositeur rapide d'aperçu sont comparés octet pour octet
  à `tools/gpu_compose.py`, référence indépendante du firmware et du RTL.
- Le hash calculé emploie le même contrat de registre LCD ordonné que les
  autres jalons, sans réutiliser une implémentation matérielle pour les pixels.

Preuves : `luma_20261004/host_validation.txt`, `preview/expected.json`,
`preview/frame_*.png`, `sources.tar.gz` et `build.txt`.
`preview/luma.mp4` est un **aperçu calculé**, échantillonné à environ 5 images/s
sur la durée complète ; ce n'est pas une capture du panneau ni sa cadence.

## Validation sur carte

Le journal `luma_20261004/load_r1/startup.txt` confirme :

```text
LUMA READY R31 ILM core=800MHz assets=1954720 crc=f5f9f450 autoplay=1
```

La commande `T` met la séquence à une phase exacte, attend la transaction
au retour vertical puis trois images complètes avant de lire le hash LCD.
Les **13/13 phases correspondent** aux références suivantes :

| Phase | Hash LCD |
|---:|---|
| 100 | c4e2e7fe |
| 800 | 10894755 |
| 1600 | d3a814f2 |
| 2305 | 71aea796 |
| 2640 | 5cebd145 |
| 2958 | c96f080b |
| 3480 | ce0d68cb |
| 3880 | 67ecc5d5 |
| 4115 | 6c32623e |
| 4490 | b6613d11 |
| 4900 | b7d05e60 |
| 5390 | f63801ff |
| 5560 | 7ab5eb72 |

L'endurance est pilotée par `tools/check_luma.py` : lecture périodique des
compteurs et échos binaires de 32 octets pendant l'animation. Résultat : **PASS**, 316,53 secondes, **17 424 images**, **3 boucles** complètes,
**55,04 images/s**, 1 984 octets d'écho exact. Aucune ligne manquante, couche
ou sprite invalide, ni erreur applicative. Maximum : **734/2 556 cycles par
ligne** (28,7 % du budget) ; 3 851 cycles de rechargement du cache de sprites.
Preuves : `luma_20261004/check_r1/result.json` et `usb.txt`.

Le rechargement du programme seul, ressources conservées en DDR, passe aussi
en **2,8 secondes** (`reload_r1/`). Les CRC, identité et compteurs sont corrects.
L'utilisateur confirme le **4 octobre : « Oui, c’est fluide et correct »**.

## Portée et limites

Les tests de pixels sont mesurés sur le chemin LCD réel, pas seulement sur le
CPU. Le hash porte sur les indices : il ne prouve pas à lui seul la couleur,
le branchement du panneau ou l'appréciation visuelle. Les fichiers PNG/MP4
montrent le résultat attendu. La confirmation visuelle de l'utilisateur est acquise pour R1, distinctement
des tests automatiques.

Les données d'animation sont scriptées ; il n'y a pas encore de commandes de
jeu, d'IA, de collisions générales ou de son. La version R1 boucle automatiquement
en environ **102 secondes**. Le chargement est volatile : après extinction ou
reconfiguration, relancer `tools/load_luma.py` selon `assets/luma/README.md`.
La suite de diagnostic vidéo complète reste accessible après restauration
R31 ; elle n'est pas embarquée simultanément dans cette petite application.


## Suite R2 et grand final LUMA

À la demande de l'utilisateur, l'aventure est prolongée par une démonstration
plus visible des accélérations du GPU, puis un grand final avec portrait et
titre LUMA. La scène reste entièrement automatique, sur le même bitstream R31.

La boucle contient désormais **8 320 phases** : 5 120 d'aventure, puis 3 200
pour les lumières additives, le portail déformé, les cristaux texturés en
perspective avec profondeur Z16, les ondes et le grand final. À partir de la
phase 7 080, un éventail Gouraud opaque grandit jusqu'à dépasser les quatre
coins du LCD. À partir de 7 320, un portrait natif 352 × 440 monte dans le
champ ; le titre LUMA grandit à droite, sur un fond d'anneaux animés et d'étoiles.
Le portrait original a été généré avec la feuille du héros comme référence ;
prompts et mode intégré imagegen sont conservés dans `assets/luma/prompts.md`.

### Choix de rendu et budget

Deux premiers essais R2 en RGB565 natif ont passé les comparaisons de pixels,
mais leur cadence mesurée était insuffisante : environ **27,4 images/s** pour
l'essai r2 et **28,3 images/s** pour r3. Le passage au maillage affine pour
le portail, la copie partielle et l'élimination des faces cachées ont réduit
le coût, sans permettre 55 images/s. Ces essais ne sont pas la version finale.

Le rendu RGB565 R2 utilise donc le mode matériel **400 × 240 agrandi ×2**.
L'aventure précédente conserve son décor natif 800 × 480. Le portrait, les
textes et tous les sprites sont toujours composés en 800 × 480 après
l'agrandissement. Les deux surfaces couleur et le tampon Z occupent chacun
192 000 octets ; le fond intermédiaire utilise une quatrième page. La restauration
du fond rend les sauts de diagnostic déterministes, y compris après le final.
Pendant l’agrandissement opaque, quatre bandes entourant un rectangle intérieur
sont copiées ; la lumière recouvre tous les pixels du rectangle. Le portail utilise une déformation UV affine ; l'interpolation de
perspective est réservée aux vrais objets 3D.

La lumière finale emploie un éventail Gouraud opaque : aucun mélange alpha
plein écran avec relecture du fond n'est nécessaire. Les anneaux et les
petits halos emploient réellement le mode additif. Les facettes projetées
inférieures à huit pixels d'aire sont éliminées avant génération des gradients
Z, puis les facettes restantes sont testées par le tampon de profondeur.

### Référence indépendante

`tools/render_luma.py --sweep` exécute toutes les **8 320 phases sous UBSan** :
au plus **58 sprites visibles** et **1 485 commandes GPU par image**. La
croissance du grand anneau a révélé un débordement d'un produit intermédiaire
32 bits ; le produit est maintenant explicitement calculé sur 64 bits.

Les poses de l'aventure sont comparées à `gpu_compose.py`. Les effets sont
rejoués dans le modèle Python indépendant de `TESTS/test_gpu_v1.py`, incluant
texture, profondeur, interpolation, addition, copie, agrandissement ×2 et
composition native. Les références comprennent le CRC32 des 192 000 octets
RGB565 et la somme des couleurs RGB666 envoyées au LCD. Elles couvrent aussi
la lumière presque plein écran et trois états du portrait/titre.

`luma_fx_20261004/preview/luma_fx.mp4` est un aperçu calculé de la suite,
échantillonné toutes les onze phases ; ce n'est pas une capture du LCD.

L'essai r4, déjà en mode 400 × 240, passe 25/25 poses et 183,8 secondes
sans erreur, mais perd brièvement une quarantaine d'images lors de la lumière
plein écran. L'essai r5 supprime les copies de fond devenues invisibles à cet
instant. `TESTS/test_luma_bloom.py` prouve la couverture des **96 000 pixels
à chacune des 240 phases** du grossissement, en utilisant les règles de
rasterisation indépendantes. Onze comparaisons de toute la mémoire, gardes
comprises, commencent depuis une surface empoisonnée et correspondent à une
restauration intégrale. Les 25 références LCD/CRC restent inchangées.
Preuve : `luma_fx_20261004/bloom_validation.txt`.


### Version finale R2 / chargement r5

Le paquet conserve **3 245 216 octets**, CRC32 `9b074d80`, SHA-256
`f2251ce0526321d56190b40c27416fe399ec79095be0db196bc4ba567da288a8`.
Le programme occupe **27 128 octets** (texte 25 768, données 1 360), avec
3 032 octets de BSS et la réserve de pile du linker inchangée. SHA-256 :
`870897ac9e79eb53451d8d092ab2ee11e8fd16862675f282a47e50e97475c204`.

Le chargement complet des nouvelles ressources a pris **324,1 secondes**
(r4). Le téléchargement du programme optimisé seul a pris **3,7 secondes**
(r5), sans reset DDR ni reconfiguration FPGA. Les vérifications J-Link et
le CRC exécuté par l'AE350 passent, avec USB HS 480 Mbit/s. Le dossier
`sources.tar.gz` conserve les sources de la version finale et les manifestes
conservent leurs empreintes. La vidéo d'aperçu, calculée avant cette dernière
optimisation, reste exacte puisque les pixels n'ont pas changé.

Validation finale : **PASS, 25/25 poses**, puis **168.48 secondes**
d'animation et **9 242 images** (54.85 images/s,
contrôles USB compris). Départ en phase 7 070 : toutes les phases de la boucle
sont traversées, avec deux passages par l'agrandissement final.
Les **1056 octets d'écho binaire** sont exacts. Tous les compteurs
d'erreurs, sous-alimentations LCD (relatives et absolues), couches/sprites
invalides et commandes GPU rejetées restent à zéro.

Le maximum de composition vaut **789/2 556 cycles par ligne** (30.9 %).
Le temps maximal de préparation et d'attente des effets vaut **15.215 ms**,
mesuré par le compteur du **CPU 800 MHz** : ce ne sont pas des cycles GPU
à 75 MHz. Il reste environ 2.95 ms dans la période LCD de 18,17 ms.
Maximum de rechargement du cache de sprites : 6131 cycles. Les sollicitations
USB de diagnostic expliquent l'écart entre la cadence mesurée et les 55,04 Hz
nominaux du panneau ; aucun décrochage spécifique au grossissement ne subsiste
dans ce relevé.

Preuves : `luma_fx_20261004/check_r5/result.json`, `usb.txt`, `load_r4/`,
`load_r5/`, `host_validation.txt`, `bloom_validation.txt`, `preview/expected.json`.
Après les tests, la démo est relancée automatiquement à la phase 6 800 pour
montrer les cristaux puis le grand final. La confirmation visuelle utilisateur
consignée plus haut concerne R1 ; aucune confirmation visuelle R2 n'est encore
reçue. Le chargement de cette application reste volatile.
