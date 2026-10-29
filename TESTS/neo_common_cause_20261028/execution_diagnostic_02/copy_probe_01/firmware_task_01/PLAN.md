# Prochain test unique proposé : COPY565 dans les mêmes128B

## Pourquoi celui-ci

Le contrôle matériel CLEAR flags0 termine ; CLEAR flags1 reste bloqué et les
lectures CPU retrouvent le motif intact. Au sens du RTL, le trajet commun du
CLEAR atteint la bifurcation RECT_SETUP et peut terminer. Les états physiques
internes ne sont pas tous observés : nous ne prétendons pas avoir capturé
RECT_SETUP lui-même. La commande et le retour done ne sont donc pas bloqués
pour toutes les opérations, mais la branche de transaction reste à départager.

COPY565 utilise un autre moteur de requêtes (`u_copy`) à la place du chemin
RECT_ROW/CHUNK/COLOR, puis partage la sortie du GPU, le staging v1_pending et
l’arbitre. Sa destination garde exactement l’adresse du CLEAR qui échoue.
Le FILL historique n’est pas retenu : sa base fixe changerait la région DDR.

## Paquet exact et effet attendu

TARGET inchangé :
`16000000 12000020 12000040 00100001 00200020 00000000 00000000 00000000`

COPY :
`1d000000 12000000 00100001 00000020 00000000 00000000 00100001 00000000`

Source :16x1 pixels RGB565, stride32B, à12000000. Position source0,0,
destination0,0, dimension copiée16x1. Destination TARGET12000020, Z12000040.
Source et destination sont disjointes et alignées32B. Tous les accès restent
à l’intérieur du scratch128B déjà utilisé ; aucun parcours mémoire supplémentaire.

Après le même motif CPU XOR-adresse et contrôle TARGET, le résultat attendu :
- done2, busy/full0, erreurs/lost/rejected0,16mots de commande reçus ;
- une lecture native de32B à12000000 puis une écriture de32B à12000020 ;
- octets32..63 = copie exacte des octets0..31 initiaux ;
- les96autres octets restent le motif initial.

Le banc complet R19 passe sur deux couples horloges/phases avec ces paquets.
L’endpoint indépendant compare adresse/payload/masque et compte une lecture,
un retour, une écriture. Deux contrôles négatifs (commande jamais prête,
écriture jamais prête) donnent le timeout de completion attendu. Les sources
RTL sont inchangées ; result.json lie leurs empreintes. Aucun firmware ou
chargement carte supplémentaire n’est fait dans ce dossier à ce stade.

## Interprétation bornée

Si COPY termine avec le contenu attendu, le trajet de requête/retour et l’accès
à cette destination ont fonctionné pour COPY. Cela oriente vers les états et
signaux spécifiques au CLEAR non vide ; cela ne qualifie pas toute la DDR ou
tout l’arbitre et n’exclut pas un défaut de timing dépendant du trajet.

Si COPY bloque, ne pas en déduire que le staging est fautif : COPY ajoute une
lecture GPU et son retour, absents du CLEAR. Le snapshot/counters et le contenu
CPU restent nécessaires pour savoir si la lecture et/ou l’écriture ont eu lieu.
Le modèle ne reproduit ni les puces DDR, ni le PHY, ni le CPU/CDC physique.

Root garde le choix et l’exécution du test. Il réutilisera les gardes carteR19,
CPUROM/ILM/cache/FBoff, verrou, watchdog et restauration exacts. Aucun nouveau
bitstream, aucune modification des snapshots ou sources communes.
