# Qualification GPU V1 — 4 octobre 2026

**Statut : VALIDÉ sur Pro Dock dans `gpu_v1_r31`, le 4 octobre 2026.**
Les sept points passent simulations, timing, suite complète, USB HS et
30 minutes d'endurance ; l'utilisateur confirme les trois scènes.
Image SRAM : [`console_gpu_v1_800.fs`](../bitstreams/console_gpu_v1_800.fs),
[notice](../bitstreams/console_gpu_v1_800.md),
[bilan machine](gpu_v1_20261004/r31_validation.json).

Le journal ci-dessous conserve les étapes et échecs de qualification.
Référence antérieure validée : `gpu_perspective_r10`. R20 a passé le timing et
la régression historique sur carte, mais a révélé une inversion d'activations
de registres absorbés dans les DSP de copie ; il n'est pas une référence V1
validée. La protection de ces registres est vérifiée en synthèse et par un
modèle de primitive. R31 ferme maintenant le timing, passe deux rechargements
SRAM, les échos USB HS, la régression graphique complète et l'endurance.
Les étapes ci-dessous conservent les résultats de chaque
révision, y compris les échecs. Les sept points sont décrits dans
[GPU_V1.md](../ARCHI/GPU_V1.md).

## Simulations et hôte déjà passés

- Premier banc V1 : 554 commandes, 14 refus attendus, 24 528 fragments écrits,
  comparaison exacte des 3 Mio couleur/Z/texture et gardes. 11 619 succès de
  cache, 909 défauts. AHB 80 MHz et mémoire 75 MHz, attentes variables,
  lectures CPU et affichage concurrentes via le véritable arbitre DDR.
- Scènes partagées avec le firmware : 3 scènes × 4 positions ; tous les octets
  de mémoire et les gardes exacts face à un rasteriseur Python indépendant.
  Les commandes C sont produites sous UBSan, arrêt au premier comportement indéfini.
- API/conteneurs : 130 contrôles, tailles 1/13/256/512, formats RGB565 et
  ARGB4444, mipmaps jusqu'à 1 × 1, refus des en-têtes/dimensions/offsets erronés,
  calculs de géométrie aux limites sous UBSan. Filtrage alpha prémultiplié vérifié.
- Ancien 2D : 604 commandes exactes ; équivalence cycle par cycle sur
  2 081 517 cycles blitter et 2 081 518 cycles DMA, sans décalage ajouté.
- Composition native existante : 77 670 746 cycles du lecteur et
  77 670 748 cycles de l'arbitre identiques à `gpu_perspective_r10`.
- Composition 400 × 240 ×2, pas 832, HUD/sprites/tuiles natifs, changements
  atomiques et reprise après DDR bloquée : pixels exacts. Charge non surchargée
  maximale du banc 2433/2556 cycles par ligne. Retour au mode indexé vérifié.

Un essai volontairement plus chargé (4 couches de tuiles + **7** surfaces,
sprites et fond RGB) dépasse le budget de ligne. Il ne constitue pas une
configuration admissible : conserver cette limite explicite. La qualification
avec les **5** surfaces du banc de référence passe, sans masquer les erreurs.
Le test de surcharge historique reste également détecté.

## Contrôles complémentaires passés

- Dimensions maximales 1024 × 512, coins et dernières lignes : comparaison
  mémoire exacte. Le banc r3 ajoute l'alternance des trois moteurs dans le FIFO :
  **703 commandes**, 14 refus attendus, 25 106 fragments écrits, 75 151 écritures
  DDR dont 71 773 blocs complets ; 9553 succès et 824 défauts de cache.
- Non-régression raster : 785 commandes, 18 refus attendus, mémoire exacte.
- Après enregistrement de la sélection du moteur : équivalence de l'ancien
  rasteriseur sur 2 490 564 cycles, de l'arbitre sur 2 490 566 cycles, 359
  commandes de la référence L13–L15, sans changement de latence historique.
- Affichage natif 800 × 480 à pas 1664 : pixels exacts et retour au mode indexé.
  Première charge 16 surfaces + fond RGB : 2522/2556 cycles ; le maximum
  global ultérieur inclut la surcharge délibérément injectée par le banc.

## Premier routage, r1 : refus de chargement

1509 violations setup, aucune violation hold. Pire marge **−5,153 ns** ;
1502 violations dans le domaine GPU/DDR, 7 dans PHY_CLKOUT (TNS −0,410 ns).
Le bitstream produit par Gowin n'est pas qualifié et n'a pas été chargé.
Les contraintes d'horloge sont inchangées. Le contrôle de synthèse du scanout
ne trouve pas de DSP à registres de plusieurs horloges.

La correction r2 répartit le découpage des rectangles et évite les lectures
texture des fragments rejetés par le Z. La correction r3 localise le paquet
V1, enregistre la sélection du moteur et l'acquittement DDR (avec suppression
de toute seconde acceptation du même transfert), enregistre les fins de plages
et sépare la validation d'un plan de l'écriture de ses registres. Ces délais
supplémentaires concernent les nouveaux opcodes ; les cycles historiques sont
vérifiés par les bancs d'équivalence.

Les preuves sont dans `TESTS/gpu_v1_20261004/`. Les builds restent figés dans
leur propre dossier ; aucun build d'un autre projet n'est modifié.

## Compléments r3 et résultat r2

Le rendu vers une texture puis sa réutilisation est aussi vérifié : publication
par dessin, invalidation explicite après changement de cible, puis invalidation
automatique après une copie qui remplace les texels. Le banc étendu passe
**732 commandes**, 14 refus attendus, 31 250 fragments écrits, 15 283 succès
et 1238 défauts de cache ; les 3 Mio restent exacts. Les douze scènes passent
à nouveau sur le RTL r3.

r2 ne ferme pas le timing : 1151 violations setup, aucune hold ; pire marge
−6,162 ns, principalement validation des plans et de la copie. Cette image
n'a pas été chargée. r3 a été lancé pour isoler ces chemins de commande ;
son résultat figure dans la section ci-dessous.

Le complément r4 vérifie aussi les bits réservés d'en-tête : une description
TARGET/TEXTURE/MATERIAL/PLANE malformée invalide l'ancien état concerné.
**746 commandes, 22 refus attendus**, 31 250 fragments écrits et mémoire
exacte. Le même scénario passe avec des réponses mémoire dès le premier
cycle après acceptation, sous concurrence CPU/scanout et délais variables.
Le cache accepte ainsi une réponse arrivant avec l'acquittement enregistré,
sans perdre la première donnée. Les latences DDR habituelles restent testées.

