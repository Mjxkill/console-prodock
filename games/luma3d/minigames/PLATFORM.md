# La tour des rouages — module indépendant v1

Le moteur `l3_platform.h`/`.c` simule un parcours original de plateformes
avec trois coordonnées : x horizontal, y hauteur, z profondeur. Il expose
sa géométrie et ses acteurs pour le rendu3D, sans écrire un pixel et sans
modifier les cinq moteurs initiaux, Simon ou le shooter. Aucune allocation,
aucun flottant, aucune dépendance GPU ou matérielle.

## Jouer

Cinq niveaux aux hauteurs0,32,64,96,128 ; quatre échelles alternent à droite
et à gauche. Les niveaux1 et3 comportent un trou central. Gauche/Droite
maintenus déplacent le joueur en x. Haut/Bas maintenus déplacent la profondeur
z, ou font monter/descendre lorsqu'on est aligné avec une échelle. Un front
Action déclenche un saut ; maintenir Action ne répète pas les sauts.

La gravité produit une vraie trajectoire. Un saut trop court laisse tomber
sur la plateforme inférieure. Les tonneaux roulent sur leur niveau, tombent
aux extrémités ou dans les trous et continuent à l'étage inférieur. Leurs
trois couloirs de profondeur permettent aussi des esquives latérales. Les
collisions tiennent compte des trois axes ; sauter ou grimper change donc
réellement les contacts possibles.

Trois vies ;120 pas de protection après un choc. Le relais du niveau2
mémorise un point de reprise : un choc ultérieur y replace le joueur, en
conservant le relais et le meilleur étage atteint. Le fanal en haut à droite
accorde la victoire une seule fois lorsqu'on l'atteint au sol. Le score
dépend du meilleur étage, du relais et du fanal, jamais du nombre de
repassages. Retour demande la sortie avec un état strictement identique et
sans récompense ; `init` recommence, `decode` reprend.

## Contrat d'intégration

État opaque384 octets. Positions en unités1/256, x borné8..152, z borné8..56,
y positif vers le haut. La vue contient sept surfaces rectangulaires, quatre
échelles et au plus onze acteurs : joueur, fanal, relais, huit tonneaux.
Les surfaces et trous sont ceux des collisions ; ils peuvent être extrudés
pour le rendu. Pour le joueur, flags1=air,2=échelle,4=protection. Pour un
tonneau, flags1 indique une chute ; pour fanal/relais, flags1 indique acquis.
Les positions du joueur sont ses pieds, celles des tonneaux leur base.

Le temps avance à60Hz, avec phase fractionnaire conservée, `dt_ms` plafonné
à250. Les fronts de saut sont traités une fois, même avec `dt=0`. Les
directions restent des contrôles maintenus. La vue permet une interpolation
visuelle ; la simulation ne doit recevoir que les commandes et le temps,
pas les positions interpolées du rendu.

Les huit emplacements de tonneaux sont fixes. Lorsqu'ils sont tous occupés,
la tentative d'apparition est abandonnée sans modifier les entités ni leur
compteur. Les identités actives restent uniques. Le codec écrit400 octets
little endian : `L3PF`, version1, taille384, FNV-1a32,32 mots de métadonnées
puis huit tonneaux de huit mots. Validation des bornes, statuts, compteurs,
score, relais, position dans l'échelle, trajectoire et identités avant toute
écriture de destination. L'empreinte vise la corruption accidentelle, sans
protection cryptographique contre la triche.

## Démonstration et preuves

Le conseiller `l3_platform_demo_input` suit les échelles, saute les trous et
essaie ses commandes sur une copie avec les mêmes règles pour anticiper un
choc. Il ne modifie jamais l'état fourni et n'écrit aucun drapeau de victoire.
Le témoin `tests/traces/platform_win.trace` commence par
`L3PLATFORMTRACE 1 1`, suivi de `pressed held dt_ms`. À la graine1 il atteint
le sommet en107 commandes et9783ms, avec cinq sauts, trois vies et1650 points.
Ce parcours court démontre les règles ; il ne représente pas plusieurs
heures de contenu ou une campagne complète.

```sh
python3 games/luma3d/minigames/tests/run_arcade_tests.py --module platform \
  --out games/luma3d/minigames/tests/results/<nom-unique>
```

Tests :64 graines victorieuses, six cadences identiques, sauts et gravité,
trou franchi ou chute réelle, échelles dans les deux sens, profondeur,
réapparition au relais, récompense unique, pool de huit tonneaux saturé,
défaite naturelle/redémarrage, reprise pendant une ascension et à fraction
de pas non nulle, chaque sauvegarde tronquée ou octet corrompu, données
sémantiques invalides à empreinte recalculée,50000 appels aléatoires bornés,
et relecture de la trace indépendante du conseiller. C99 strict puis
AddressSanitizer/UBSan ; LeakSanitizer désactivé à cause du moniteur `ptrace`.
L'intégration3D, les contrôles globaux des deux profils, la synthèse, le timing
et les essais carte restent des preuves distinctes de ces tests hôte.
