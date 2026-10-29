# Témoin UTW1, candidat Neo dérivé de R19

Ce témoin est un instrument de diagnostic **candidat**, sans correction du
défaut observé. La qualification matérielle reste **FAIL** : les captures R19
existantes renvoient une version nulle ; le candidat n'est ni routé ni chargé.

## Frontière observée

Le témoin échantillonne `reply`, `receive_index`, `busy` et `snapshot_count` au
même front HCLK que la banque UTNA. Son acceptation est exactement
`!hreset && reply_valid`, y compris lorsque `busy=0`. Ce dernier cas est
compté séparément. Il ne crée aucun CDC. `hreset` synchrone est prioritaire
sur CE ; toutes les données persistantes utilisent des DFFRE explicites.

Les mots 0, 1 et 2 ont chacun une valeur brute, un tag de séquence prélevé sur
`snapshot_count` et un compteur d'écritures. Ils ne sont **pas atomiques**
pendant la réception : les tags et compteurs servent précisément à refuser
une capture partielle. L'instrument ne ralentit pas la FIFO, ne modifie pas
`busy` et ne fournit aucun retour au chemin de commande/capture.

## Registres en lecture seule

Base UTNA : `0xe9002000`. Les registres existants `+00..BF` conservent leur
décodage et leur latence. Les nouveaux offsets alignés étaient réservés et
retournaient zéro dans le netlist R19. Les offsets non alignés `+C0..FF`
continuent à retourner zéro. Toute écriture dans cette extension est ignorée.
La seule commande UTNA reste à `+0C`, inchangée.

| Offset | Valeur |
|---|---|
| C0 | `0x55545731`, identité UTW1 |
| C4 | `0x00010001`, ABI 1 / disposition 1 |
| C8 | Mot brut reçu à l'index 0 |
| CC | Mot brut reçu à l'index 1 |
| D0 | Mot brut reçu à l'index 2 |
| D4 | Alias du mot brut 1, autre classe d'adresse |
| D8/DC/E0 | Compteurs de capture des index 0/1/2 |
| E4 | Nombre total de mots reçus |
| E8 | Nombre de mots reçus à l'index 31 (fin de trame) |
| EC | Nombre de mots reçus hors `busy` |
| F0 | État de progression et erreurs persistantes |
| F4/F8/FC | Tags de séquence des mots 0/1/2 |

État F0 : bits 2:0 = index 0/1/2 vus dans la trame courante ; bit 3 = trame
ouverte ; bit 4 = index inattendu ; bit 5 = duplication d'un index témoin ;
bit 6 = débordement d'un compteur ; bit 7 = zéro ; bits 12:8 = prochain
index attendu ; bits 15:13 = zéro ; bits 20:16 = dernier index reçu ; bit 21
= `busy` au dernier mot ; bits 31:22 = zéro. Les erreurs sont persistantes
jusqu'au reset existant. Aucune lecture ne les efface.

Après N captures complètes depuis reset, avec **N ≥ 1**, sans autre événement :

- compteur UTNA `+08` = compteurs D8/DC/E0 = E8 = N ;
- E4 = 32 × N, sans dépassement 32 bits ; EC = 0 ;
- F4/F8/FC = N−1 ; F0 = `0x003f0007` ;
- C8 = identité UTNA, D0 = commande attendue, CC = D4 ;
- état UTNA `+04` = 0 (ni `busy` ni commande rejetée).

Après reset, pour N=0, les données, tags, compteurs et F0 sont tous nuls.
Cette image initiale n'est pas une capture à interpréter. Le reset des DFFRE
est synchrone : HCLK doit avancer pour vider le témoin. L'essai d'horloge
arrêtée concerne uniquement l'horloge USB, HCLK continuant à fonctionner.

**EC doit obligatoirement être vérifié**, même si F0 est normal. Un mot 0
reçu hors busy, suivi des mots 1..31 avec busy, peut donner F0=`0x003f0007`
et EC=1 : la trame a 32 mots mais ne satisfait pas le contrat de collecte.
L'alias D4 relit les mêmes bascules que CC ; il ne détecte pas à lui seul
une défaillance interne du registre raw1. Cette limite est conservée dans
l'interprétation ci-dessous, sans ajouter de logique au candidat gelé.

Pour une future collecte, lire l'état et la séquence avant et après **deux
lectures complètes** des registres et de la banque, sans commande concurrente.
Les deux images doivent être identiques et respecter toutes les relations
ci-dessus. Une version de banque nulle reste un échec même si les autres
valeurs sont exploitables pour le diagnostic. Pas de script matériel inclus.

## Interprétation conditionnelle

Si le défaut initial persiste avec ce nouveau placement, si les sentinelles,
tags, compteurs, alias et contrôles passent :

| Mot banque 1 | Témoin 1 | Conclusion limitée |
|---|---|---|
| 0 | 1 | L'écart se situe en aval de la frontière observée, ou dans la lecture du témoin/de la banque à distinguer ensuite. |
| 0 | 0 | La valeur est déjà nulle à la frontière, ou le témoin est lui-même erroné ; cela ne désigne pas à lui seul la FIFO. |
| 1 | 1 | Le défaut n'est pas reproduit sur ce nouveau candidat. Aucune cause établie. |
| 1 | 0 | Témoins incohérents : ne pas interpréter la frontière comme fiable. |

Une différence de tags, une capture incomplète, un compteur hors `busy`, une
erreur d'ordre/duplication/débordement ou un alias incohérent invalide cette
lecture simple. Les 402 FF, les taps et le mux de lecture augmentent la
charge/routage du design : il n'existe aucune garantie d'observation physique
sans perturbation.

## Transformation et réversibilité

Le constructeur vérifie le SHA du netlist R19, de son bitstream, du netlist
routé et du manifeste de toutes ses sources. Il copie le snapshot, ajoute
uniquement la source Neo du helper, puis conserve tous les anciens modules.
Seul `usb_idle_trace` reçoit le helper et 32 LUT3 ; chaque registre `hrdata`
garde son CLK, RESET, CE et Q, seul son D passe par un mux sélectionné par
l'adresse de l'extension. Tous les paramètres primitifs originaux restent
inchangés. Le retour arrière est vérifié octet pour octet.

Le helper est mappé seul par Yosys avec `-family gw5a -strict-gw5a-dffs`,
sans RAM, I/O, PLL ni GSR ajouté. Le netlist du système R19 n'est jamais
resynthétisé. Le mapping local est simulé avec la bibliothèque officielle
Gowin ; il ne vaut ni acceptation par le lecteur Gowin ni timing fermé.
Le dossier ne contient aucun lancement de P&R ou de programmation. Une
future étape de construction exige une revue distincte, la licence et les
gardes habituelles. La remise sur carte du R19 de référence reste la voie
de retour matériel ; aucune archive protégée n'est remplacée.
