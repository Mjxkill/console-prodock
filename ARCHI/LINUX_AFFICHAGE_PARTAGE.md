# Linux : jeu, terminal texte et diagnostics sur le LCD

Implémentation du 11 octobre 2026. Elle utilise le compositeur, les tuiles et
le scanout RGB565 déjà présents dans G22r0. Aucun nouveau RTL ni bitstream
n'est requis. L'état des essais physiques est consigné séparément dans
`TESTS/LINUX_DESKTOP_20261011.md`.

## Dispositions

LCD 800 × 480, police 8 × 16 :

```
          400 pixels                   400 pixels
┌──────────────────────────┬──────────────────────────┐
│                          │                          │
│ Jeu 400 × 240            │ Terminal Linux 50 × 15  │ 240
│                          │                          │
├──────────────────────────┴──────────────────────────┤
│ Diagnostics GPU / LCD / USB / SD : 100 × 15         │ 240
└─────────────────────────────────────────────────────┘
```

- `prodockctl layout split` : disposition ci-dessus.
- `prodockctl layout game` : jeu plein écran. Une source 400 × 240 est
  doublée matériellement ; une source 800 × 480 reste native.
- `prodockctl layout console` : terminal Linux 100 × 30 caractères.

Les modes changent au retour vertical. Un jeu continue à s'exécuter quand
le terminal occupe tout l'écran. Quitter un jeu affiché en plein écran rend
la disposition partagée. Changer de disposition ne ferme pas le programme.
Le terminal est redimensionné par fbcon ; la taille du pseudo-terminal du
shell est ensuite mise à jour, avec SIGWINCH au processus de premier plan.

## Véritable chemin texte matériel

Le pilote adopte l'interface **fbcon tileblit** déjà employée par le projet
voisin `logic_analyser_wifi`. Les callbacks transmettent des caractères,
couleurs, copies de cellules et curseur ; ils ne produisent pas de pixels.
Le GPU Pro Dock compose les glyphes via ses couches de tuiles DDR3, plutôt
que via les registres texte spécifiques au FPGA de l'analyseur.

Chaque caractère de 8 × 16 utilise deux tuiles de 8 × 8. Deux couches par
console permettent 16 couleurs de premier plan et 16 couleurs de fond :
une grille de fonds opaques et une grille de glyphes transparents. Le curseur
inverse les deux couleurs de sa cellule. L'interprétation ANSI, les retours
à la ligne et le défilement logique appartiennent au terminal Linux ;
la lecture des glyphes, le découpage des fenêtres et la composition sont
matériels. Ce n'est pas une boucle CPU qui redessine un framebuffer texte.

La police de 4 096 octets est développée en atlas de 512 Kio uniquement lors
d'un changement de police. Les cellules utilisent deux octets (caractère,
premier plan, fond), les grilles GPU deux entrées de 16 bits par caractère
et par couche. Chaque groupe de grilles et chaque atlas a deux banques.
Le pilote écrit la banque inactive, publie le cache A25 par SBI, présente
les nouveaux descripteurs et attend l'acquittement au retour vertical.
L'ancienne banque n'est réutilisée qu'après cet acquittement. La palette
reste une ressource globale ; son remplacement n'est pas atomique avec les
grilles, comme dans l'ABI matérielle existante.

## Propriété des ressources

Le pilote unique sérialise les commandes, les échanges de grilles et les
présentations ; un seul processus possède `/dev/prodock-gpu` à la fois.
`/dev/prodock-display` est indépendant de cette exclusivité : le terminal
et le contrôle des dispositions continuent à fonctionner pendant le jeu.
Ces deux interfaces sont réservées à root, avec contrôle de capacité.

| Ressource | Attribution sous Linux |
|---|---|
| Fond RGB565 | Jeu ; page noire en l'absence de jeu |
| Couches 0 à 11 | Jeu |
| Couches 12 et 13 | Fond et glyphes du terminal |
| Couches 14 et 15 | Fond et glyphes des diagnostics |
| Sprites | 64, priorité inférieure à la couche 12 |
| Palette 0 à 239 | Jeu |
| Palette 240 à 255 | Consoles texte |
| `0x00800000..0x05E00000` | 86 Mio accessibles à l'application |
| `0x05E00000..0x06000000` | 2 Mio privés du gestionnaire d'affichage |

