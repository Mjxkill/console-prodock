# Contenu réellement disponible — 24 octobre 2026

La version 3D est une tranche technique jouable, pas encore la longue aventure
demandée. Le dernier état matériel confirmé est R3 en visite automatique sur
Pro Dock, PID 424. La lecture des journaux sur ax15 confirme cette preuve du
24 octobre à 17:55 CEST ; aucune nouvelle interrogation du CDC n'a été faite
pendant la revue actuelle. Aucun contrôleur Pro Dock/J-Link n'était actif sur
ax15 et le verrou diagnostic n'avait pas de détenteur.

| Domaine | Présent dans R3 | Limite réelle |
|---|---|---|
| Monde | Une vallée de 160 × 160 m, hameau, lac, moulin, pont et ruines ; relief texturé en vraie 3D | Un seul lieu ; pas d'intérieur ni de seconde région jouable |
| Héros | Marche, course, saut, inertie, caméra arrière et collisions ; membres/cape articulés | Pas de nage, escalade, monture ni véhicule en 3D |
| Commandes | WASD, IJKL, espace, E et T par terminal | Pas de manette intégrée ; la visite en cours utilise l'autopilote avec entrée fermée |
| Activité | Ramasser quatre lettres puis atteindre l'observatoire | L'interaction finale marque un état de réussite en mémoire ; pas de scène de conclusion ni de changement spatial du monde |
| Autopilote | Suit quinze points par la même physique, ramasse les lettres, revient à pied | C'est un parcours de démonstration, pas une succession de missions |
| Habitants et récit | Noms de lettres et repères dans les données | Pas de conversation, choix, emploi du temps ou mission donnée par un personnage |
| Défis | Pentes, obstacles et eau profonde bloquante | Pas d'ennemi, combat, tir, santé, énigme, mécanisme ou donjon en 3D |
| Progression | Quatre bits de collecte et un objectif dans l'état vivant | Pas d'inventaire durable, journal, chapitre, déblocage ou sauvegarde/reprise 3D |
| Son | Ressources YuE2 expérimentales archivées dans le chantier précédent | Aucun backend audio intégré au binaire 3D courant ; aucune promesse de son sur la carte |
| Rendu | Perspective, Z, lumière, textures ComfyUI, moulin/lettres/héros animés | Derniers débits à pose fixe : environ 9 à 13 FPS, cible 30 FPS non atteinte |
| Exploration libre | Physique de la vallée et contrôle manuel existants | Le terrain compact R3 peut s'écarter de la collision jusqu'à 2,08 m hors chemin ; la qualification complète de l'exploration reste à faire |

Le test de parcours accomplit l'aller-retour en 3 787 pas de simulation à
60 Hz, soit 63,1 secondes simulées. Ce nombre vérifie le parcours physique ;
ce n'est ni une durée humaine de découverte ni du contenu d'une heure.
Le prototype 2D archivé comporte davantage de missions et de salles, avec
un parcours automatique complet de 49,4 minutes. Il n'est pas exécuté par
le moteur 3D et ses minutes ne s'ajoutent pas à celles de cette vallée.

La cible de conception reste plusieurs heures, avec un objectif principal
de 6 à 10 heures. Aucun volume jouable de cet ordre n'est construit ou mesuré
actuellement. Aucun calcul à partir de titres de missions, de longues
distances ou de temporisateurs ne constitue une preuve de durée.

Pour transformer cette vallée en première véritable mission, le prochain
lot de contenu doit apporter un habitant qui confie un objectif visible,
une décision ou un mécanisme qui modifie un trajet, puis une restitution
qui ouvre un lieu différent. Cette mission devra fonctionner au clavier
sans autopilote, pouvoir être quittée et reprise après redémarrage, et
donner un retour lisible à l'écran. Les sauvegardes devront supporter
corruption/rejet atomique et identité stable des objets avant d'ajouter
des heures de progression.

