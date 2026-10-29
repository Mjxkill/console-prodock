# Carillon des quatre couleurs — module indépendant v1

`l3_simon.h`/`.c` ajoute le jeu de mémoire demandé sans modifier les cinq
moteurs, leur header ou leurs sauvegardes. État opaque de 112 octets,
sauvegarde explicite little endian de 128 octets, signature `L3SM`, version1,
empreinte FNV-1a et validation transactionnelle stricte. Le jeu n'utilise
aucun tas, GPU, flottant ou accès matériel.

Les directions représentent quatre couleurs : Haut rouge, Droite vert,
Bas bleu, Gauche jaune. Le carillon joue sa séquence, puis attend qu'on la
répète dans le même ordre. Chaque réussite ajoute une couleur, jusqu'à huit.
Une mauvaise couleur, un mauvais ordre ou deux fronts de couleurs simultanés
terminent l'essai. Les lanternes sont allumées 600ms, séparées par 250ms de
silence ; la bonne réponse reçoit un retour visuel de 240ms. Une pause de
600ms marque chaque manche réussie. Les séquences sont reproductibles à
graine identique.

Les fronts reçus pendant la démonstration sont ignorés. Une touche tenue ne
produit jamais de réponse à la transition vers la saisie. `held` est accepté
pour conserver le contrat d'entrée commun, mais ne répète aucune couleur.
`pressed` doit contenir uniquement les nouveaux fronts fournis par
l'intégrateur. La conversion n'ajoute aucun front caché. Retour demande la
sortie avec un état identique ; il n'accorde aucune récompense. Les statuts
WON/LOST se figent, le redémarrage passe par `init` et la reprise par le
décodeur. Les appels sont plafonnés à250ms ; les décompositions d'une même
durée donnent le même état lorsque les fronts arrivent aux mêmes instants.

`L3SimonView.grid` contient quatre cases en2×2, pas20, et les chaînes de
commandes. `phase` précise INTRO/SHOW/GAP/INPUT/ROUND_OK/ERROR/COMPLETE.
`active_color` vaut0..3 ou4 pour aucune ; `sequence_length`, `input_index`,
`phase_ms` et `feedback_ms` permettent le signal « écouter / à vous » et
l'animation. Le moteur ne joue pas de son et ne gère pas la récompense du
monde ; l'adaptateur peut ajouter quatre notes correspondant aux couleurs.

`l3_simon_demo_input` renvoie uniquement les commandes ordinaires et attentes
nécessaires. Le témoin `tests/traces/simon_win.trace` gagne avec36 fronts
et35400ms, sans écrire le statut. Son en-tête est `L3SIMONTRACE 1 1` (version,
graine), puis les lignes sont `pressed held dt_ms`.

```sh
python3 games/luma3d/minigames/tests/run_arcade_tests.py --module simon \
  --out games/luma3d/minigames/tests/results/<nom-unique>
```

Les tests couvrent64 graines victorieuses à6 cadences, les fautes de couleur
et d'ordre, les fronts simultanés, les touches maintenues à travers les
phases, les pauses/reprises au milieu de flashes et de saisies, chaque
troncature et octet corrompu, et20000 appels aléatoires bornés. Compilation
C99 stricte, puis AddressSanitizer/UBSan. LeakSanitizer est désactivé à cause
du moniteur `ptrace`, comme pour le lot des cinq moteurs. Ces preuves hôte
ne qualifient ni une intégration graphique, ni le FPGA, ni une carte.