Les couches des consoles disparaissent en plein écran jeu. Elles restent
réservées pour permettre le retour au partage sans reconfigurer le jeu.
La séparation masque matériellement les pixels et sprites du jeu sous les
consoles. Un jeu natif 800 × 480 est découpé en mode partagé ; pour voir toute
sa scène dans le quart supérieur gauche, il doit rendre en 400 × 240.

Pour une source 400 × 240, PRESENT emploie `format=7`, un pas de **1 600
octets minimum** et une allocation de 480 lignes. Le scanout du mode partagé
lit des lignes entières de 800 pixels et les couches opaques cachent la partie
inutilisée. Le mode jeu active le doublement matériel en utilisant les mêmes
adresses et le même pas. Le pilote refuse une allocation trop courte.
L'API renvoie les bornes actualisées dans INFO ; mmap et les validateurs de
commandes/surfaces refusent les 2 Mio privés. Les couches ou priorités de
sprites réservées produisent une erreur. Les entrées 240..255 du paquet
PALETTE doivent être nulles ; seules les entrées 0..239 sont appliquées.

## Shell et exécutable

`prodock-terminal` relie l'entrée série USB CDC à un pseudo-terminal Linux.
Le shell possède ce pseudo-terminal comme terminal de contrôle. Sa sortie
est envoyée à la console série et à `/dev/tty1`, où le terminal natif Linux
interprète les séquences ANSI. Ctrl-C, les processus de premier plan, les
lancements en arrière-plan et le redimensionnement restent ceux de Linux.
Il ne s'agit pas d'un interpréteur de commandes ajouté au firmware.

Exemples :

```sh
prodock-game                         # casse-briques jouable : A/D, flèches, Q
prodock-game --demo                  # jeu autonome
prodock-game --demo --frames 600 &    # shell disponible pendant le jeu
prodockctl layout game
prodockctl layout console
prodockctl layout split
prodockctl display
```

Le jeu d'intégration est un ELF RV32 lié avec la musl adaptée à l'A25. Linux
calcule les collisions et reçoit les touches ; les effacements et rectangles
sont exécutés par l'accélérateur FPGA. Les autres démos bare-metal restent
disponibles dans leur mode séparé ; ceci ne convertit pas automatiquement
leurs exécutables en programmes Linux. L'ABI géométrie G3D1 reste à exposer
et à valider dans le pilote Linux, qui accepte actuellement les opcodes 1–30.

Le bandeau de diagnostic est actualisé chaque seconde. Les FPS correspondent
aux PRESENT réussis du jeu, la fréquence LCD au compteur de trames matérielles,
et le débit de commandes aux commandes effectivement envoyées par le pilote.
Les erreurs, les sous-alimentations et le maximum de cycles par ligne sont
lus dans le FPGA. L'état USB provient des registres UMSC en lecture seule ;
les compteurs SD sont ceux de `/sys/block/mmcblk0/stat`. Aucun accès SD
supplémentaire n'est déclenché pour afficher ces informations.

### Tableau de bord R13

La révision logicielle R13 remplace les lignes brutes par trois tableaux
encadrés dans la grille 100 × 15. Les bordures, voyants et barres utilisent
les glyphes de la police VGA 8 × 16 et les couches de tuiles déjà réservées
aux diagnostics. Le rafraîchissement reste limité à une fois par seconde ;
le pilote ne republie que les paires de cellules qui ont changé.

| Tableau | Valeurs et représentation |
|---|---|
| GPU / affichage | FPS du jeu, Hz LCD, commandes/s, total des commandes, maximum de cycles par ligne, masque d'erreurs, faute du pilote, sous-alimentations, couches et sprites invalides |
| USB / console | Liaison HS et vitesse négociée, console CDC/UART2, perte FIFO MSC, resets mémorisés, disque USB servi/inactif, registre brut |
| SD / stockage | Présence, capacité, secteurs, lecture/écriture en Kio/s et volumes cumulés lus/écrits |