Une campagne longue nécessitera ensuite plusieurs situations distinctes :
exploration et raccourcis persistants, énigmes à plusieurs états, rencontres
avec déplacements/attaques lisibles, puis capacités et véhicules donnant
accès à de vraies activités. Les régions, intérieurs et conséquences devront
être construits et parcourus. Les durées seront relevées lors de parties
réelles, séparément des solveurs et des visites automatiques.

Le travail logiciel actuel est un candidat isolé de rejet des objets hors
champ : `candidates/frustum_r2/`. Il conserve le contenu, les textures et les
pixels de R3 sur huit vues contrôlées ; il réduit certains DRAW et sommets.
Son gain de cadence n'est pas encore mesuré sur carte. R3 reste affichée,
sans modification FPGA, noyau, SD ou flash.

## Première mission 3D, candidate locale distincte

`build/adventure_20261024_review3/` contient maintenant une première boucle
complète : Maëlle confie le courrier, deux lettres conduisent à Silo, trois
pierres du relais des Roseaux demandent un ordre précis, puis Iria reçoit les
quatre lettres aux ruines. Le journal et les dialogues français utilisent
deux couches indexées existantes ; la caméra, les habitants et le paysage
restent en vraie 3D. Une mauvaise séquence peut être recommencée.

Les tests de scénario et les 1 000 états de rendu couvrant les cinq phases
passent aux deux profils, ainsi que huit aperçus par le modèle GPU. La mission
automatique prend 61,87 secondes simulées, dont 30 secondes de lecture, et
l'aller-retour 93,35 secondes. Aucune durée humaine ni performance matérielle
de ce nouveau lot n'est mesurée. Le binaire AE350 est prêt, non chargé.

Les trois habitants réutilisent encore le modèle du héros avec des tailles
et teintes différentes ; leurs silhouettes doivent être retravaillées.
La progression reste en mémoire, sans sauvegarde 3D. Ce lot n'ajoute ni combat,
ni véhicule, ni autre région et n'atteint pas la campagne de plusieurs heures.
Le relais et le signal final sont les seules conséquences visuelles actuelles.
Le candidat frustum est séparé, et R3 reste la version matérielle laissée visible.
Le détail et les commandes de reproduction sont dans
`candidates/adventure_r1/README.md`.

Le delta local `build/adventure_cast_20261024_r2/` différencie ensuite les trois
habitants : robe/tablier et bonnet pour Maëlle, uniforme/casquette et sacoche
pour Silo, cheveux clairs et cape violette pour Iria. Il conserve exactement le
scénario, la caméra, la physique et le HUD de la tranche précédente. Huit aperçus
et le même contrat complet passent, sans hausse du nombre de DRAW dans ces
vues. Ce delta est lui aussi non chargé et sans mesure FPS matérielle. Les
limites de contenu et de durée ci-dessus restent toutes présentes.


Mise à jour matérielle du 25 octobre 2026 : vallée vivante art3

Le candidat `build/valley_living_20261024_art3` est maintenant chargé sur Pro Dock,
laissé visible en parcours automatique (`/tmp/luma3d-vl2`, PID 635). Six scènes
avec pixels et banques HUD exacts ; la courte mission du courrier se termine
réellement sur carte. Textures ComfyUI, silhouettes des habitants, eau/arbres/oiseaux
animés et HUD compact sont intégrés. Rapport :
`tests/hardware/living_20261024_vl2/REPORT.txt`.

Ce résultat n'étend pas la durée de contenu : une mission courte, sans sauvegarde
3D durable, combats, véhicules ni campagne longue. La fluidité reste insuffisante :
7,31 FPS à l'arrivée contre 8,74 FPS pour R3 ; moyenne totale du parcours 7,45 FPS.
Le profil Neo a seulement des contrôles locaux pour ce lot. Aucun nouveau FPGA,
noyau ni stockage persistant n'a été écrit lors de cet essai.
