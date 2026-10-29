# LUMA — plan de refonte du 27 octobre 2026

## Décisions et priorité

Le retour utilisateur sur la version R6 en cours d'essai est positif : le
parcours paraît plus fluide et Tetris/1024 sont beaucoup plus beaux. Conserver
cette direction. Les prochaines améliorations visibles prioritaires sont :

1. Glissements des pièces et fusions, au lieu de sauts de case.
2. Textures nettement plus belles dans le parcours, sans perdre sa fluidité.
3. Refonte du Simon, encore jugé insuffisant.
4. Finition des autres activités, puis vrais jeux de cartes et extension du monde.

Ce retour visuel est distinct d'une mesure de FPS. Le tour matériel PP2 de R6
est en cours lors de la rédaction ; ses résultats par activité doivent guider
les budgets. Le diagnostic Neo continue en parallèle, avec un responsable
distinct, sans attendre les ressources artistiques ni utiliser la Pro Dock.

## Livrables par chantier

| Chantier | Modifications concrètes | Critère de fin du lot |
|---|---|---|
| Animation commune | Horloge d'animation indépendante des coups de jeu ; interpolation de position, ombre, opacité et échelle ; file d'événements bornée ; reprise propre après pause | Mêmes règles, sauvegardes et résultats, avec positions intermédiaires visibles ; aucune téléportation liée au rythme de la démo |
| 1024 | Toutes les tuiles glissent simultanément ; fusion seulement à l'arrivée ; apparition douce de la nouvelle tuile ; ombre et brève mise en valeur de la fusion | Aucun doublon, chiffre fantôme ou fusion anticipée ; animations testées dans les quatre directions et sur fusions multiples |
| Tetris / blocs | Déplacement latéral et chute animés ; silhouette de destination translucide ; pose, disparition des lignes et descente des rangées ordonnées | Collision logique inchangée, ghost exact ; plusieurs lignes et entrée rapide pendant animation correctement traitées |
| Simon | Instrument de mémoire ancien de LUMA : quatre cristaux enchâssés, socle gravé, anneaux lumineux, enfoncement ; montée progressive de lumière, halo diffus qui s'étend puis s'éteint en fondu | Couleurs lisibles éteintes/allumées ; pics de la séquence distincts malgré les fondus ; rythme stable quel que soit le FPS ; erreur et réussite soignées |
| Circuit et formes | Matières cohérentes avec l'atelier ; pièces glissantes, rotation animée, ombres ; progression visible du courant et retour d'erreur clair | Défi réellement jouable au clavier, annulation et reprise exactes ; aucun panneau ne masque les pièces |
| Shooter | Garder le rendu par couches et sprites, améliorer silhouettes, formations, explosions, bouclier et boss ; trajectoires continues | Lecture claire des projectiles ; mesure à charge reproductible, comparaison avec les principes de NEBULA ; pas de gain déduit du seul nombre de triangles |
| Maison hantée en 3D | Personnage et fantômes glissent entre les cases, virages animés ; sols/murs/portes cohérents, lanternes, ambiance et objets à collecter | Aucun saut de case affiché ; grille et collisions conservées, aucun virage ne coupe un mur ; exploration libre et embranchements |
| Tour de plateformes en 3D | Pierres, bois, métal, obstacles et silhouette du personnage plus soignés ; ombre de réception et caméra lisible | Sauts et plateformes compréhensibles ; animations continues ; aucune modification visuelle ne désynchronise les collisions |
| Parcours 3D | Herbe, fleurs, chemins, rochers, bois, façades, eau et feuillage ; personnages mieux identifiables, points d'intérêt et ambiance | Comparaison avant/après sur les mêmes vues et trajets ; détail lisible à la résolution du jeu ; aucune régression de collision ou perte de fluidité acceptée silencieusement |
| Jeux de cartes | Table et cartes originales, distribution, éventail, sélection, retournement et plis ; moteur visuel partagé | Premier jeu complet de défausse de couleurs, puis poker et tarot avec règles et tests séparés ; aucune simple maquette annoncée comme jeu terminé |
| Aventure longue | Plusieurs lieux et chemins par région ; défis facultatifs, personnages, découvertes et récompenses ; nouvelles régions et déplacements | Contenu réel mesuré et sauvegardable ; la durée d'une boucle automatique ne vaut pas une campagne de plusieurs heures |