Les voyants verts indiquent un état normal, orange une vigilance ou une
mesure indisponible, rouges un défaut. Un GPU sans nouvelle présentation
est indiqué au repos, en gris. Le voyant global reprend le défaut ou
l'avertissement des trois tableaux. Les erreurs matérielles mémorisées
restent visibles ; le tableau ne les efface pas.

Les trois types de barres ont des unités explicites :

- **Fluidité** : présentations du jeu divisées par les trames LCD sur la
  période écoulée. Ce rapport n'est pas un taux d'occupation du GPU. Sous
  80 % avec un jeu actif, le voyant GPU passe orange.
- **Ligne max** : pic matériel des cycles de composition rapporté au budget
  de 2 556 cycles de cette configuration G22r0. Vigilance à 80 %, barre
  rouge à 90 %, défaut à partir de 100 %. C'est un maximum mémorisé, pas
  une moyenne calculée sur la dernière seconde.
- **SD** : débit des compteurs de secteurs Linux, avec une échelle fixe
  de 1 Mio/s. Une barre sature à son maximum mais la valeur numérique peut
  dépasser ce maximum. Elle ne représente ni la capacité utilisée ni un
  débit maximal qualifié de la carte.

`480 Mbit/s` est la vitesse USB négociée, pas une mesure du débit utile.
Les bits UMSC 2/3 sont des resets USB/BOT **mémorisés**, pas des resets en
cours. Le bit 7 signale une perte de FIFO **MSC** ; ce registre ne constitue
pas un compteur des erreurs du CDC. L'état inconnu `0xffffffff` apparaît
orange, sans inventer des défauts pour chaque bit. Une déconnexion est
orange ; une liaison connectée sans HS, une perte MSC ou un endpoint MSC
bloqué sont rouges.

Les taux utilisent le temps monotone réellement écoulé. Le rebouclage des
compteurs matériels 32 bits est pris en compte. Les données SD absentes,
les compteurs réinitialisés ou une capacité modifiée donnent `--` pour le
débit, jusqu'à obtenir deux échantillons comparables. Les commandes
utilisent le compteur logiciel 64 bits. Le pilote, l'ABI, le FPGA et les
ressources graphiques réservées ne changent pas pour R13.

## Concurrence et limites

Les callbacks fbcon ne dorment pas et ne touchent pas le bus matériel.
Ils protègent leur image des cellules par un spinlock et programment un
travail différé. Le worker tient le mutex GPU pendant la publication.
Le chemin GPU ne prend jamais `console_lock`, ce qui évite l'inversion
avec les callbacks de console. Les opérations de disposition ont leur
propre mutex et prennent `console_lock` avant de redimensionner fbcon.

Les jeux sont des applications de confiance ; ce GPU sans MMU ne fournit
pas d'isolation matérielle générale. Le terminal actuel est piloté depuis
le CDC HS, pas par un clavier branché à un contrôleur USB hôte du FPGA.
Le chargement Linux de validation reste volatil en DDR/ILM. L'installation
SD et le démarrage autonome sont les étapes distinctes décrites dans
`LINUX_PRODOCK.md`. G22r0 conserve son statut de build expérimental côté
contraintes temporelles : cet ajout logiciel ne ferme pas son timing.

`/dev/fb0` est désormais réservé au fbcon interne : les ouvertures utilisateur
renvoient `EOPNOTSUPP`, plutôt que d'accepter silencieusement des écritures
pixels non affichées. Les applications utilisent `/dev/prodock-gpu` ; les
changements de disposition passent par `/dev/prodock-display`. Le plein écran
ne doit pas être obtenu en contournant le gestionnaire via un ioctl fbdev.

## Chargement de validation et coût du pilote

Le transport compact évite d'envoyer les grandes plages nulles du noyau :

```sh
python3 linux/build.py all
python3 tools/load_linux.py --pack linux/build --packed --jtag-speed 4000 --out TESTS/linux_boot_unique
```

