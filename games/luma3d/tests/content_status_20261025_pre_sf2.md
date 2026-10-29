# État réel du jeu 3D — 25 octobre 2026

La version visible sur Pro Dock est la vallée **art3**, en visite automatique.
Après la reprise et la comparaison CPU + terrain, art3 a été rétabli :
PID 1058, startticks 7384377, progression des images et compteurs d’erreur nuls.
Preuve : `tests/hardware/terrain_cpu_20261025_to4/trial/result.json`.
Le FPGA G22r0 et le noyau G3D1 restent inchangés. Les nouveaux candidats
logiciels ne qualifient pas le matériel Neo.

| Domaine | Réellement jouable dans art3 | Limite actuelle |
|---|---|---|
| Paysage | Vallée 160 × 160 m, hameau, lac, moulin, pont, crête et ruines ; relief et textures ComfyUI | Une région, sans intérieur ou deuxième monde |
| Personnage | Marche, course, saut, inertie, collisions et caméra arrière | Pas de nage, escalade, monture ou véhicule 3D |
| Habitants | Maëlle, Silo et Iria, silhouettes distinctes, dialogues français | Trois personnages, un seul arc scénarisé |
| Mission | Deux lettres vers Silo, relais Terre–Vent–Ciel, quatre lettres remises à Iria | Boucle courte ; pas une campagne de plusieurs heures |
| Monde animé | Eau par UV, arbres proches, moulin, oiseaux et héros articulé en temps réel | Eau opaque ; pas de simulation de météo ou d’écosystème |
| Interface | Dialogue et carnet via une ou deux couches indexées, cache par page | Aucun inventaire développé ni choix narratif durable |
| Contrôle | WASD, IJKL, espace, E, J et T par terminal ; même physique en automatique | Pas de manette intégrée ; le processus de démonstration tourne avec entrée fermée |
| Progression | Collectes, ordre des pierres, signal et fin de mission dans l’état vivant | Pas encore de sauvegarde/reprise 3D durable |
| Défis | Relief, obstacles et relais à remettre dans l’ordre | Aucun combat, ennemi, tir ou donjon en 3D |
| Son | Ressources YuE2 expérimentales conservées du chantier précédent | Aucun backend audio intégré au jeu 3D |

La mission est réellement accomplie sur Pro Dock dans l’essai art3 :
`tests/hardware/living_20261024_vl2/REPORT.txt`. Le parcours automatique local
termine la mission en 61,87 secondes simulées, dont 30 secondes de dialogue ;
aller et retour en 93,35 secondes. Ce sont des mesures d’automate, pas une
durée humaine de découverte. Le prototype 2D archivé avait davantage de
contenu ; il n’est pas exécuté par le moteur 3D et sa durée ne s’y ajoute pas.

L’objectif de plusieurs heures, avec une cible de conception de 6 à 10 heures,
n’est pas construit ni mesuré. Il manque notamment des lieux distincts,
énigmes à plusieurs états, rencontres, capacités qui ouvrent de vrais trajets,
conséquences persistantes et sauvegardes robustes. Des titres de missions,
des temps d’attente ou des distances artificielles ne constituent pas du contenu.

## Fluidité et qualification

Art3 donne environ 7 à 13 FPS selon les vues fixes ; la cible de 30 FPS n’est
pas atteinte. Le rendu emploie G3D1, Z16, perspective, cache texture, voie opaque
proche, ciel réutilisé par COPY, CLEAR Z, LOD de maillages et couches HUD.
Audit sourcé : `tests/G22R0_FEATURE_AUDIT_ART3.md`.

Le tri terrain seul a été testé sur les six mêmes vues, 30 images après 3 de
chauffe, avec retour témoin final. Toutes les images et banques HUD passent,
mais le candidat n’a pas été conservé : médiane +3,07 %, inférieure au seuil
préfixé de 5 %, et dérive témoin +3,22 %, au-delà de 3 %.
Résultat : `tests/hardware/terrain_order_20261025_to2/trial/AB_REPORT.txt`.
Art3 a été rétabli, sans NEBULA.

Le candidat suivant ajoute un cache CPU statique. Les commandes GPU restent
exactement celles du tri seul sur 1 980 caméras/LOD et 52 positions du parcours.
Les images échantillonnées sont identiques à art3. Son essai to3 a été interrompu
à la demande de l’utilisateur avant toute scène et sans arrêter art3.
La reprise autorisée to4 est terminée : 13 scènes exactes, mais gain médian
de 1,15 %, inférieur au seuil de 5 %. Le candidat n’a pas été retenu ; art3
reste affiché. Rapport : `tests/hardware/terrain_cpu_20261025_to4/trial/AB_REPORT.txt`.

Une limite de géographie héritée reste à corriger : hors du chemin qualifié,
le terrain compact peut s’écarter de la collision jusqu’à environ 2 m.
L’exploration libre complète n’est donc pas encore qualifiée.

Un correctif isolé est maintenant validé localement dans
`build/terrain_surface_20261025_r2` : collision issue des triangles réellement
dessinés, tablier cohérent, reprise de 1 960 positions et parcours complet PASS.
Les neuf vues conservent les mêmes comptes de commandes et triangles ; ce n’est
pas une mesure de débit. Les LOD éloignés restent des approximations visuelles.
Le paquet intègre aussi la sauvegarde explicite `--save chemin`, avec contrôle
des domaines numériques et remplacement atomique. Ces fonctions ne sont pas
encore chargées sur la carte ; art3 visible conserve ses limites historiques.

Les preuves locales des deux profils, les pixels sur Pro Dock, les débits et
les éventuels essais Neo sont des résultats distincts. Les anciens états et
leurs limites restent conservés dans les rapports historiques ; le précédent
texte de cet état est archivé dans `tests/content_status_20261025_pre_resume.md`.
