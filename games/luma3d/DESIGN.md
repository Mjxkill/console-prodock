# LUMA — principes d’exploration et d’activités

L’aventure doit proposer plusieurs lieux dans une même région, avec chemins
alternatifs, détours facultatifs, boucles et raccourcis persistants. Une route
automatique n’est qu’un itinéraire de présentation : elle ne définit pas les
déplacements permis au joueur. Marcher sur un terrain libre ne suffit pas à
faire une région intéressante ; les détours doivent conduire à des découvertes
et à des actions utiles. La demande utilisateur du 25 octobre insiste sur
cette distinction.

Les activités doivent pouvoir être choisies librement. Familles demandées :
circuit logique, blocs qui tombent, regroupement de formes, fusion jusqu’à
1024 et labyrinthe de collecte avec poursuivants. Chaque lieu offre une entrée
par E ; quitter restaure exactement l’exploration, sa position, son orientation,
sa caméra et sa mission. Les règles restent déterministes. Les puzzles de plateau utilisent les
couches 2D du GPU ; le labyrinthe de la maison hantée utilise de vrais murs,
fantômes et lanternes en 3D, avec une caméra de jeu G3D1. Les récompenses sont persistantes et uniques, y compris
si un défi gagné est recommencé. Aucun ensemble de cinq victoires ne doit être
obligatoire pour traverser une région.

État actuellement qualifié : OP2/R5 sur Pro Dock possède deux petites régions,
trois missions courtes, deux trajets dans les Terrasses et cinq activités
facultatives. Le jardin et la maison ouvrent des raccourcis. Le sentier ouest
reste praticable sans victoire ni réparation du pont ; Nils peut être rencontré
avant de rétablir l'eau. La visite automatique reste un parcours de présentation.

Le lot local `build/arcade_world_20261026_r2` ajoute trois lieux dans cette même
région : clairière des quatre échos, simulateur de l'observatoire et tour des
courroies. Leurs rendus, commandes, V5, récompenses uniques et retours sont
intégrés et testés localement. Ce lot n'est pas encore chargé sur carte ; OP2
et sa V4 restent inchangés.

Les trajets sont validés avec les mêmes commandes, pentes et collisions que
le joueur, sans téléportation. Les nouvelles surfaces rendues et physiques
restent cohérentes. Le découpage par région et les budgets DRAW/commandes sont
contrôlés ; les FPS sont mesurés séparément sur des poses définies. Une capture
PC ne prouve ni la fluidité ni l’affichage sur la carte.

Objectif à terme : plusieurs heures d’exploration et d’activités variées.
Cette durée n’est pas encore construite ni mesurée. Les relectures, attentes,
répétitions obligatoires et temps estimés ne sont pas comptés comme du contenu.


Demandes supplémentaires, désormais présentes dans le lot arcade local :
- Maison des lueurs : vestibule, salle de portraits, pièce aux lanternes,
  passages secrets ; labyrinthe 3D de fantômes, lumières à retrouver et pouvoir
  temporaire. L’état logique sur grille ne remplace pas son rendu spatial.
- Cercle des quatre cristaux : mémoire de couleurs, séquence lumineuse à
  reproduire puis allonger (type Simon), sans dépendance au son matériel.
- Tour des engrenages : plateformes 3D, sauts, échelles, obstacles roulants,
  points de reprise et objectif au sommet (inspiration jeux de plateformes
  classiques, monde et maillages originaux).
Les cristaux et la tour ont désormais leur lieu, leur vue G3D1 et leur reprise
V5 dans le candidat arcade. Les étages supérieurs de la tour sont montrés en
coupe pour conserver la visibilité. Ils ne sont pas encore livrés sur carte.

- Simulateur de vol de l’observatoire : shoot’em up vertical original,
  vaisseau libre, tirs/esquive, vagues, bonus/bouclier et boss. Rendu natif par sprites
  et deux couches d’étoiles, monde en pause et récompense unique : intégré
  au candidat local. Il reste un tutoriel court, avec son habillage et son
  débit matériel à qualifier. Les huit familles ne forment pas encore une
  campagne longue ou huit jeux autonomes achevés.

Le socle isolé `candidates/adventure_arcade_r1` fournit :
adaptateur des huit moteurs, reprise de chaque défi, récompenses uniques et
import des cinq états V4. Ses tests de logique ne constituent ni un rendu GPU
de ces trois activités supplémentaires ni une qualification matérielle.

L’intégration réelle se trouve dans `candidates/adventure_arcade_world_r1` :
le monde conserve ses anciens parcours et sa surface ; la réussite de la tour
ouvre une branche vers les eaux, les deux autres récompenses allument des
repères. Ces récompenses restent facultatives et ne s’ajoutent qu’une fois.