Le pilote passe également UBSan sur un triangle d'aire −1 et à coordonnées
extrêmes : les gradients hors plage sont refusés avant le calcul de l'origine.
Le firmware contrôle les gardes toutes les 120 images et mesure l'intervalle
entre présentations réelles, y compris le temps des échanges USB de diagnostic.

## Routage r3 et interface DDR r5

r3 termine après 75 min 53 s de placement/routage : **775 violations setup**,
aucune hold. Domaines concernés : DDR 768 (TNS −1253,690 ns), bus 80 MHz 5
(−6,647 ns), LCD 2 (−2,398 ns). USB PHY_CLKOUT et sclk passent. Pire chemin
−4,527 ns, de la sélection V1 à l'adresse du contrôleur DDR ; 81,8 % du délai
de ce chemin provient du routage. Des retours DDR commandant les registres
larges du cache figurent également parmi les pires chemins. r3 n'est pas chargé.

Ressources r3 de l'ensemble : 66 689 éléments logiques, 43 248 registres,
242 BSRAM, 83 DSP, 8 PRIMARY. Le contrôle de synthèse du scanout passe.
Ces valeurs ne constituent pas les ressources d'une image V1 qualifiée.

Le build r4, lancé avec les derniers contrôles fonctionnels mais avant ce
résultat, est arrêté pendant le placement ; seul son `gw_sh` est ciblé après
vérification du PID et du répertoire. Les douze scènes r4 passent en simulation.

r5 ajoute un registre complet de transaction V1 avant l'arbitre et un registre
de réponse DDR, avec maintien jusqu'à acceptation et protection contre la
double capture. Les opcodes historiques gardent leur chemin et leurs cycles :
2 490 564 cycles raster et 2 490 566 cycles arbitre comparés à nouveau, exacts.
Les 746 commandes V1 passent aux deux latences mémoire. Gowin est configuré
pour dupliquer les ressources à fort fanout (`replicate_resources=1`, SUG1220
§3.2) ; aucune fréquence ni exception de timing n'est modifiée. Un fichier
annexe contient uniquement des requêtes de rapport par domaine, pour ne plus
masquer les chemins bus/LCD derrière les 25 pires chemins globaux.
Les douze scènes de référence passent à nouveau sur le RTL r5.

Le premier montage des requêtes de rapport dans un second SDC est refusé
par Gowin (TA2004 : horloges absentes de ce contexte), avant placement. r5 ne
produit donc pas d'image qualifiable. r6 conserve exactement ce RTL et
construit un seul SDC dérivé : préfixe binaire égal au fichier de production,
puis cinq commandes `report_timing`. Le fichier de production et son SHA-256
restent identiques, les deux fichiers sont archivés dans le manifeste ; aucun
changement de période, groupe d'horloges ou exception n'est ajouté.

r7 emploie le même RTL et le même firmware avec l'algorithme de placement 3,
en parallèle du placement par défaut de r6. La comparaison des sources ouvertes
et des parties ouvertes du résultat de synthèse est exacte ; les blocs chiffrés
générés par Gowin ne sont pas comparés octet à octet. Les entrées de génération
des IP sont identiques. Preuve : `r6_r7_design_identity.json`.

Le script d'endurance synchronise le début de chaque écho avec la boucle CPU :
il envoie les quatre octets commande/longueur/première donnée, attend ce premier
écho, puis envoie le reste. Cette séquence évite de saturer le petit FIFO UART
pendant un dessin. Le test logiciel de cette séquence couvre 64/512/4096 octets
et des lectures fragmentées. L'affichage continue pendant l'écho ; le CPU reprend
la préparation des images à la fin, et le compteur de temps inclut ce délai.

