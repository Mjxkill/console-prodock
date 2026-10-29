# Visite complète de LUMA — candidat logiciel isolé

Cette version ajoute `--showcase` (boucle) et `--showcase-once` (un parcours) au vrai jeu. Les déplacements, interactions et huit défis passent par les commandes ordinaires et les moteurs existants. Aucun drapeau de victoire n’est imposé ; aucun film ni coordonnées de projection précalculées. La réinitialisation d’une nouvelle partie de démonstration ne se produit qu’après le retour final réussi.

## Parcours et contenu couvert

| Séquence | Ce que voit le spectateur |
|---|---|
| Courrier de la vallée | Maëlle, Silo, Iria, quatre lettres, relais et marche avec caméra suiveuse |
| Atelier des vents | Passage au-delà du pont, deux ailettes, ouverture, cloche et retour |
| Terrasses d’ambre | Nora, sentier ouest vers Nils, jardin facultatif et portillon récompensé |
| Réseau d’eau | Prise, vanne et passerelle : deuxième itinéraire entre les lieux |
| Jardin des formes | Placement des formes, victoire et récompense |
| Observatoire des nombres | Fusion jusqu’à **1024**, victoire et retour au lieu |
| Atelier des blocs | Blocs qui tombent, lignes complétées |
| Ruines du circuit | Orientation des conducteurs et connexion |
| Maison des lueurs | Labyrinthe en vraie 3D, lumières, fantômes et pouvoir temporaire, passage secret |
| Tour des courroies | Plateformes en vraie 3D, sauts, échelles, obstacles, point de reprise et sommet |
| Quatre échos | Démonstration puis reproduction des cristaux colorés, huit manches |
| Simulateur des étoiles | Petit vaisseau, vagues, projectiles, bouclier, boss et victoire |
| Retour | Nora, chemin des eaux, portail réellement emprunté, panorama dans la vallée |

Les huit activités restent facultatives et accessibles dans un ordre libre en mode manuel. L’itinéraire de la démo est un exemple, pas une obligation de jeu. Les pauses de lecture et de visibilité de la démo ne constituent pas du contenu supplémentaire ni une estimation de durée de campagne.

## Lisibilité, contrôle et sauvegardes

Les conseils automatiques sont traduits en pas **strictement positifs**. Chaque commande attend un acquittement de présentation réelle avant la suivante. Les quatre puzzles sur grille conservent chaque action au moins 400 ms de simulation. Les modes chronométrés avancent par pas de 1/60 s, puis attendent l’image suivante : leur simulation peut ralentir à faible FPS pour rendre les commandes visibles. Les victoires restent affichées quatre secondes et au moins une présentation. Ce rythme est propre à la visite ; les règles et commandes du mode manuel sont conservées.

`E`, une touche de déplacement ou une autre commande reconnue interrompt la visite et rend la main **sans déclencher aussi une action dans le puzzle**. `Q` quitte directement la démo. Après reprise manuelle, `Q` dans une activité revient normalement dans le monde. Un tour dure entre 778,7 et 1007,3 secondes simulées dans les cadences testées (60 à 3 acquittements/s), soit environ **13 à 17 minutes**. La durée réelle sur Pro Dock reste à mesurer. Une borne de 1200 s simulées et de 3600 s murales par tour évite un blocage silencieux ; un échec affiche un message et le mode `--showcase-once` rend un code non nul.

La démonstration refuse `--save`, `--manual` et `--benchmark`. Elle n’ouvre ni n’écrit les sauvegardes utilisateur. Les champs d’état du spectacle sont transitoires, exclus du format V5. Après prise en main, cette session reste sans sauvegarde. Le mode manuel habituel avec chemin explicite reste disponible en relançant le jeu. Les références AR1, OP2, leurs exécutables et leurs preuves ne sont pas modifiées.

`--host --showcase-once --advance N --capture prefix` est une **fixture hors écran explicitement journalisée** : elle accélère la préparation d’une image de contrôle en simulant un acquittement toutes les dix étapes. Elle ne mesure pas la durée et ne doit jamais être présentée comme la démo matérielle. L’avance rapide d’une démo est refusée sur le chemin matériel.

## Accélérations réellement exposées

La vallée et les activités 3D utilisent G3D1 : transformations, perspective, profondeur, textures ; le ciel réemploie COPY et la profondeur est effacée par CLEAR. Eau, ailes des oiseaux et arbres restent animés par le jeu. Le HUD utilise une ou deux couches indexées natives avec couleur zéro transparente et banques alternées. Les puzzles 2D utilisent un plan indexé ; le shooter emploie deux couches d’étoiles, les sprites et son plan d’interface, avec transparence par clé de couleur. Il ne s’agit pas de mélange alpha général, ni de seize couches actives. Aucun nouveau DRAW de texte ni nouvel asset n’est ajouté par le contrôleur de visite.

## Limites conservées

C’est une tranche d’aventure avec deux régions, un atelier et huit défis courts, **pas encore la grande campagne de plusieurs heures demandée**. Pas de véhicules jouables dans cette branche 3D, pas de musique matérielle qualifiée, pas de combat libre de campagne, ni de nouvelle zone ajoutée ici. Le shooter reste visuellement simple. Les vues sont rendues par le vrai flux de commandes ; la comparaison RV32/QEMU ne remplace ni le GPU AE350 réel, ni les FPS matériels, ni une observation de l’écran.

Aucun FPGA, noyau, flash ou carte SD n’est modifié. OP2 reste la dernière version vérifiée sur la Pro Dock tant que ce candidat et sa conduite d’essai n’ont pas été relus.