## Ordre d'intégration

**Lot A — conserver les progrès visibles.** Terminer le tour PP2, récupérer
les mesures par activité et figer R6 comme point de comparaison logiciel.
Ne pas modifier le programme durant sa mesure. Conserver les références
historiques FPGA G22r0 / NEBULA R17 et la sauvegarde utilisateur.

**Lot B — plateaux vivants.** Intégrer le moteur `puzzle_motion_r1` à une
copie de R6, avec le temps continu et le conseiller 1024 compact seulement
après leurs tests. Livrer 1024, Tetris et Simon, puis appliquer les mêmes
primitives au circuit et aux formes. Le nouvel art de Tetris/1024 reste une
variante à comparer, pas une obligation de remplacer le visuel apprécié.
La demande de glissement concerne également le labyrinthe façon Pacman :
interpoler les acteurs sur leurs segments autorisés, y compris les fantômes,
sans déplacer les collisions ni laisser une diagonale traverser un angle.

**Lot C — matières du monde.** Génération et sélection en parallèle du lot B.
Remplacer d'abord les textures sans ajouter de géométrie, modifier les
collisions ou augmenter aveuglément leur allocation. Tester les mêmes poses
et mouvements. Ajouter ensuite végétation/objets/effets selon le budget mesuré.

**Lot D — finition des activités 3D et du shooter.** Décliner les matières
retenues ; compléter les effets, le rythme et les retours d'action. Chaque
activité doit être jouable et visible seule, puis dans la visite automatique.

**Lot E — cartes et campagne.** Réutiliser le moteur d'animation validé,
ajouter de vraies règles et des adversaires, puis étendre les régions et les
quêtes. Cheval, vélo, véhicule et vol restent des mécanismes à développer et
tester ; ils ne sont pas déjà présents parce qu'un concept d'image existe.

Les lots artistiques, la simulation des règles, la programmation et les essais
du lot précédent avancent en parallèle. L'ordre ci-dessus concerne les
intégrations et leur validation, pas une attente entre tous les travaux.

## Accélérations à exploiter réellement

- Garder les atlas et fonds fixes en DDR. Déplacer les coordonnées, les
  fenêtres de lecture et les adresses de couches au lieu de recopier un écran.
- Utiliser les couches indexées pour les fonds et interfaces stables, les
  sprites pour les petits éléments ; le matériel a 16 couches, dont 12
  accessibles au jeu avec le noyau actif, et 64 sprites de 32×32 maximum.
- Les couches et sprites indexés ont une couleur-clé transparente, **pas un
  alpha fractionnaire**. Les ombres et fondus réels passent par les triangles
  texturés RGB565/ARGB4444 du moteur V1, avec une surface et un nombre de
  couches translucides bornés.
- Les seize grosses tuiles d'un plateau ne tiennent pas toutes dans 64 sprites
  à la résolution souhaitée. Prévoir un rendu hybride avec quads GPU ; ne pas
  réduire la demande à l'animation d'une seule tuile.
- Le parcours demeure en vraie 3D : géométrie G3D1, textures, profondeur et
  caméra calculée pendant le jeu. Les images générées servent de matières et
  de ressources, pas de vidéo ni de paysage préenregistré remplaçant le relief.
- Évaluer mipmaps explicites, regroupement de matériaux, visibilité et niveau
  de détail. Les billboards ne sont retenus que si le résultat et le temps
  d'image s'améliorent : réduire les faces peut augmenter le coût des pixels.
