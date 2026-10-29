# Patrouille des comètes — module indépendant v1

Le vaisseau, ses projectiles, les ennemis, leurs tirs et les bonus sont des
acteurs déterministes. `l3_shooter.h` et `.c` sont indépendants des cinq
moteurs initiaux et de Simon ; aucune API ni sauvegarde existante ne change.
Aucun GPU, flottant, tas ou matériel n'est utilisé.

## Règles

Piloter avec les directions **maintenues** ; maintenir Action pour tirer
toutes les huit simulations. Un front Action déclenche aussi un tir si le
canon est prêt. Les fronts directionnels seuls ne déplacent pas le vaisseau
en l'absence de `held`. Le déplacement est borné par les bords de l'arène.
Retour renvoie EXIT sans modifier le moindre octet ; victoire/défaite
figent l'état. `init` recommence une partie reproductible avec la même graine.

La première vague contient trois appareils à descente verticale. La seconde
ajoute quatre ennemis en zigzag ou en balayage ; le gardien final se déplace
latéralement et tire des éventails dirigés vers le joueur. Un ennemi normal
demande deux impacts, le boss vingt-quatre. Le vaincre gagne la partie.
Les ennemis qui quittent le bas de l'arène coûtent une vie si le joueur n'est
pas protégé. Les collisions suivent les mêmes règles pour un joueur et la
démonstration.

Trois vies,120 pas de protection au départ et après une vie perdue. Les
ennemis libèrent un bonus toutes les deux destructions : bouclier300 pas,
cœur plafonné à trois vies, ou double tir360 pas. Une destruction, un impact
sur le joueur ou un bonus retiré du plateau ne peut être compté deux fois.
Les couleurs et types de bonus sont explicités dans la vue, avec les temps
restants. Les récompenses du monde demeurent du ressort de l'intégrateur.

## État, temps et rendu

État entier1536 octets, sans pointeurs, à conserver opaque. Temps interne
60Hz avec phase fractionnaire persistante ; `dt_ms` plafonné à250ms. Pour
comparer plusieurs fréquences d'appel, garder les mêmes intervalles de
contrôles maintenus et les mêmes instants de fronts. Les pauses de menu ne
transmettent pas de durée. Les sauvegardes gardent aussi la cadence de tir,
les trajectoires, projectiles et protections.

L'arène logique mesure160×192. Les positions sont les centres en unités de
1/256 pixel logique ; ce sont des données de simulation, distinctes de la
résolution de l'écran. La vue fournit45 acteurs maximum : joueur, huit
emplacements ennemis,32 projectiles partagés et quatre bonus. Chaque acteur
porte type, identité stable tant qu'il est vivant, position, vitesse, points
de vie, demi-tailles et couleur logique0..15. Sur le joueur, flags1=bouclier,
flags2=double tir. L'intégrateur peut interpoler ces centres et dessiner ses
propres sprites ; il ne doit pas réinjecter l'interpolation dans l'état.

Les pools ont une taille fixe. Une création lorsque son pool est plein est
abandonnée de façon déterministe. Aucun dépassement, réallocation ou tableau
variable n'est utilisé. Les identités sont recyclées seulement lorsqu'elles
ne sont plus portées par un acteur actif.

Le codec écrit1552 octets little endian : signature `L3SH`, version1,
taille1536, FNV-1a32, puis32 mots de métadonnées et les44 entités de huit
mots. Il valide dimensions, bornes, identités uniques, pools et types,
comptage apparus/détruits/échappés, vagues, phases et statut. Un refus ne
modifie pas la destination. L'empreinte détecte les corruptions accidentelles,
sans prétendre signer les parties contre la triche.

## Preuves locales

`l3_shooter_demo_input` fournit des directions et tirs ordinaires, en visant
les ennemis et en esquivant les projectiles. Il ne modifie pas l'état. Le
témoin `tests/traces/shooter_win.trace` contient l'en-tête
`L3SHOOTERTRACE 1 1`, puis les commandes `pressed held dt_ms`. La graine1
gagne en120 appels, sans perdre de vie, avec huit ennemis détruits et2000
points ; le temps interne terminal est11916ms.

```sh
python3 games/luma3d/minigames/tests/run_arcade_tests.py --module shooter \
  --out games/luma3d/minigames/tests/results/<nom-unique>
```

La suite vérifie64 graines victorieuses, six fréquences d'appel, la reprise
exacte au milieu des tirs, les limites du pool32, les doubles impacts sur un
ennemi, la protection après une mort, le bonus consommé une seule fois, la
défaite et le redémarrage, chaque troncature et octet corrompu, et50000
appels aléatoires bornés. Compilation C99 stricte et AddressSanitizer/UBSan ;
LeakSanitizer reste désactivé à cause du moniteur `ptrace`. Ces essais ne
qualifient ni l'intégration des sprites ni une carte ou son FPGA.