Le contrôle SDF des FIFO couvre maintenant aussi les 16 bits de pointeurs Gray
du FIFO de commandes GPU (`--gpu`). La borne commune est corrigée à **12,5 ns**,
période du domaine le plus rapide AHB 80 MHz, également pour le pont AHB/DDR
75 MHz (l'ancienne valeur 13,333 ns était moins conservatrice). Essai sur le
routage r3 : GPU ≤1,551 ns, pont CPU/DDR ≤1,312 ns, trace USB passive ≤1,470 ns.
Ces résultats ne qualifient pas r3, qui échoue au timing synchrone ; les trois
contrôles doivent être refaits sur le routage finalement chargé. Ils ne sont
pas une simulation de métastabilité ni une preuve de MTBF.

Le routage r7 est également refusé : après normalisation du nom de build
et de l'horodatage, son rapport de timing complet est **identique à r6**.
L'option de placement 3 est bien transmise dans `cmd.do`, mais n'a donc fourni
aucune diversité de résultat dans cet essai. Ce n'est pas une nouvelle preuve
indépendante de timing. Voir `r6_r7_timing_identity.json` ; r7 n'est pas chargé.

## Routage r6 et découpage des calculs r8

r6 termine en 52 min 59 s de placement/routage. Il reste **334 violations
setup, aucune hold** : 332 en DDR (TNS −508,692 ns), 2 en AHB 80 MHz
(TNS −1,675 ns). USB, sclk et LCD passent. Pire chemin −4,703 ns :
adressage de texture, de la hauteur à l'adresse DDR après limitation des
coordonnées, multiplication par le pas et additions. Les autres familles
critiques concernent le choix perspective/mipmap, les validations pilotant les
activations des registres de descripteurs et le découpage des copies.
**r6 n'est pas chargé.** Ressources : 66 701 éléments logiques,
44 736 registres, 242 BSRAM, 83 DSP, 8 PRIMARY.

r8 corrige ces familles dans les nouveaux moteurs, sans changer les opcodes
historiques : prédicats de validation enregistrés, choix des coordonnées séparé
du décalage de mipmap, coordonnées bornées puis multiplication et addition
d'adresse sur des étapes distinctes. Les coordonnées adressées occupent 9 bits,
suffisants pour les textures validées de 512 texels. Le découpage des spans et
celui des copies sont également enregistrés. Ces étapes ajoutent de la latence
au pipeline V1 ; les cadences doivent être mesurées sur la carte avant validation.
Les 746 commandes, 22 rejets attendus et les 3 Mio de mémoire comparée passent
avec les réponses DDR normales et anticipées ; les empreintes attendues ne
sont pas modifiées. Les douze poses passent aussi à nouveau, avec des empreintes identiques aux
versions précédentes. Compilations complètes `gpu_v1_r8` (placement par défaut)
et `gpu_v1_r9` (placement 3) lancées sur le même RTL corrigé ; résultats ci-dessous.

## Routage r9 et contrôle des transactions r10

r9 termine le placement/routage en 28 min 25 s : **103 violations setup,
aucune hold**. DDR : 92, TNS −70,663 ns ; USB PHY_CLKOUT : 11,
TNS −5,636 ns. Bus 80 MHz, LCD et sclk passent. Le pire chemin (−3,561 ns)
part du sélecteur V1, chargé par 315 consommateurs, passe par WRITE et
l'acquittement DDR, puis revient à l'état de l'ancien rasteriseur. Les
anciens chemins internes des triangles présentent aussi quelques marges
négatives, jusqu'à −1,166 ns. r9 n'est pas chargé. Ressources : 66 534
éléments logiques, 44 957 registres, 242 BSRAM, 83 DSP et 8 PRIMARY.

r10 conserve la file ordonnée et son propriétaire pour les données, mais
forme VALID/WRITE à partir des demandes enregistrées des trois moteurs
mutuellement exclusifs. READY arrive directement aux anciens moteurs,
qui ne le consomment que dans leurs états d'émission. Le sélecteur du
large bus de données sort ainsi de la boucle WRITE → arbitre → état.
Le registre de transaction V1 conserve son acquittement et sa protection
contre les doubles captures. Les retours de lecture restent aiguillés.
Le test `test_gpu_accel_equivalence.py` compare le parent complet à celui
figé dans r8, y compris les réponses AHB et chaque transaction DDR valide ;
il vérifie qu'aucune demande de deux moteurs ne se chevauche.

| Séquence | Commandes | Cycles AHB comparés | Cycles DDR comparés | Transactions |
|---|---:|---:|---:|---:|
| Indexée/affine | 604 | 2 220 065 | 2 081 517 | 122 223 |
| Ancien RGB565 | 359 | 2 656 338 | 2 490 564 | 102 487 |
| Mixte V1 et anciens opcodes | 746 | 1 227 339 | 1 150 743 | 87 020 |

Les trois séquences passent, ainsi que les pixels/gardes indépendants et
les douze poses. Les payloads d'un cycle VALID=0 ne sont pas comparés,
car leur valeur n'appartient pas au protocole ; VALID et les transactions
valides sont comparés à chaque cycle. Les simulations vérifient le chemin
physique fonctionnel modifié, pas seulement un moteur recevant des entrées
communes.

Deux petits chemins V1 sont également raccourcis : le test Z utilise
l'étape LOD existante pour enregistrer sa décision, et le décaleur de sortie
de copie est calculé à chaque cycle, supprimant son activation large par
l'état. Ces changements n'ajoutent aucun cycle par rapport à r8/r9.

Le pire chemin USB r9 contient un fil de **5,461 ns** entre le multiplexeur
RXACTIVE à R17C171 et le contrôleur à R7C126. r10 place uniquement ce
multiplexeur à R12C148, entre les deux groupes. Les netlists fournisseur,
la négociation HS, les périodes et les exceptions de timing ne sont pas
modifiées. Ce placement reste à qualifier ; le brochage ne change pas.
Compilation complète r10 lancée avec l'algorithme de placement 3 ; résultat ci-dessous.

La variante r11 conserve exactement le RTL, le firmware, les périodes et les
placements explicites de r10. Elle désactive uniquement la duplication
automatique des registres par Gowin (`replicate_resources=0`, placement 3),
pour mesurer son effet sur la congestion et les marges routées. Cette option
est désormais un argument explicite de `build_gpu.py`, enregistré dans
`build_options.json` ; la valeur par défaut reste 1. Aucun résultat physique
ne peut être déduit des simulations communes à ces deux variantes.

r12 explore l'algorithme de placement 1, avec duplication automatique activée
(valeur par défaut), sur le même RTL que r10/r11. Son dossier est indépendant
des autres compilations, y compris celles des autres projets. Les options de
placement ne modifient ni les fréquences demandées ni le contrat fonctionnel.

## Routage r11 et corrections locales r13

r11 termine le placement/routage en **18 min 44 s**. Il reste **37 violations
setup et aucune hold** : 36 DDR (TNS −9,552 ns) et une AHB (−0,015 ns).
Toutes les horloges USB et le LCD passent. Ressources : 65 355 éléments
logiques, 43 755 registres, 242 BSRAM, 83 DSP, 8 PRIMARY. Le contrôle de
synthèse du scanout passe. r11 n'est pas chargé.

Les pires chemins DDR observés sont :

- −1,227 ns : comparaison de rectangle vide vers le registre Y absorbé dans
  l'entrée du DSP de calcul de plan ;
- −1,067 ns : validation des mots de commande vers l'état du rasteriseur
  historique ;
- −0,614 ns : lecture BSRAM de composition, avec un fil de 7,212 ns ;
- −0,339 ns : validation d'une copie vers l'activation de ses bornes.

r13 garde le placement 3 sans duplication automatique, et corrige les trois
chemins logiques sans ajouter de cycle. Les bornes privées des copies et des
rectangles sont enregistrées même si le descripteur est vide/invalide ; seul
l'état décide ensuite si une opération mémoire est autorisée. Le Y suivant
est calculé à la fin d'une ligne même si elle était la dernière. Ces valeurs
inutilisées ne peuvent pas émettre de transaction DDR. Le rasteriseur
historique prédécode la validité des mots pendant le cycle déjà disponible
entre la fin de lecture de la commande par le blitter et START.

`test_gpu_accel_equivalence.py --reference-video` compare désormais aussi
les neuf modules vidéo enfants à leurs versions figées dans r11, avec leurs
propres états et registres. Le banc vérifie à chaque START que la commande
était déjà stable au cycle précédent. PASS sur les 746 commandes mixtes V1
et les 359 commandes de régression RGB565 : respectivement **1 150 743** et
**2 490 564 cycles DDR identiques**, ainsi que les réponses AHB, transactions,
pixels et gardes. La séquence étendue de perspective passe aussi : 785 commandes, 18 rejets
attendus, 4 870 499 cycles AHB et 4 566 547 cycles DDR identiques,
181 665 transactions. Le test DDR à réponse anticipée passe également. Preuves :
`gpu_v1_20261004/r13_*_full_equivalence.{json,log}`. Le RTL du lecteur de
composition et le SDC ne sont pas modifiés ; les marges de ces chemins
restent à contrôler dans le nouveau routage.
Les bancs générés, modèles de référence, vecteurs, sources ouvertes et
outil de comparaison sont conservés dans
`gpu_v1_20261004/r13_full_equivalence_sources.tar.gz` avec son SHA-256.

## Routage r13 et décodage du rasteriseur r14

r13 termine son placement/routage en **21 min 54 s**, avec 109 violations
setup et aucune hold. L'USB, le LCD et les chemins V1 précédemment corrigés
passent. DDR : 108 endpoints, TNS −81,954 ns ; AHB : un endpoint, −0,311 ns.
Ressources : 65 378 éléments logiques, 43 760 registres, 242 BSRAM, 83 DSP.
Le contrôle de synthèse du scanout passe. r13 n'est pas chargé.

107 chemins négatifs partent du même bit d'état TEX_COPY de l'ancien
rasteriseur, jusqu'à −1,369 ns. Ce bit, chargé par 291 consommateurs, traverse
le décodage prioritaire d'états pourtant exclusifs et active notamment les
quatre interpolateurs U/V/Z/Q. r14 isole leurs deux activations effectives
(SPAN2 et PIX_STORE) dans un bloc séquentiel indépendant. Il indique aussi
`parallel_case` pour les états one-hot, comme le générateur de triangles
existant. Une assertion dans le banc vérifie l'état one-hot à chaque cycle.

Le dernier chemin triangle r13 vaut −0,244 ns. Le test d'intersection des
bornes utilise désormais l'identité `max(gauches) <= min(droites)` équivalente
à toutes les comparaisons `gauche[i] <= droite[j]`, calculées en parallèle.
Les min/max servant à la position et à la largeur du span sont conservés.
Aucun cycle n'est ajouté et le générateur reste commun aux trois moteurs.

Enfin, l'activation AHB de `m_hready` était fixée près du CPU, à R3C153,
alors que son entrée vidéo arrivait de R29C37 : 5,070 ns sur ce seul fil,
puis 0,966 ns vers le registre. La même LUT, identifiée par son rôle dans
la netlist, est placée à R18C112 pour équilibrer ces distances. Il s'agit
uniquement d'un déplacement CST ; le SDC reste identique.

Les comparaisons complètes à l'instantané r13 passent avec les contrôles de
pixels/gardes : 604 commandes indexées (2 081 517 cycles DDR), 785 commandes
perspective (4 566 547 cycles) et 746 commandes mixtes V1 (1 150 743 cycles).
Le test de stabilité avant START et l'assertion one-hot passent. Preuves et
sources des bancs : `gpu_v1_20261004/r14_*_full_equivalence.*` et
`r14_full_equivalence_sources.tar.gz` avec SHA-256. Build r14 : placement 3,
duplication automatique désactivée ; résultat de timing ci-dessous.

## Résultat tardif du placement r8

Le placement par défaut r8 termine après **2 h 36 min 25 s**, avec
**618 violations setup et aucune hold** : DDR 602 (TNS −753,081 ns),
AHB 15 (−14,317 ns), sclk USB 1 (−1,166 ns). Pire chemin DDR : −5,813 ns.
Ses ressources sont 66 529 éléments logiques, 44 957 registres, 242 BSRAM,
83 DSP. Cette variante n'est pas chargée. Son RTL était identique à r9,
mais son placement est nettement moins favorable ; le temps de routage
ne constitue donc pas un indicateur de qualité du résultat.

## Routage r14 et sélection texture r15

r14 termine le placement/routage en **18 min 3 s**. Tous les domaines sauf
DDR passent, notamment AHB, sclk, PHY_CLKOUT et LCD. Il reste 45 endpoints
setup DDR (TNS −14,440 ns), aucun hold. Les 45 chemins partent tous du bit
perspective `flags[4]` et finissent sur les adresses BSRAM de l'ancienne
texture, avec une marge minimale de −0,830 ns. Les trois groupes corrigés
pour r14 ne sont plus négatifs. Ressources : 65 661 éléments logiques,
43 760 registres, 242 BSRAM, 83 DSP. r14 n'est pas chargé.

r15 conserve les mêmes cycles et décode séparément les coordonnées affines
et les deux échantillons perspective : test de limites, répétition/limitation
et adresse 7 bits par axe. Le choix du mode et de l'échantillon se fait ensuite
sur les résultats courts, au lieu de précéder la comparaison 49 bits.
Il n'ajoute aucun étage ni aucune requête mémoire.

Les comparaisons au parent et aux neuf modules vidéo figés de r14 passent :
785 commandes de perspective, 4 566 547 cycles DDR identiques ; 746 commandes
mixtes V1, 1 150 743 cycles identiques. Les réponses AHB, pixels, profondeur,
gardes mémoire et assertions passent également. Preuves et sources :
`gpu_v1_20261004/r15_*_full_equivalence.*` et archive
`r15_full_equivalence_sources.tar.gz` accompagnée de son SHA-256.
La première compilation de simulation a repéré un identifiant réservé
SystemVerilog (`inside`), renommé `in_bounds` avant ces tests et le build FPGA.
Le firmware, la V1, le générateur de triangles, le scanout, le CST et le SDC
sont inchangés par rapport à r14. r15 utilise placement 3 sans duplication.
La variante r16 conserve ce même RTL et désactive également la duplication,
mais utilise l'algorithme de placement 4. Elle est compilée dans un dossier
indépendant, sans relancer ni modifier les routages déjà actifs.

## Résultats r10/r15 et prédécodage du blitter r17

r10 échoue au routage après **2 h 30 min 21 s** avec 65 connexions non
routées (PR0004). Aucun bitstream de cette variante n'est qualifié.

r15 termine en **24 min 19 s** de placement/routage : 95 violations setup,
aucune hold. DDR : 93, TNS −89,185 ns ; PHY_CLKOUT : 2, TNS −3,835 ns.
AHB, sclk et LCD passent. Les chemins d'adresse texture corrigés passent.
Ressources : 65 702 éléments logiques, 43 760 registres, 242 BSRAM, 83 DSP.
r15 n'est pas chargé.

Le principal groupe DDR part du bit 6 de l'opcode du blitter : 76 endpoints,
pire marge −2,363 ns, en passant par le décodage de classe puis les activations
des registres de préparation. Les autres groupes concernent READY/init DDR,
le lancement d'un diviseur de triangle et un test Z. Le chemin USB négatif
part du reset du contrôleur vers deux bascules sur front descendant du PHY ;
il comprend 5,212 ns de trajet vers le reset applicatif, puis 3,434 ns vers
le PHY. Aucune netlist fournisseur ni logique de reset USB n'est modifiée.
La variante de placement r16 est déjà lancée sur ce RTL.

r17 enregistre six classes exclusives de commandes pendant la lecture des
sept derniers mots, avant SETUP. La classification ne traverse donc plus le
chemin des activations de préparation. L'opcode brut, le protocole et les
cycles restent inchangés. Le banc vérifie aussi que les classes ne se
chevauchent jamais. Comparaison au parent et aux neuf modules vidéo r15 :
PASS sur 604 commandes indexées, 785 perspective et 746 mixtes V1, soit
7 798 807 cycles DDR identiques, avec réponses AHB, pixels et gardes exacts.
Preuves : `gpu_v1_20261004/r17_*_full_equivalence.*`, archive de sources avec
SHA-256. Le commentaire sur le nombre de mots lus a été précisé après les
tests ; aucun texte Verilog exécutable n'a changé avant le build r17.
Placement 3, duplication désactivée ; le reste du RTL et des contraintes est
identique à r15/r16.

r16 (même RTL que r15, placement 4) termine en **13 min 7 s** avec
331 violations setup et aucune hold : DDR 268, TNS −209,017 ns ; sclk 50,
TNS −57,134 ns ; PHY_CLKOUT 13, TNS −9,182 ns. AHB et LCD passent.
Les chemins négatifs incluent l'arbitrage DDR, les retours de lecture et
des trajets internes USB. Ce placement est moins favorable et n'est pas
chargé. Ressources : 65 699 éléments logiques, 43 760 registres, 242 BSRAM,
83 DSP. Le routage r17 reste indépendant et conserve le placement 3.

r17 termine avec **23 violations setup, aucune hold** : DDR 22,
TNS −27,582 ns ; sclk 1, TNS −0,030 ns. AHB, PHY_CLKOUT et LCD passent.
Les chemins de décodage corrigés passent. Les groupes DDR restants sont :
sortie BSRAM du lecteur de lignes vers l'alignement (3, pire −1,845 ns),
comparaison de fin de copie vers le compteur de ligne (18, −1,728 ns),
longueur de segment indexé (1, −0,103 ns). Le chemin sclk est interne au
PHY fournisseur, laissé inchangé. Ressources : 65 704 éléments logiques,
43 766 registres, 242 BSRAM, 83 DSP. r17 n'est pas chargé.
Les groupes et empreintes des rapports r14 à r17 sont archivés dans
`gpu_v1_20261004/r*_timing_failure.json`.

r18 conserve les cycles et prépare trois corrections : test de dernière
ligne de copie enregistré pendant le transfert, répartition du décalage de
pixels sur les deux registres existants (1 bit puis 4 bits, après sélection
de banque), calcul direct de dépassement de segment à la place d'une
soustraction suivie d'une comparaison. Les 1 048 576 combinaisons de longueur
restante (0..2047) et d'offset (0..511) donnent exactement la même longueur.
Les comparaisons complètes des accélérateurs et du lecteur sont relancées
avant compilation. Aucun changement au CST, au SDC ou aux IP fournisseur.

Ces quatre comparaisons r18 passent : 604 commandes indexées, 785 perspective,
746 mixtes V1 (7 798 807 cycles DDR identiques) et 77 670 746 cycles du lecteur
de lignes (arbitre : 77 670 748). Pixels, gardes, réponses AHB, transactions
DDR et cadences sont inchangés. Les 16 surfaces avec RGB565 conservent leur
maximum de 2 522/2 556 cycles ; la surcharge volontaire est toujours signalée.
Preuves et sources : `gpu_v1_20261004/r18_*equivalence.*` et
`r18_full_equivalence_sources.tar.gz` avec SHA-256.
r18 est lancé le 4 octobre à 14:24 UTC, placement 3 sans duplication.
r19 utilise les mêmes corrections avec le placement 2, sans duplication,
dans un stage indépendant. Il est lancé à 14:26 UTC pour comparer les deux
dispositions physiques sans modifier les compilations en cours.

## Résultats r18/r19 et tampon DDR r20

r19 termine en 10 min 19 s de placement/routage, avec 112 violations setup,
aucune hold : DDR 79/TNS −22,296 ns, sclk 27/−12,227 ns, PHY_CLKOUT
5/−1,841 ns, AHB 1/−0,433 ns. Ce placement est écarté.

r18 termine en 14 min 20 s de placement/routage. USB, AHB et LCD passent,
ainsi que les trois groupes corrigés. Il reste 92 violations setup DDR,
aucune hold, TNS −110,394 ns. 91 chemins partent du compteur de FIFO
d'événements vers le tampon CPU de l'arbitre DDR (pire −3,568 ns) : le
signal de requête tardif active un large groupe de registres de données.
Un autre chemin relie la requête de tuiles à l'état du rasteriseur
(−0,066 ns). Aucun de ces deux builds n'est chargé. r18 utilise 65 829
éléments logiques, 43 783 registres, 242 BSRAM, 83 DSP.

r20 échantillonne les 320 bits de commande/adresse/données/masque du port CPU
tant que son tampon est vide. Le cycle d'acceptation capture les mêmes
valeurs ; le tampon plein les conserve jusqu'à leur consommation. La requête
tardive ne commande plus que le bit de présence. Le reset, la priorité,
READY et les cycles d'acceptation restent inchangés.

Le moniteur compare toujours tous les contrôles à chaque cycle, et les
adresses/commandes lorsque `m_en=1`, les données/masques lorsque
`m_wr_en=1`. Les charges utiles non validées peuvent désormais changer dans
le tampon vide ; elles ne sont pas consommées par le contrôleur DDR.
Le banc ciblé fait varier les données et masques CPU indépendamment, les
mémorise à l'acceptation et les compare à l'émission sous blocages :
5 128 lectures, 916 écritures, 2 491 opérations CPU, 10 022 cycles
identiques à r18. Le test V1 à réponse minimale d'un cycle passe également
sur 746 commandes, 22 rejets attendus et 31 250 pixels ombrés exacts.
La comparaison complète lecteur/arbitre passe aussi : 77 670 746/77 670 748
cycles identiques, 1 729 862 lectures CPU concurrentes, maximum conservé de
2 522/2 556 cycles par ligne. Les journaux et sources sont archivés sous
`gpu_v1_20261004/r20_*`, notamment le banc à données d'écriture variables.
r20 est lancé à 14:48 UTC avec placement 3 et duplication désactivée.
r21 reprend ce RTL et ce placement avec l'algorithme de routage 2 au lieu
de 1. `tools/build_gpu.py --route-option` expose les trois choix documentés
par Gowin (SUG1220, section 3.2, page 30), conserve 1 par défaut et archive
la valeur dans `build_options.json`. Seule cette option varie ; aucune
période, exception de timing ou source d'IP ne change. Le parseur et la
syntaxe Python ont été vérifiés avant le lancement.

## Timing fermé : r20

**r20 passe tous les contrôles setup et hold**, sans changement des horloges
ni du SDC de production. Placement/routage : 13 min 55 s. Minimum des
1 085 chemins détaillés : +0,138 ns (tous types confondus). Minima setup
rapportés : DDR/GPU 75 MHz +0,344 ns ; AHB 80 MHz +0,240 ns ; LCD 35 MHz
+14,725 ns ; PHY_CLKOUT 60 MHz +1,658 ns ; sclk 120 MHz +0,160 ns.
Ressources : 65 829/138 240 éléments logiques, 43 783/139 140 registres,
242/340 BSRAM, 83/298 DSP, 8/8 horloges PRIMARY.

SHA-256 du bitstream :
`a8dbddb61baf92d204052d89056c8967768285b19056aaea724a5fad3bd35f17`.
Les 118 fichiers du manifeste sont vérifiés. L'audit de synthèse du scanout
passe : aucun DSP avec absorption de registres d'horloges différentes.
Les bornes routées Gray passent sur 12 bits AHB/DDR (max 1,065 ns), 16 bits
de FIFO de commandes GPU (1,611 ns) et 18 bits de trace USB (1,245 ns),
pour une limite conservatrice de 12,5 ns. Ces mesures SDF ne constituent
pas une preuve analogique de métastabilité/MTBF, ni un audit de tous les CDC.
Preuves : `r20.tr`, `r20_timing.json`, `r20_resources.txt`,
`r20_scanout_synthesis.json`, `r20_*_gray_sdf.json`.

La variante r21 (route 2) est écartée : 21 violations setup (DDR 2,
AHB 16, sclk 3), aucune hold. Aucun changement AHB ou USB supplémentaire
n'est requis pour r20, qui passe avec route 1.

Les deux chargements SRAM r20 passent, avec réénumération USB HS 480 et
20 échanges exacts après chacun. La suite historique G0–G6, FAST, L11–L15,
perspective et composition passe. **La première scène V1 échoue**, donc r20
n'est pas une image validée pour V1 et l'endurance n'a pas été lancée.

## Défaut de copie après synthèse et correction r22

Lecture J-Link de la mémoire après l'échec : seuls les **400 pixels** du
rectangle copié `(364,198)..(383,217)` diffèrent. Tous les autres pixels et
le tampon Z sont exacts. Les 772 778 octets initialisés des textures, mips
et polices sont identiques à la référence. Trois copies entre pages distinctes
injectées au repos sont rejetées à tort, alors que la copie dans la même page
est acceptée avec une mauvaise adresse source. Les huit commandes de la sonde
sont bien comptées. Les captures et comparaisons sont dans
`gpu_v1_20261004/debug_r20/`; régression dans `board_r20/`.

La netlist du module ouvert `gpu_copy565` révèle deux DSP (`n421_s1` pour
la fin de plage, `n2748_s0` pour l'adresse source) ayant absorbé le registre
word1 du blitter puis le registre du paquet V1. Leurs enables sont inversés :
`C_IREG` est activé à la capture V1, `C_PREG` à la capture word1 antérieure.
Avec l'adresse 0x00800000, le modèle officiel MULTALU27X18 calcule ainsi
0x00030c00 au lieu de 0x00830c00. Cela explique les fausses détections de
chevauchement et les lectures depuis une mauvaise page.

`TESTS/test_gpu_copy_dsp.py` reproduit 64 erreurs avec les paramètres figés
r20 et vérifie 64 résultats exacts avec le registre de paquet conservé dans
la logique. Il utilise sans modification le modèle officiel local
`gw5a/prim_sim.v`; il ne constitue pas une équivalence complète de la netlist.
Le correctif r22 protège uniquement `gpu_v1.packet_base` (32 bits) avec
`syn_preserve=1`, conformément à SUG550-2.1E §4.3 et §5.12. Les autres mots
du paquet restent optimisables. L'ABI et les cycles RTL sont inchangés.

Le garde-fou `tools/check_gpu_copy_synthesis.py` rejette les doubles pipelines
C à enables distincts dans le copieur ; il rejette correctement les deux DSP
r20. Les futurs builds GPU exécutent ce contrôle, en plus du contrôle scanout.
Pour r22 déjà lancé, le même audit est exécuté séparément.

Les 746 commandes de limites V1 passent à réponse DDR minimale d'un cycle :
22 refus attendus, 31 250 fragments et 3 MiB de mémoire/guards exacts.
Les 12 poses des trois scènes passent également la comparaison RTL intégrale.
Le r22 est écarté avant chargement : l'audit élargi à `gpu_v1` détecte
encore le DSP de `z_end` (`n1435_s`). Il capture le registre de paquet puis
`z_base` avec les enables inversés (capture paquet / décodage TARGET).
La scène conserve habituellement le même Z et ne couvre donc pas ce cas.

Le r23 protège **tout le registre packet de 256 bits**, sans changement de
cycles RTL. Le garde-fou vérifie maintenant `gpu_copy565` et `gpu_v1`.
Le firmware ajoute `V1 MEMORY PASS` : déplacement du Z d'au-dessus à
au-dessous de la page couleur, copie entre pages avec lanes distinctes,
effacement Z partiel, comparaison intégrale des 2 496 octets comprenant
les pixels, paddings et gardes des trois surfaces. Ce test est exigé avant
les 12 poses et avant/après l'endurance. ITCM : 63 832 octets.
Le banc RTL ajoute également ces cinq commandes (751 au total).
Le résultat de timing r23 figure dans la section suivante.

Le r12 ancien s'est terminé avec 16 nets non routés. Il n'a jamais été chargé.

## Timing r23 et diviseur r24

Le r23 finit avec seulement **deux violations setup DDR**, de -0,304 et
-0,105 ns : `dx[2]` → addition du prochain Q → test Q>0 dans les deux
diviseurs de perspective V1. Toutes les autres horloges et tous les hold
passent. Il n'est pas chargé. R22 avait 31 violations setup et n'est pas chargé.

R24 capture le signe de Q au démarrage puis teste le dénominateur enregistré
contre zéro dans l'étape ABS existante. L'étape SETUP voit la même condition
Q>0. **Aucune latence ajoutée** et aucun changement des résultats, y compris
Q nul/négatif. Le banc compare chaque cycle de sortie au diviseur r23 et
vérifie 2 252 paires rationnelles contre Python : PASS, latence maximale 28 cycles.
L'équivalence de l'accélérateur et tous ses enfants passe sur 751 commandes,
1 227 822 cycles AHB, 1 151 196 cycles DDR, 87 052 transactions ; la totalité
des pages et gardes reste exacte. Preuves : `r24_divider.log`,
`r24_v1_equivalence.*`, archive `r24_divider_equivalence_sources.tar.gz` et SHA.

## Timing r24 et pont AHB r25

Le r24 passe tous les chemins GPU/DDR et USB. Il reste six violations setup
sur le pont EXTS AHB, de -0,161 à -0,070 ns, sans violation hold. Le chemin
fait l'aller-retour `m_hready` → bloc dur AE350/HSEL → enables de capture
adresse. R24 n'est pas chargé.

R25 capture les champs privés adresse/écriture/cible lorsque le pont est
IDLE. La condition d'acceptation (HSEL, HTRANS et HREADY) reste identique
et est seule à faire passer en DATA. Un échantillon non sélectionné ne
peut donc pas être émis. Le retour HSEL ne commande plus les 34 enables
de données. Les registres de retour HREADY/HRDATA et la latence ne changent pas.

`TESTS/test_ahb_exts_bridge_equivalence.py` compare tous les bits des sorties
à chaque cycle au pont r24 : **250 000 cycles**, 23 629 requêtes acceptées,
23 607 émises et 22 annulées par reset avant émission, toutes exactes.
Le banc contrôle aussi indépendamment adresse, cible et données émises et
l'absence de requête sans acceptation, avec attentes des deux esclaves.
Preuves : `r25_ahb_bridge.*`, archive du banc/sources et empreinte SHA.
Le r25 finit avec une seule violation setup AHB (-0,350 ns), du signal
`guarded_write` vidéo au CE de `m_hready`, et aucun hold. Les chemins de
capture adresse corrigés passent ; GPU/DDR, USB et LCD passent également.
R25 n’est pas chargé. R26 essaie route 2 sur le même RTL et le même firmware,
sans changement des horloges ni des exceptions de timing.

## Retour HREADY complet — r27/r28

R26 échoue avec un setup AHB à -2,257 ns sur le même registre de retour
HREADY, et trois DDR à -0,519/-0,134/-0,067 ns. Aucun hold ; non chargé.

R27 donne une expression complète de la prochaine valeur HREADY à chaque
cycle : vrai pour un IDLE sans demande acceptée ou un WAIT dont l'esclave
est prêt. Cela supprime le maintien implicite et le long décodage vers le CE
de ce registre de retour. L'ancien placement forcé du LUT CE est supprimé
car ce chemin n'est plus celui du RTL ; le SDC reste inchangé.
L'équivalence avec le pont r24 d'origine repasse sur 250 000 cycles, avec
les mêmes 23 629 acceptations, 23 607 émissions et 22 annulations par reset.
R27 utilise route 1 ; R28 route 2 du même RTL/firmware, placement 3 et
réplication désactivée. Les deux sont lancés ensemble ; leurs échecs de
timing sont détaillés ci-dessous. La netlist r27
confirme un `DFFSE m_hready_s0` dont CE est relié à VCC : plus de décodage
combinatoire sur cette activation. Preuve : `r27_ready_synthesis.json`.

## Boucle AHB près du cœur — r29/r30

R27 ne présente plus de violation GPU/DDR, mais conserve un setup AHB
à -0,407 ns et un setup PHY sclk à -0,031 ns. R28 présente 16 setups
(14 DDR, un AHB, un sclk). Aucun hold ; aucune de ces variantes n'est chargée.

Le chemin AHB r27 relie HREADY en R15C73 au cœur en R0C160, puis HSEL
au registre d'état en R31C36 : 10,728 ns de liaisons. R29 rapproche les
registres HREADY et les deux bits d'état en R4C150. Le test HREADY dans
IDLE est supprimé car HREADY y est toujours vrai pour tout état atteignable
(après reset ou fin de WAIT). La comparaison au pont original r24 repasse
sur les mêmes 250 000 cycles et le même comptage des transactions.
R29 utilise placement 3/route 1, R30 placement 2/route 1, sans duplication.
Les horloges et le SDC sont inchangés.

R29/R30 sont arrêtés avant placement : le bit d'état 1 est nommé `st_1_s5`
après optimisation, et non `st_1_s0`. La contrainte est corrigée selon la
netlist ; R31/R32 reprennent respectivement les placements 3/2 avec le même
RTL et le même firmware. Aucune variante r29/r30 n'est chargée.

## Qualification matérielle finale — R31

### Timing, ressources et sources

R31 termine le 4 octobre à 21:19 CEST avec **zéro violation setup/hold**
sur toutes les horloges, 1 085 chemins détaillés et une marge minimale globale
de +0,140 ns. Les pires setups GPU/DDR et AHB sont respectivement +0,706 et
+1,524 ns. Le SDC conserve son empreinte et les fréquences 800/80/75/35 MHz.

Ensemble FPGA : 65 812/138 240 éléments logiques, 43 754/139 140 registres,
242/340 BSRAM, 83/298 DSP et 8/8 PRIMARY. Le scanout et les deux modules
d'adressage passent les garde-fous de synthèse. Les 119 sources figées et
l'image sont vérifiées. SHA-256 de l'image :
`60806fa2e988641e5b67ddcc5b13873c5b39c87621d5f1a23bbcf5e80b6d6aee`.

Les trajets des pointeurs Gray SDF passent : 12 bits AHB/DDR, maximum
1,060 ns ; 16 bits FIFO GPU, maximum 1,416 ns ; 18 bits trace USB, maximum
1,546 ns, tous sous la borne 12,5 ns. Ces contrôles ne constituent pas une
preuve de MTBF. Ces contrôles sont complétés par les essais matériels
ci-dessous, réalisés sur l'image de même empreinte transférée sur ax15.

R32 (placement 2) finit ensuite avec 567 violations setup : 342 DDR,
158 PHY_CLKOUT, 64 sclk et 3 AHB, pire marge -5,907 ns ; aucun hold.
Cette variante n'est pas chargée. La qualification conserve R31, placement 3.

### Rechargements, suite complète et endurance

La suite complète R31 passe sur la Pro Dock : G0–G6/FAST/L11–L15,
perspective/composition, test mémoire V1, douze poses couleur/Z/LCD, mesure
du changement de résolution, 720 images V1 et retour au mode indexé. Les
deux rechargements produisent chacun une nouvelle énumération à 480 Mbit/s,
avec 20 séries d'échos, soit 217 640 octets binaires exacts au total.
Preuves : `board_r31/result.json`, `board_r31/gpu.log` et `r31_board_metrics.json`.
Le 4 octobre, l'utilisateur confirme : **« Oui, les trois scènes sont correctes »**,
à la question portant sur aventure, couloir et route ainsi que la stabilité
du bandeau natif, sans lignes manquantes ni déchirure.
L'endurance se termine avec **PASS**, après **1 802,141 secondes** :

- **58 680 images**, 489 fenêtres de 120 images ; 19 560 images de chaque scène.
- **191 552 octets d'écho USB exacts** pendant l'animation, blocs de
  64/512/4096 octets, configuration HS 480 inchangée et aucune réénumération.
- Zéro underflow LCD, zéro refus de commande, gardes mémoire intactes.
- Dessin maximal **30,534 ms**, composition maximale **504/2556 cycles par ligne**.
- Douze empreintes couleur/Z/LCD, test mémoire, changement de résolution,
  six fenêtres d'animation et retour indexé revérifiés après l'endurance.
- Trois scènes laissées en animation après la fin du test.

Le plus long intervalle de présentation atteint **381,522 ms** pendant
le traitement d'un écho par la boucle CPU/UART à 115200 bauds. Ce délai de
diagnostic est inclus dans les mesures, sans le confondre avec le temps de
dessin GPU. Le LCD continue son rafraîchissement. Hors ces échos, la suite
complète mesure 27,40–27,51 images/s pour l'aventure, 27,40 pour le couloir,
54,58 pour la route. Le comparatif de résolution passe de 102,228 ms à
28,464 ms en 400 × 240, facteur 3,59.

Preuves : `endurance_r31/result.json`, `endurance_r31.log`, scripts exacts
copiés dans les dossiers de tests et `r31_validation.json`. Le bilan de
qualification vérifie à nouveau les empreintes du bitstream, des 119 sources,
des scripts et du contenu de `r31_sources.tar.gz`. Les 52 fichiers de travail
vidéo, ponts modifiés, firmware et outils comparés restent identiques à R31
(`r31_working_sources_check.json`).

- [x] Timing setup/hold à fréquences inchangées ; ressources ; analyse de synthèse
  du scanout ; provenance et empreintes des sources figées.
- [x] Chargements SRAM répétés, énumération USB HS 480, stress USB et suite GPU
  complète sur la Pro Dock FTDI 2023112818 raccordée à ax15.
- [x] Vérification des 12 poses, cadence et compteurs en animation ; confirmation visuelle.
- [x] Endurance de 30 minutes puis nouvelle vérification des empreintes.
- [x] Archivage `.fs` validé, SHA-256, sources et journaux. La confirmation
  visuelle de l'utilisateur est consignée séparément des comparaisons automatiques.

## Reproduction

Build complet, dans un nom de dossier encore inutilisé :

```sh
python3 tools/build_gpu.py --name gpu_v1_rN \
  --usb-controller gowin-high --usb-controller-ide /home/michael/gowin/IDE \
  --usb-controller-system-freetype \
  --usb-phy gowin --usb-phy-ide /home/michael/gowin/IDE \
  --usb-phy-system-freetype --usb-phy-rx-mode advance
```

**Options de R31 : ajouter `--place-option 3 --replicate-resources 0`.**
Route 1, par défaut. R32 remplace uniquement le placement par 2 et échoue
au timing ; ne pas le substituer à l'image R31 retenue.

Pour reproduire r7, r9 ou r10, ajouter `--place-option 3` ; r11 ajoute aussi
`--replicate-resources 0`, comme r13/r14/r15/r17. r6 et r8 utilisent le placement par défaut.
Pour r12, ajouter `--place-option 1`.
Pour r16, ajouter `--place-option 4 --replicate-resources 0`.
Pour r18, ajouter `--place-option 3 --replicate-resources 0` ; pour r19,
`--place-option 2 --replicate-resources 0`.
Pour r20, `--place-option 3 --replicate-resources 0` ; pour r21, ajouter
également `--route-option 2`. Les variantes précédentes utilisent route 1.
Le fichier `build_options.json` du stage
conserve les arguments exacts lorsqu’il est présent.

Cette commande régénère le firmware incorporé à l'ITCM. La génération des IP
USB utilise l'IDE indiqué ; la synthèse complète utilise l'installation
Gowin V1.9.12 prévue par le script. Le manifeste et les fichiers `usb_phy.json`
et `usb_controller.json` de chaque build précisent les versions effectives.

```
python3 TESTS/test_gpu_v1.py --out /tmp/console_v1_limits
python3 TESTS/test_gpu_v1.py --read-min 1 --out /tmp/console_v1_fast_reply
python3 TESTS/test_gpu_v1_api.py
python3 tools/render_gpu_v1.py --out /tmp/console_v1_scenes --rtl --write-header
python3 TESTS/test_gpu_raster.py --out /tmp/console_v1_old_raster
python3 TESTS/test_gpu_accel.py --affine --equiv-blitter-root tang/impl/gpu_l1315_r3/source --equiv-dma-delay 0 --out /tmp/console_v1_legacy
python3 TESTS/test_gpu_layers_equivalence.py --reference-root tang/impl/gpu_perspective_r10/source --out /tmp/console_v1_layers_equiv
```

Banc d'affichage : `TESTS/rtl/gpu_layers_tb.sv`, paramètres W=800, H=480,
VT=533, SPRITES=1, TILES=5, OVERLAY=1, HALF=1, PITCH=832. Le mode natif à pas
personnalisé utilise HALF=0/PITCH=1664. Les sources sont celles du banc de
composition habituel, dont `gpu_rgb_reader.v`.

Sur ax15, après contrôle du manifeste, de la cible et du timing :

```
python3 tools/check_gpu_reloads.py --stage tang/impl/gpu_v1_rN --out TESTS/gpu_v1_board_rN --rounds 2 --usb-rounds 20
python3 tools/check_gpu_v1_endurance.py --seconds 1800 --out TESTS/gpu_v1_endurance_rN
```

Un seul propriétaire du port CDC. Les scripts conservent les journaux et leur
code de vérification. Aucun accès à la flash, aucun chargement d'une autre carte,
aucune modification des compilations Gowin des autres projets.