- Ne pas augmenter simultanément résolution, transparence, géométrie et
  taille des textures sans mesurer chaque cause de coût.

## Production des images sur gx10-2

ComfyUI exclusivement, dans le candidat `art_refresh_20261027`. Les sources
R6/R7 restent intactes. La génération est mise en file pendant les travaux
de code et de simulation ; les autres tâches ComfyUI ne sont pas annulées.

1. Comparer **Qwen Image 2512** et **Flux2 Dev** sur les mêmes sujets, puis
   Z-Image Turbo si utile. Aucun modèle n'est déclaré meilleur par son nom.
2. Comparer une scène d'objet travaillé (Simon) et une vraie matière répétable
   du monde. Demander une vue orthographique de surface, sans horizon, sans
   perspective ni ombre directionnelle incompatible avec le jeu.
3. Examiner l'original, sa conversion RGB565/ARGB4444, sa réduction 128²/256²,
   sa répétition 3×3 et son rendu oblique dans une scène. Rejeter les images
   belles en grand mais bruyantes, floues ou illisibles dans le jeu.
4. Retenir le modèle et le prompt par famille de ressource ; plusieurs modèles
   peuvent être utiles. Lancer les variantes de matières, accessoires et
   personnages, puis importer uniquement les gagnantes.
5. Conserver workflow, modèle, seed, prompt, identifiant serveur, original,
   conversions, empreintes et décision. Une génération soumise n'est pas une
   ressource intégrée ou validée sur LCD.

Familles à produire : Simon (socle/touches), sols et façades du parcours,
feuillage et accessoires du village, maison hantée, tour, vaisseaux et effets,
tables/cartes ; variantes de matières des plateaux actuels si elles apportent
un gain visible. Les chiffres, symboles de jeu et textes sont composés par
le programme pour rester exacts et lisibles.

## Répartition parallèle

| Travail | Responsable d'intégration | Aides indépendantes |
|---|---|---|
| Jeu, essais Pro Dock, mesures et temps continu | Agent `luma_game` | Beam : budget et chemin de rendu ; DeepSeek : code, états et cas limites |
| Animations des plateaux, Simon, génération ComfyUI | Agent `luma_minigames` | Claude Fable : composition et finition ; DeepSeek : transitions et règles |
| Textures du monde et critères de sélection | Racine avec `luma_minigames` | Claude Fable : cahier artistique ; Beam : coût, répétition et conversion |
| Neo : observateur COPY/mémoire, simulation et candidat | Agent `neo_gpu_diagnosis` + racine | Revues ciblées des raccordements ; bancs locaux et mappés exécutés par les agents |

Claude Code utilise Fable ; OpenCode utilise DeepSeek V4.1 Flash et Beam.
Les modèles externes reçoivent des paquets de code explicites. Leurs patches
et tests proposés sont relus, exécutés et intégrés par le responsable ; une
réponse de modèle ne constitue pas une simulation exécutée ni une preuve.
Un même sujet peut avoir un auteur et un contradicteur indépendants. Un seul
responsable écrit chaque module et un seul effectue les essais d'une carte.

## Critères d'acceptation

**Règles.** Coups légaux, rotations/fusions simultanées, pause, annulation,
défaite, victoire, redémarrage et sauvegarde. À temps commun, une animation
doit avoir la même pose à plusieurs cadences. Tester également les longues
images, l'épuisement de la file d'animations et les changements d'activité.

**Image.** Captures du vrai renderer sur les deux profils, contrôles des
commandes et des plages mémoire, puis inspection des animations. Un plateau
doit montrer des positions entre les cases ; des captures de deux positions
finales ne suffisent pas. Transparence, chiffres, ombres et silhouettes restent
lisibles à la taille réelle. Les images ComfyUI seules ne valident pas le jeu.

