# Capture R19 partielle — mot version absent

L'extracteur strict termine avec le code1 attendu : l'en-tête de la première
capture ARM est `[0x55544e41,0,1]`, au lieu de `[0x55544e41,1,1]`.
Le contrôle n'a pas été assoupli. DISARM, STOPPED, STABLE et POST_USB n'ont
pas été exécutés ; leurs absences sont les conséquences de ce premier échec.

Le résultat matériel est terminé et ses fichiers ont tous été vérifiés par
SHA. R21r2 n'a été ni chargé ni observé dans cet essai. Le retour R19 exact
est attesté, SHA
`1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c`,
avec garde GPU/NCP fraîche et UTNA contrôle `[ID,0,0]`. L'inspection des photos
reste celle du coordinateur root ; aucune caméra ou sonde n'a été ouverte ici.

Les quatre relevés vidéo avant ARM montrent +99 images sur1632ms de temps
hôte, zéro underflow et la même somme `0x1ff8f800`. Ces valeurs décrivent le
relevé ; elles ne mesurent pas une fréquence de PLL ou une énumération HS.

Le statut ARM est idle à la séquence1 avant, entre et après les deux lectures
de banque. Les banques sont identiques. Cela prouve une lecture stable dans
cette fenêtre, pas la répétabilité sur plusieurs ARM ni la justesse des mots
qui ont traversé la FIFO.

## Contrat et netlist

Les fichiers RTL USB trace R19/R21r2 sont identiques, SHA
`97854f943d523304877e4fafc52c53e71ef03cb3e54940f13cd1a7a0bdbe8d9f`.
Le mot1 de `live` est la constante `32'd1`, indépendante d'armed. Les trois
modules synthétisés USB trace/FIFO commande/FIFO réponse sont également
identiques entre les deux builds. Le bit `snapshot[32]` est un DFFRE D=VCC,
avec les mêmes clock/reset/enable que le bit0 de commande `snapshot[64]`.

La banque est réalisée en RAM16SDP4 avec logique supplémentaire de
validité/reset. La simulation fonctionnelle des modules synthétisés exacts
passe trois couples d'horloges/phases avec les primitives Gowin ; le mot1 y
reste1. Le témoin négatif du tick final échoue comme prévu. Résultat séparé :
`../utna_header_netlist_01/result.json`. Ni SDF, ni routage, ni étage AHB amont
ne sont couverts par cette simulation ciblée.

## Hypothèse discriminante : alias du contrôle

Après l'ACK1, les registres de contrôle +00/+04/+08 valent précisément
`[ID,0,1]`. Une perte du bit adresse6 lors des lectures +40/+44/+48 produirait
donc exactement l'en-tête observé. Pour cette première capture presque nulle,
l'hypothèse reproduit les32mots : voir `bit6_alias_hypothesis.json`.

**L'alias n'est pas démontré.** Une corruption de capture peut produire le
même résultat. De plus, la somme scanout lue à +60 est correcte ailleurs :
il ne faut pas déclarer le bit adresse6 globalement absent.

Une future commande snapshot2 en premier séparerait commande2 et séquence1.
Comparer les lectures individuelles +08/+48 et +04/+44, ainsi que l'ordre
inverse et la rafale, pourrait distinguer contenu de banque et alias de
lecture. Une alternative est DISARM6 à la séquence2. Ce sont des propositions
pour un essai root séparément revu, pas des opérations exécutées ici. Le
critère version1 reste obligatoire ; aucun PASS ne peut ignorer cet écart.
