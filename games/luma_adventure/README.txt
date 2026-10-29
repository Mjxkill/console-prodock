LUMA — Les Jardins du Souvenir
Prototype jouable original, code partagé PC / Pro Dock / Neo

État laissé sur la Pro Dock — 24 octobre 2026
--------------------------------------------
À la demande explicite de l'utilisateur, LUMA reste maintenant visible et
en marche après une démonstration réussie : ne plus restaurer automatiquement
NEBULA. Les restaurations décrites plus bas sont les faits des anciens essais.
Dernière vérification : PID 1343, extérieur 2 « Marées », --demo --no-save,
déplacements et tirs automatiques, sans prérequis de progression injectés.
Ce mode existant anime une scène ; il ne visite pas toute la campagne.
Les cinq compteurs GPU sont nuls ; CDC et verrou de diagnostic sont libérés.
Preuves : tests/hardware/live_20261024_r9b_marees/confirmed/result.json.

Depuis la console série Linux, pour prendre les commandes de cette zone :
kill -TERM `cat /tmp/luma-live.pid`
sleep 1
/tmp/luma-riscv --world 2 --no-save

WASD/flèches : déplacement ; E : interaction ; espace : épée ; F : arc ; Q : quitter.
Pour revoir la première salle optique, utiliser --world 26 au même lancement.
Ajouter --demo pour les mouvements/tirs automatiques (Ctrl-C arrête ce mode
lorsqu'il est lancé au premier plan). Seules les régions 2/22/26/27/35 sont
installées dans /tmp : aperçu ciblé, pas encore la campagne entière sur carte.
Le monde 0 n'est pas retransféré pour éviter de retarder l'affichage demandé.

État honnête
-----------
Le moteur et les données de campagne sont jouables : exploration libre,
combat à l'épée et à l'arc, habitants, coffres, enquêtes, choix, itinéraires,
progression persistante entre régions et huit modes de déplacement.
Les mécaniques de sanctuaire comprennent interrupteurs, cibles à l'arc,
caisses, dalles, portes, séquences, circuits de lampes, tourelles et réseaux
de lumière à miroirs orientables. Les caisses peuvent masquer les faisceaux.
Trente salles réparties dans trois sanctuaires sont intégrées aux six régions
(36 cartes au total). Le parcours des 96 missions et de ces salles passe par
les commandes de jeu, sans téléportation de diagnostic ni inventaire injecté : 2 966,3 secondes
simulées, soit 49,4 minutes avec toutes les solutions connues, sans lecture ni
recherche. Ce résultat prouve un parcours, pas une durée humaine. La cible de
conception de 6–10 heures n'est PAS acquise ; les autres sanctuaires et une
campagne plus substantielle restent à construire et à éprouver.
La Poste des Reflets ouvre une galerie entre deux quais au retour du joueur ;
le parcours vérifie ce raccourci dans les deux sens, sans répéter sa récompense.
Après le dénouement, E ou Start ferme l'écran final et permet de poursuivre
l'exploration. Les voyages et sauvegardes conservent la fin du récit obtenue.

Le village utilise des textures, habitants et décors générés dans ComfyUI,
avec sources et provenance dans art/. Les mécanismes des sanctuaires ont des
silhouettes et états distincts. Les cinq icônes optiques sont encore des
dessins procéduraux provisoires ; certaines animations restent provisoires.
Les musiques YuE2 existent mais attendent une
écoute de validation : aucun cue non qualifié n'est joué automatiquement.

Exécution PC (depuis ce dossier)
--------------------------------
make indexed
./build/indexed/luma

Compilateur C, SDL2 via pkg-config, Python3, NumPy, Pillow et liblz4 sont nécessaires.
Le constructeur produit un petit paquet commun et un paquet par région.
Une seule région est chargée à la fois. La logique et les données sont les
mêmes dans le frontend PC et le binaire RISC-V ; le PC émule les commandes,
couches et sprites réellement soumis au GPU de la carte.

Touches : WASD/flèches déplacer ; E parler/utiliser/pousser/orienter ; espace épée ;
F ou X arc ; V ou Tab véhicule ; 1/2/3 réponse ; M carte ; J carnet ;
H aide ; P pause ; R recommencer une salle ; Q ou Échap quitter.
La sélection d’une caisse privilégie la direction regardée.
La remise à zéro conserve les trésors, clés et ennemis vaincus et restaure
les caisses, miroirs et mécanismes de la salle. Les véhicules sont interdits dedans.
Les cycles de marche animés sont actuellement frontaux ; les orientations
dos/profils utilisent des poses statiques cohérentes.
Les manettes PC reconnues par SDL sont ouvertes et suivies à chaud :
stick/croix déplacer, A parler, X épée, B/RB/gâchette droite arc, Y véhicule,
Retour carte, LB carnet, Start pause, clic droit aide. Dans une énigme :
A/B/X répondent 1/2/3. Clic gauche réinitialise une salle intérieure.
Les tests utilisent une vraie manette virtuelle SDL ; l'essai avec une
manette physique et les commandes complètes sur carte restent à faire.

Options utiles :
./build/luma --no-save --headless --frames 1 --snapshot build/vue.ppm
./build/luma --no-save --720p --headless --frames 1
./build/luma --save /chemin/persistant/luma.sav
./build/luma --audition audio/renders/previews/pilot_a_free_loop.wav
./build/luma --mute

Sauvegardes
-----------
Le fichier PC par défaut est luma.sav dans le répertoire courant.
Sur carte, le défaut /tmp/luma.sav est VOLATIL et disparaît au redémarrage.
Pour une vraie partie longue, fournir explicitement --save avec un chemin
persistant disponible. Aucun stockage SD n'est créé ou écrit par les essais
matériels de ce prototype (ils utilisent --no-save).

Format v5 (lecture v4 et v5) : identifiants stables de monde/entité/mission, CRC, écriture dans
un fichier temporaire exclusif à nom unique, fsync, renommage atomique et
fsync du dossier. Un ancien fichier temporaire ne bloque pas une nouvelle
sauvegarde. La migration depuis le véritable lecteur/écrivain R5 v4 (26 cartes)
vers les 36 cartes conserve inventaire, santé, trésors et les 15 missions
inchangées du chapitre 3 ; c17 n'hérite pas de l'ancienne complétion de c16.
Les orientations des miroirs et les positions des caisses sont persistantes.
L'ancien lecteur R5 refuse un carnet v5 sans le réenregistrer ni le modifier.
Le réordonnancement des données conserve les découvertes ; les identifiants
supprimés sont ignorés avec notification. Une ancienne sauvegarde de prototype
incompatible ou un fichier invalide est refusé sans l'écraser. Cette stratégie
n'est pas une migration universelle des règles de quête : toute modification
du sens d'un drapeau doit être accompagnée d'une migration explicite.

Vérification
------------
make test
make test-indexed
python3 tools/test_save_upgrade.py --baseline-world tests/hardware/trial_20261024_r5/generated_world.c --world 2
python3 tests/reference_capture.py build/reference_800
python3 tests/reference_capture.py build/reference_720
python3 audio/test_sdl_backend.py

Les captures de référence se créent avec --capture PREFIX. Elles contiennent
les commandes, la scène et la mémoire nécessaires au modèle indépendant.
La comparaison actuelle passe sur chaque pixel en 800×480 et 1280×720.
Elle contrôle aussi les réservations Linux R17 : palette 240–255 nulle,
couches 12–15 inactives et priorités de sprites inférieures à 12.
Les tests couvrent logique déterministe, progression, corruption/reprise des
sauvegardes, événements d'entrée à fréquence de rendu différente, mécaniques
et parcours par commandes de jeu. Aucun de ces tests PC ne qualifie la Neo.

Compilation et essais carte
---------------------------
make riscv

Les binaires de ce dossier sont des CANDIDATS isolés. Ils ne remplacent ni
l'image Linux ni le FPGA de référence G22r0 / NEBULA R17. L'inventaire global
et l'intégration aux constructeurs Linux restent à coordonner séparément.

Pro Dock r1 : transfert validé, échec avant rendu sur la palette réservée
240..255 du pilote texte Linux. Cause corrigée dans le candidat suivant.
Pro Dock r2 : 600 images en 77,895 secondes, soit 7,70 FPS chargement
initial inclus ; zéro erreur GPU, underflow, couche/sprite invalide ou fault.
NEBULA a été restauré et son processus vérifié après cinq secondes lors de cet essai.
Ce débit inclut le chargement et ne mesure pas la cadence établie.
R2perf2, mêmes ressources avec cache sémantique du HUD : 600 images après
120 images d’échauffement, console silencieuse, 42,01 FPS moyens.
Le p95 est inférieur ou égal à 37,5 ms, p99 à 53,9 ms, maximum 72,284 ms ;
158 images sur 600 dépassent 33,333 ms. La cible de 30 FPS réguliers
n’est donc pas encore démontrée. Le panneau G22r0 tourne à environ 55 Hz.
R3 (village_r6) passe sur Pro Dock : 41,90 FPS moyens, p95 <=37,4 ms,
p99 <=47,9 ms, 164/600 images au-delà de 33,333 ms ; aucune erreur GPU.
NEBULA a été restauré après R3. Voir tests/hardware/trial_20261024_r3/REPORT.txt.
La lecture physique du LCD par une personne reste à confirmer. Voir tests/hardware/trial_20261024_r2/ ; résultat
matériel et identités sont distincts du dernier rendu PC. Aucun résultat de ce dossier
n'autorise à annoncer que le dernier code est qualifié sur les deux cartes.
Neo : essais matériels du jeu en attente.

Les essais historiques tools/prodock_trial.py et tools/prodock_scene_trial.py
ont tourné sur ax15 avec verrou diagnostic et accès série exclusif, transferts
uniquement dans /tmp avec CRC par bloc et CRC final, puis essais bornés et
restauration de NEBULA. La préférence actuelle de maintien de LUMA est indiquée
en tête de ce document. Aucun flash, rechargement FPGA/noyau ni écriture SD.
Le bitstream actif est identifié par continuité de la restauration documentée
et SHA de sa référence ; il n'existe pas de registre de hash matériel lu ici.

Audio : lecteur SDL réel avec fondu, pause et chargement WAV ; le frontend
carte utilise un backend silencieux car aucun pilote audio Linux réel n'est
qualifié. Les fichiers generated sont uniquement écoutables explicitement
avec --audition ; seuls les cues ready entrent dans la sélection automatique.

Candidat de défilement indexé (séparé du rendu RGB565)
----------------------------------------------------
make indexed
./build/indexed/luma --assets build/indexed/luma.pak
make indexed-riscv

Le paysage utilise la couche de tuiles 32×32 du GPU et ses registres de
scrolling ; aucune copie du paysage n'est soumise pendant une image normale.
Les effets utilisent une surface transparente avec mises à jour des seules
lignes modifiées, indépendante pour chaque page. La palette commune au fond,
aux acteurs et au HUD change certaines couleurs : la comparaison
build/indexed/compare_village.png conserve ce compromis visible.

Les tests locaux passent avec le compositeur GPU indépendant pour les deux
résolutions, les projectiles/particules/épée, deux pages réutilisées, menus,
clipping et changement de salle. ASAN/UBSAN passent également. Le candidat
matériel R4 est figé dans tests/hardware/trial_20261024_r4 ; sa mesure (51,67 FPS, p95 <= 31,4 ms, 23 images lentes sur 600)
ne vaut que pour ses SHA et la région 0. NEBULA avait été restauré. Le seuil moyen/p95
de 30 FPS passe sur cette scène ; des saccades ponctuelles restent présentes. La correction ultérieure
des transitions affiche une scène de chargement sans couches avant de réécrire
la région active ; cette correction n'appartient pas au candidat R4.

Le HUD conserve un cache CPU par page et copie seulement les mots modifiés ;
les changements d'endurance n'imposent plus de recopier tout le panneau.
L'option --benchmark-vehicle N exige --demo --no-save et une carte extérieure.
Elle déverrouille temporairement ce véhicule pour mesurer le rendu : ce mode
de diagnostic ne démontre pas la progression permettant de le gagner.

Mesures comparées du 24 octobre — rendu retenu R5
------------------------------------------------
Chaque scène a 120 images d’échauffement et 600 images mesurées sans commande
UART pendant la fenêtre. G22r0 et Linux R17 restent inchangés.

Scène R5       FPS moyens   p95 <=      Images > 33,333 ms
Marche         52,93        22,5 ms     13 / 600
Cheval         51,44        31,6 ms     25 / 600
Salle 22       49,51        35,5 ms     44 / 600

Le critère moyenne >= 30 FPS et p95 <= 33,333 ms passe dans les deux premières
scènes, mais manque encore dans le sanctuaire. Des saccades restent présentes.
Le cheval est déverrouillé uniquement dans le diagnostic ; la salle 22 démarre
directement. Ce sont des mesures du moteur, pas un parcours matériel complet.
Les variantes R6/R7 (cache d’effets comparé) et R8 (masque de blocs) réduisent
les octets copiés sans améliorer suffisamment les mesures. Elles sont archivées
avec leurs échecs de performance ; le chemin R5 est conservé.
NEBULA a été restauré après chacun de ces essais, avec compteurs propres.
Voir tests/hardware/trial_20261024_r5/REPORT.txt et tests/hardware/performance_comparison_20261024.json.

Le dernier code local ajoute les réseaux optiques, leur sauvegarde v5, les dix
salles de la Poste des Reflets, sa galerie et la poursuite de l'exploration après
le récit. Il corrige aussi le recalcul des dalles avant une interaction ou une
reprise : une source ne peut garder l'ancien état d'une dalle quittée.
Les tests PC couvrent ces règles, les deux pages de rendu des faisceaux et la
conservation des sprites du héros dans une scène dense. Les binaires PC et
RISC-V compilent. R9b teste ensuite sur Pro Dock des scènes optiques et leurs
interactions ; la campagne entière et la Neo restent en attente.
R5 et les preuves négatives R6–R8 restent figés ; NEBULA avait été restauré
à l'issue de ces essais.
Voir tests/local/reflections_20261024/REPORT.txt pour les preuves du lot local.

R9b — optiques et retour galerie sur Pro Dock
-------------------------------------------
Le jeu est exactement celui du lot local figé. Trois fenêtres de 600 images
après 120 d'échauffement, sans commande UART : salle 22 à 48,91 FPS / p95
<= 36,2 ms ; salle 26 à 49,57 FPS / p95 <= 36,0 ms ; salle 35 à 47,25 FPS /
p95 <= 36,8 ms. Les trois critères de régularité à 30 FPS restent en échec.
Tous les compteurs GPU sont nuls, les processus se terminent normalement.

Un exécutable fonctionnel séparé, avec le même moteur/rendu, résout réellement
la première salle puis la dernière et traverse la galerie dans les deux sens.
Son départ est direct et les anciennes missions extérieures sont semées pour
la seconde fixture. Son rendu tous les quatre pas et à chaque interaction
ne mesure pas une cadence normale. Aucun contrôle physique de manette testé.
Le retour extérieur charge sa région en environ 5,44 s, limite encore visible.
Seules les régions 2/22/26/27/35 ont été transférées dans /tmp ; ce n'est pas
une installation de toutes les cartes sur la cible. Aucune sauvegarde écrite.
NEBULA a été restauré et vérifié après cinq secondes au terme de R9b ;
FPGA/noyau/SD inchangés. Le lancement visible ultérieur laisse désormais LUMA.
Voir tests/hardware/trial_20261024_r9b/REPORT.txt et ses journaux identifiés.