Cette commande attend une console bare-metal identifiée et mise au repos ;
elle ne s'applique pas directement à un Linux déjà actif. Pour changer le
noyau, arrêter Linux, réinitialiser le FPGA en SRAM avec le bitstream prévu,
charger le firmware de transfert, puis lancer cette commande. Les SHA du
manifeste et les CRC avant/après décompression sont obligatoires. Aucune
installation SD ni programmation de flash n'est effectuée par ce chargeur.

Le pilote garde une copie de chaque banque de descripteurs pour éviter les
écritures MMIO inchangées. La FIFO est vérifiée avant chaque mot, avec délai
borné si pleine ; les accès du même périphérique sont ordonnés et les
barrières mémoire entourent le lot. Les maintenances de cache A25 sont
conservées. Quand un jeu présente régulièrement, ses PRESENT emportent les
modifications de texte, afin d'éviter une attente verticale supplémentaire.
Le terminal se remet à présenter seul si le jeu ne présente plus récemment.

`prodockctl display` expose aussi les temps cumulés `feed_us`, `wait_us`,
`cache_us` et `present_us`, en microsecondes modulo 2³². Ils servent à mesurer
les écarts entre deux lectures ; `present_us` comprend aussi les présentations
texte indépendantes, et n'inclut pas la construction de leurs grilles.

Les grilles texte sont initialisées intégralement une fois par banque et
par dimension de terminal. Ensuite, le pilote compare des paires de cellules
avec la copie propre à la banque inactive : chaque paire différente produit
quatre écritures de 32 bits pour les deux demi-glyphes et leurs fonds. Cela
évite de reconstruire/copier 64 Kio à chaque clignotement de curseur.
`text_us` mesure la préparation cumulée du texte avant les présentations.
Les champs USB « pertes » et « reset » affichés sont des indicateurs 0/1 du
registre matériel, pas des nombres cumulés de paquets ou de reconnexions.

## Utilisation de la version chargée

Sur ax15, ouvrir la console série (le numéro ACM peut changer après une
reconnexion) :

```sh
python3 -m serial.tools.miniterm /dev/ttyACM1 115200 --raw --eol LF
```

L'option `--eol LF` est nécessaire pour envoyer une seule validation par
touche Entrée. Par défaut, miniterm envoie CR+LF, que le shell reçoit comme
deux validations : cela affiche `prodock# prodock#`. `--raw` ne désactive
pas cette transformation des fins de ligne. Sur la carte R13, CR+LF produit
deux prompts, LF seul ou CR seul en produit un. Le relais PTY conserve les
octets reçus ; les programmes qui utilisent un terminal brut restent ainsi
compatibles. Ce réglage du client ne demande aucun rechargement FPGA/Linux.

Depuis un autre PC :

```sh
ssh -t michael@ax15 'python3 -m serial.tools.miniterm /dev/ttyACM1 115200 --raw --eol LF'
```

Le jeu de démonstration laissé par la validation tourne en arrière-plan.
Pour le remplacer par le jeu contrôlé au clavier :

```sh
kill "$(cat /tmp/desktop-demo.pid)"
prodock-game
```

A/D ou flèches déplacent la raquette ; Q ou Ctrl-C rendent le shell.
Pour garder le shell disponible : `prodock-game --demo &`.
Les commandes `prodockctl layout split`, `game` et `console` fonctionnent
pendant ce jeu en arrière-plan. Ctrl-] quitte miniterm sur le PC.

Sur l'affichage Linux R12, le test de 180 images mesure 51,92 FPS avec les
consoles actives. Le stress de sortie texte continue et de six changements
de disposition est plus coûteux : 28 FPS mesurés. La fréquence physique du
LCD est 55,04 Hz ; ces nombres ne décrivent pas le débit d'un jeu 3D complexe.
R13, avec le nouveau tableau de bord, mesure 52,43 FPS sur le même test de
180 images. Les tests des dispositions et du texte passent, et l'utilisateur
confirme que le tableau de bord est lisible et stable.