**Temps d'image.** Mesurer simulation/conseiller, préparation, publication de
mémoire, SUBMIT et PRESENT séparément ; compter octets copiés, commandes,
sprites et couches. Mesurer moyenne, p95, p99 et maxima par activité et sur
les transitions, sans inclure les vérifications JTAG/UART dans la fenêtre.
Viser 60 FPS pour les plateaux/shooter et au moins 30 FPS pour le parcours ;
ce sont des objectifs, pas des résultats acquis. Si le matériel reste sous
ces objectifs, publier les mesures et le coût dominant, sans appeler le lot
« fluide » au seul motif que les pixels sont corrects.

**Carte.** Pro Dock sous verrou, binaire identifié, mêmes trajets/charges,
compteurs d'erreurs et mémoire contrôlés, puis laisser le jeu visible après
succès. Neo reste une qualification séparée. Toute modification commune
soumise aux gardes des cartes rejoue la campagne complète
`tools/run_board_regressions.py` dans un nouveau répertoire.

## Repères des travaux déjà engagés

- R6 figée : `build/arcade_polish_20261026_r6` ; essai en cours
  `tests/hardware/polish_20261027_pp2_prepared_r2`.
- Animations : `candidates/puzzle_motion_r1` ; temps continu :
  `candidates/motion_continuous_r1` ; conseiller :
  `candidates/adviser_compact_r1`.
- Textures déjà préparées, distinctes du futur comparatif :
  `candidates/world_materials_r7` ; audit des capacités :
  `tests/G22R0_FEATURE_AUDIT.md`.
- Neo : `TESTS/neo_720p_20261012/capture_memory_20261027` depuis la racine du
  dépôt ; simulations de l'observateur dans
  `TESTS/assisted_reviews_20261026/observer_copy_01`.

Les statuts des processus et des générations sont dans leurs manifestes et
journaux ; ce document décrit le plan et ne sert pas de moniteur permanent.

## Première mesure R6 reçue pendant le travail

Le tour PP2 a terminé les huit activités par leurs commandes normales. Les
dernières vérifications de la boucle laissée à l'écran et de la sauvegarde
passent également : R6 reste visible, sauvegarde utilisateur inchangée,
aucune écriture FPGA/noyau/SD/flash. Résultat :
`tests/hardware/polish_20261027_pp2_result/result.json`, SHA-256
`e67eb4481091169da36c1825c5809e0eae1ddec9251f42fc275d4447df54ca36`.
Première lecture des coûts du tour :

| Activité | FPS moyens mesurés | Coût ou irrégularité déterminant |
|---|---:|---|
| Exploration | 10,89 | SUBMIT 266,39 s sur 432,39 s, environ 61,6 % |
| 1024 | 9,63 | Préparation CPU 244,93 s sur 293,46 s, environ 83,5 % ; conseiller seulement 1,93 s |
| Blocs | 32,14 | p99 dans une classe jusqu'à 368 ms ; maximum 434 ms |
| Shooter | 35,09 | p99 dans une classe jusqu'à 220 ms ; maximum 309 ms |
| Maison 3D | 5,91 | Coût détaillé à lire dans le rapport matériel |
| Simon | 13,51 | Coût détaillé à lire dans le rapport matériel |
| Tour 3D | 16,37 | Coût détaillé à lire dans le rapport matériel |

Ces valeurs proviennent d'activités et de durées différentes ; elles ne sont
pas une comparaison A/B avec NEBULA ou SC1. Les percentiles sont des classes
de l'histogramme, pas des temps individuels connus au milliseconde près.

**Conséquence immédiate :** priorité au rendu des plateaux et à la suppression
des préparations coûteuses, avant le conseiller 1024 compact. Une animation
qui redessinerait tout le plateau côté CPU à chaque image pourrait aggraver
le problème. Préparer les matières une fois et déplacer les éléments GPU.
Les textures du parcours sont d'abord remplacées à géométrie et allocation
constantes ; le temps SUBMIT doit être remesuré après intégration.
