# Moteurs des haltes de LUMA — format 1

Ces cinq moteurs logiciels sont destinés aux activités facultatives de LUMA.
Ils ne connaissent ni le monde, ni ses récompenses, ni Linux, ni le GPU. Ils
ne modifient aucun pilote, RTL ou paquet publié. Les références Pro Dock
G22r0 / NEBULA R17 sont conservées ; ces tests hôte ne qualifient aucune carte.

## Intégration

Inclure `l3_minigames.h` et compiler `l3_minigames.c` en C99. Aucune allocation,
aucun flottant, aucune dépendance de plateforme. L'état fait 992 octets sur les
ABI vérifiées ; ses champs sont privés pour l'intégrateur. Ne jamais les
modifier directement, ni sérialiser la structure brute.

```c
L3MiniState game;
L3MiniView view;
l3_mini_init(&game, L3_MINI_CIRCUIT, activity_seed);
uint32_t event = l3_mini_step(&game, pressed, held, dt_ms);
if (event & L3_MINI_EVENT_EXIT) { /* revenir à l'exploration */ }
if (event & L3_MINI_EVENT_WON) { /* récompense unique par activityID */ }
l3_mini_view(&game, &view);
```

`pressed` contient les fronts positifs ; un bit signifie une commande. Un
front est traité une seule fois par appel, même si `dt_ms == 0`. `held` ne
recrée jamais ces fronts. Il accélère la chute des blocs avec Bas, ou indique
une direction souhaitée dans la maison. Pour des directions simultanées,
l'ordre de priorité est Haut, Droite, Bas, Gauche. Action et Rotation sont
fusionnées en une rotation unique dans le circuit ; dans les formes,
déplacement, rotation, puis pose sont traités dans cet ordre.

Le temps est plafonné à **250 ms par appel**. La conversion en pas de 60 Hz
conserve sa fraction dans l'état ; elle n'arrondit pas chaque image. Si une
pause supérieure à 250 ms doit être simulée, l'intégrateur la découpe en
appels successifs. Une pause de menu ne transmet aucun temps. Les comparaisons
de fréquence doivent conserver les mêmes instants de fronts : envoyer le
front avec `dt=0`, puis faire avancer la même durée permet cette comparaison.
Une victoire/défaite arrête le temps au pas terminal et annule sa fraction.

**Retour est prioritaire** : un front `L3_MINI_BACK` renvoie `EVENT_EXIT` et
laisse l'état strictement identique, y compris son temps et son statut. Il
n'accorde aucune récompense. Les états WON/LOST sont gelés ; ils acceptent
encore Retour. Reprendre conserve le même état. Recommencer appelle `init`
avec le type et la graine voulus ; le même couple reproduit le même départ.
L'intégrateur doit relâcher/verrouiller les touches déjà tenues à l'entrée,
à la reprise et au redémarrage pour ne pas rejouer leur ancien front.

Une entrée invalide renvoie `EVENT_INVALID` sans mutation. `EVENT_CHANGED`
signale un appel actif susceptible de modifier la vue ; ce n'est pas une
preuve qu'un coup était légal ou qu'une tuile s'est déplacée. Les événements
WON/LOST n'apparaissent qu'à la transition, pas à chaque image suivante.

## Vue logique

`cells[y * 20 + x]` est la seule indexation permise : le pas reste 20 même
pour une grille de quatre cases. Dimensions maximales 20 × 20 ; toute case
hors grille est nulle. Les couleurs sont des indices logiques 0..15, à
associer à la palette du lieu. `title`, `help` et `objective` pointent vers
des chaînes françaises statiques ; les accents sont translittérés pour
les petits afficheurs. Aucun framebuffer n'est transmis.

Les cellules portent `kind`, `color`, `value`, `flags` et un glyphe ASCII de
secours. Pour les circuits, **dessiner les connexions avec `value`** :
Nord=1, Est=2, Sud=4, Ouest=8. Les types START/FINISH conservent ce masque.
Le glyphe `+` seul ne montre pas l'orientation. CONNECTED indique le courant,
CURSOR la sélection. Les nombres portent leur valeur réelle, jusqu'à 1024.
ACTIVE indique une pièce mobile ou, dans la maison, une lanterne active.
Le curseur vaut (-1,-1) lorsqu'il n'a pas de sens. Les cibles de formes
restent visibles sous le déplacement de leur silhouette active.

## Règles et commandes

