# R19 : activité correcte, version UTNA toujours nulle

Analyse hors carte de la capture root `activity_20261028_000942`.
`analyse_capture.py` vérifie les SHA de tous ses fichiers et la restauration R19.
Aucun accès matériel, nouveau routage ou changement du RTL commun.

| Capture | Commande / séquence | Version | Ticks (mot3) | Armed (mot31) |
|---|---|---:|---:|---|
| ARM | 1 / 1 | 0 | 0 | Non |
| DISARM | 6 / 2 | 0 | 26 061 045 | Oui |
| STOPPED | 2 / 3 | 0 | 26 061 046 | Non |
| STABLE | 2 / 4 | 0 | 26 061 046 | Non |

Chaque banque a été lue deux fois, identique. ID, commande et acquittements
sont corrects. Le contrat pré-clear/pré-disarm, le dernier tick +1 et son arrêt
sont respectés. Le mot16 vaut1 aux trois dernières captures. La version reste
nulle à toutes les lectures : l'essai demeure **FAIL**, R19 a été restaurée.

## Ce qui est établi, et ce qui ne l'est pas

L'observateur exécute les commandes et transfère des données qui changent.
Un blocage permanent de tout l'observateur sous reset n'explique pas ces données.
Cela ne valide ni tous les resets de la Neo, ni ses autres blocs, ni la
fréquence physique de l'horloge, ni une liaison USB HS fonctionnelle.

Le défaut version0 persiste après quatre remplissages, sans reconfiguration
entre eux. Le scénario simple « première lecture prématurée de la case1,
puis écriture correcte laissant1 dans la mémoire » prédit une amélioration
au remplissage suivant, qui n'est pas observée. Il est donc insuffisant sous
ses propres hypothèses. Cela n'innocente pas toute la FIFO : une erreur
persistante de case/adresse/enable peut toujours produire le motif.

## La classe1 n'a toujours pas de deuxième témoin non nul

| Mot | Adresse | Valeur non nulle observée | Classe modulo4 | Ligne de validité | Demi-banque |
|---:|---|---|---:|---:|---:|
| 0 | 0xe9002040 | ID=0x55544e41 | 0 | 0 | 0 |
| 2 | 0xe9002048 | Commandes1/6/2 | 2 | 0 | 0 |
| 3 | 0xe900204c | Ticks variables | 3 | 0 | 0 |
| 16 | 0xe9002080 | 1 | 0 | 4 | 1 |
| 31 | 0xe90020bc | 0x400 pendant armed | 3 | 7 | 1 |

Les classes0,2,3 et les lignes0,4,7 donnent des données non nulles. Le masque
global de banque et ses deux demi-banques ne sont donc pas continuellement
nuls. Le bit0 est aussi lu à1 au mot16 : ce n'est pas une sortie bit0 toujours
nulle. Le mot3 prouve qu'une adresse avec address[2]=1 peut être lue ; cela
ne prouve pas toute la sélection particulière de la classe1.

Les mots de classe1 sont 1,5,9,13,17,21,25,29. Ils sont tous nuls ; seul le
mot1 a une valeur non nulle certaine imposée par le RTL. Aucun stimulus ne
garantit ici un compteur IN3, une erreur RX, un stall ou un historique non nul
dans les autres mots. On ne peut donc pas dire que toute la classe1 est cassée,
ni qu'elle fonctionne. Une seule case1 erronée et un masque de classe1 erroné
restent compatibles avec la capture.

## Vérification supplémentaire de la netlist réellement routée

Les précédentes simulations complètes utilisaient la netlist de synthèse `.vg`.
`check_routed_v2.py` extrait les **3 729 primitives exactes** du bloc dans `.vo`,
y compris la SDPB32 scindée au routage en deux SDPB16 et les quatre RAM de
validité. Trois couples de périodes/phases passent la séquence complète avec
version1. Aucun Gowin n'a été lancé.

Le premier essai du banc échouait dès l'ID parce que son raccordement traitait
`bus_htrans[1:1]` comme un bus à deux bits ; le warning Icarus le signalait.
Il reste conservé. La version2 raccorde ce port d'un seul bit et compile sans
warning. Ce défaut de banc n'est pas assimilé au défaut matériel version0.

La simulation routée reste **fonctionnelle sans SDF**. Elle ferme une lacune
de couverture du mapping, pas une preuve de timing, de métastabilité ou de
la forme réelle des resets au démarrage.

`check_masked_activity.py` ajoute un contre-exemple sur ce même graphe routé :
une impulsion SOF est simulée pendant armed, puis la seule sortie de validité
lane1 est forcée à0. Sur les 128 mots des quatre captures, seuls les quatre
mots version changent de1 à0 ; ticks, armed et le mot16 sont identiques au
témoin sans faute. **La faute est volontairement injectée**. Elle montre que
la nouvelle activité cohérente ne suffit toujours pas à innocenter ce masque,
sans identifier la cause physique. Les ticks simulés ne sont pas les valeurs
mesurées sur la carte.

## Prochaine séparation utile

Répéter les mêmes lectures ne séparera pas la sortie de la FIFO de la banque.
Deux possibilités existent, avec des portées différentes :

1. Produire un mot de classe1 non nul indépendamment de version, par exemple
   IN3 au mot5. Il faut alors un stimulus USB hôte contrôlé, actuellement hors
   du protocole sans transfert USB. Ce test sépare davantage une classe entière
   d'une case unique, mais ne localise pas encore FIFO versus banque.
2. Ajouter un **témoin au domaine HCLK**, juste avant la banque : lorsque
   `reply_valid && receive_index==1`, conserver `reply` dans des bascules
   explicites, avec un compteur de capture. Conserver aussi les mots0 et2 et
   leurs identités comme témoins. Après busy=0, lire ces témoins par un chemin
   qui n'utilise pas la RAM/validité de banque existante.

Cette seconde piste est la plus directement discriminante :

| Témoin mot1 avant banque | Banque mot1 | Direction du diagnostic |
|---:|---:|---|
| 1, témoins0/2 et compteur corrects | 0 | Écriture/stockage/validité/lecture de banque |
| 0, témoins0/2 et compteur corrects | 0 | En amont de la banque, dont FIFO ou émission |
| Témoins/compteur incohérents | Indifférent | Instrumentation ou contrat non validé : aucune localisation |

Il s'agit d'une **proposition**, pas d'un correctif ni d'un candidat construit.
Les témoins sont dans HCLK ; aucun nouveau CDC de données n'est nécessaire à
cette première séparation. Il faudra prouver que les bascules ne sont pas
ré-inférées en RAM, vérifier leurs contraintes et préserver R19 comme contrôle.
Un nouveau placement peut modifier le symptôme ; sa disparition seule ne
désignerait pas la cause et ne justifierait pas une promotion.

Le témoin doit copier la condition effective de la banque :
`!hreset && reply_valid`, avec l'ancienne valeur de receive_index au même front.
Ne pas le filtrer silencieusement par busy : la banque actuelle ne le fait pas.
Un événement hors busy doit être enregistré comme anomalie distincte. Le
compteur doit compter les captures d'index1, pas les seuls fronts de reply_valid,
car deux mots consécutifs peuvent garder reply_valid à1.

Il serait utile de lire le témoin1 à deux adresses de classes différentes et
de fournir un identifiant non nul de l'instrumentation : un mauvais décodage
de sa seule adresse de lecture ne doit pas être pris pour une valeur reçue0.
Ces garde-fous restent à spécifier et à valider avant tout candidat matériel.

Cette anomalie d'un observateur ne suffit pas à expliquer les autres défauts
Neo ni l'écart global avec la Pro Dock.