| Activité | Règles | Commandes | Objectif / défaite |
|---|---|---|---|
| Circuit des lucioles | Une route monotone solvable est construite, puis les tuyaux et leurres sont tournés. Le courant ne traverse que deux connexions réciproques. | Flèches : curseur ; Action ou Rotation : quart de tour horaire. | Relier l'entrée ouest en haut à gauche à la sortie est en bas à droite, avant 120 rotations. |
| Blocs de la carrière | Grille 8×14, sept tétriminos, collisions, rotation avec correction de bord gauche, gravité et suppression des lignes. Quatre rangées initiales laissent un puits de deux colonnes. Les deux premières pièces carrées enseignent ce puits ; les suivantes sont tirées parmi les sept formes. | Gauche/Droite : déplacer ; Haut ou Rotation : tourner ; Bas : descendre, tenu pour chute douce ; Action : chute immédiate. | Effacer quatre lignes. Perdu lorsqu'une nouvelle pièce ne peut apparaître. |
| Atelier des formes | Quatre silhouettes de couleurs différentes sont orientées par la graine et doivent rejoindre leur empreinte. Une silhouette mobile peut passer au-dessus d'une forme posée, mais ne peut être assemblée ailleurs que sur ses quatre cases exactes. | Flèches : déplacer ; Rotation : tourner ; Action : assembler. | Poser quatre formes ; huit poses incorrectes entraînent la défaite. |
| Cristal 1024 | Grille 4×4 ; les nombres égaux fusionnent une seule fois par coup. Chaque déplacement effectif ajoute exactement un 2 (90 %) ou un 4 (10 %). Un coup nul ne consomme ni graine ni nouvelle tuile. | Flèches : glisser toute la grille. | Former 1024 ; perdu lorsqu'aucun glissement ni aucune fusion ne reste possible. |
| Maison des lueurs | Plan original 13×11, lumières et lanternes, deux fantômes poursuivants. Le joueur avance d'une case toutes les six simulations, les fantômes toutes les quatorze. Une lanterne fait fuir les fantômes pendant 300 pas. Une vie perdue replace les acteurs et donne 120 pas de protection ; les lumières ramassées restent acquises. | Flèches : direction souhaitée, mémorisée jusqu'à un passage libre. Le mouvement continue tant que le couloir le permet. | Retrouver toutes les lumières/lanternes avec trois vies. |

Les points n'accordent rien directement au monde. La victoire de la maison
arrive sur sa dernière lumière ; ce moteur n'émet pas de cellule FINISH pour
ce plan. Le lieu 3D gère sa porte physique et le retour à l'exploration.

## Sauvegarde portable et validation

`encode` écrit exactement **1008 octets**, en little endian explicite :

| Octets | Contenu |
|---|---|
| 0..3 | Signature ASCII `L3MG` |
| 4..7 | Version 1 |
| 8..11 | Taille de charge utile : 992 |
| 12..15 | FNV-1a 32 bits de tous les octets sauf cette empreinte |
| 16..79 | 16 entiers de métadonnées |
| 80..207 | 32 entiers de données privées |
| 208..607 | Plateau, pas 20 |
| 608..1007 | Cibles/route de génération, pas 20 |

L'empreinte détecte la corruption accidentelle ; elle n'est pas une signature
cryptographique ni une protection contre la triche. Le décodeur exige une
taille exacte, une version compatible, des champs réservés nuls, des indices
bornés et les invariants du jeu : masse des tuiles, nombre de lignes/pièces,
correspondance des cibles, topologie, compte des lumières, statuts et phases.
Il construit un état temporaire et ne remplace la destination qu'après tous
les contrôles. Une sauvegarde tronquée ou refusée laisse la destination
strictement identique. L'ancienne version n'est jamais interprétée comme une
nouvelle version par simple taille de structure.

## Démonstrations et tests

`l3_mini_demo_input` inspecte un état valide et renvoie des commandes ordinaires
à transmettre à `step`. Il ne modifie pas cet état et ne force aucun statut.
Le circuit suit la route générée, les formes cherchent leur empreinte, les
blocs évaluent les poses, 1024 cherche quatre coups déterministes, la maison
cherche les lumières et évite les fantômes lorsque la lanterne est éteinte.
Il ne garantit pas de sauver une position déjà compromise.

Les cinq fichiers `tests/traces/win_*.trace` sont des témoins indépendants
du conseiller : première ligne `L3MINITRACE version type graine`, puis une
ligne `pressed held dt_ms` par appel. Ils se rejouent uniquement avec `init`
et `step`. À la graine 1 : 20, 6, 28, 499 et 87 commandes respectivement.

```sh
python3 games/luma3d/minigames/tests/run_tests.py \
  --out games/luma3d/minigames/tests/results/<nom-unique>
```

La suite compile en C99 strict, puis avec AddressSanitizer/UBSan. Elle couvre
les victoires, les cinq défaites, reprise et redémarrage, 64 graines pour les
trois puzzles construits, huit graines pour 1024, les fusions et coups nuls,
les collisions, 160 000 appels pseudoaléatoires bornés, 10 000 mutations à
empreinte recalculée, chaque longueur tronquée et chaque octet corrompu,
les données incompatibles et huit cadences de 1 à 250 ms à chronologie égale.
Les journaux, commandes, empreintes de sources et traces sont conservés.

LeakSanitizer est désactivé parce que l'environnement de test sous `ptrace`
ne le supporte pas. AddressSanitizer et UBSan restent actifs ; les moteurs
n'utilisent pas le tas. Les résultats concernent ces sources exactes et
l'exécution hôte. Les contrôles globaux des deux profils, la synthèse, le
timing et les essais matériels sont des preuves distinctes à joindre par
l'intégrateur ; aucun résultat hôte ne remplace leur qualification.
