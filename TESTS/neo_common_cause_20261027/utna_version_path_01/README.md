# R19 : version UTNA nulle après SNAPSHOT, analyse post-routage

Analyse locale uniquement, sans accès carte, changement RTL ou lancement Gowin.
Les captures matérielles appartiennent au contrôleur root :
`../utna_snapshot_prepared_01/snapshot_20261027_232521/`.

## Faits mesurés

Avant commande, les lectures individuelles donnaient contrôle `[ID,0,0]` et
banque nulle. Après une unique commande SNAPSHOT=2, le contrôle vaut `[ID,0,1]`.
Les huit en-têtes lus individuellement et par blocs de 3/32 mots donnent tous
`[0x55544e41,0,2]`, avec deux banques complètes identiques. Le contrat version1
échoue. La restauration exacte R19 et ses gardes sont attestées.

Ces mesures contredisent l'alias permanent banque→contrôle et une différence
entre lectures individuelles/groupées pour cet essai. Elles ne constituent pas
une qualification USB ou vidéo.

## Contrepreuve sur le FF constant

`analyse.py` extrait la netlist post-routage `.vo` et évalue ses LUT INIT.
`snapshot_32_s0` reçoit VCC. Son horloge, son reset et son CE sont logiquement
ceux de `snapshot_65_s0`, qui capture le bit1 de la commande.
Le synthétiseur partage le FF constant pour tous les 13 bits à1 de l'ID.

| snapshot[32] stable | Mot0 à l'entrée FIFO | Mot1 | Mot2, commande2 |
|---|---:|---:|---:|
| 0 | 0 | 0 | 2 |
| 1 | 0x55544e41 | 1 | 2 |

Donc « le FF version reste constamment à zéro » n'explique pas l'ID correct
dans le réseau booléen compilé. Cela ne prouve pas l'état physique de ce FF.

`prove_slot01_constant.py` ajoute une preuve exhaustive de cofactors : 34
combinaisons sur six LUT. Pour snapshot32=1 et send_index[4:1]=0, la même
branche force DI0=1 pour les indices0 **et**1, indépendamment de send_index[0] :

`n181_57=1 → n181_47=0 → n181_40=0 → n181_38=0 → n181_37=DI0=1`.

Le seul changement de send_index0 lors de 0→1 ne suffit donc pas, dans ce
modèle, à produire le zéro. Les transitoires sur d'autres signaux, les erreurs
d'adressage/enable et le stockage restent à distinguer. Ce n'est pas une
preuve d'erratum de FIFO, de silicium ou de générateur de bitstream.

Une simulation fonctionnelle des modules exacts, avec la bibliothèque Gowin,
confirme trois cas dans `fault_models/result.json` : fonctionnement normal
`[ID,1,2]`, snapshot32 forcé à zéro `[0,0,2]`, et seule sortie de validité
`bank_ER_RS_87` forcée à zéro `[ID,0,2]`. Ce dernier cas reproduit le motif
observé et les 29 autres mots nuls. **La faute est injectée volontairement** :
ce contre-exemple prouve la non-unicité de l'explication, pas la cause physique.
La simulation n'a pas d'annotation SDF.

## Chemin et ressources

- ID bit0 et version bit0 utilisent la même DI0 de la SDPB
  `u_replies/g_inferred_storage.mem_g_inferred_storage.mem_0_0_s`.
- Commande bit1 utilise DI1 de cette même SDPB.
- Les mots utilisent des adresses différentes ; le chemin des pointeurs et
  des enables n'est pas validé matériellement par la preuve de données.
- La sortie `reply[3:0]` va à `bank_bank_0_0_s`, une RAM16SDP4, dont les mots0
  et1 sont deux adresses. Les données ne sont pas des bascules isolées.
- La remise à zéro de la banque utilise aussi des RAM16SDP1 de validité et
  des registres de groupe. Le slot1 dépend de la lane
  `bank_ER_RS_bank_ER_RS_0_0_s0`, distincte des lanes0 et2. Un masque invalide
  peut masquer un mot sans démontrer que la donnée FIFO est incorrecte.

`bank_validity_supplement.txt` conserve les 56 cellules du cône de validité,
y compris les MUX2 et les quatre RAM. Ce supplément a été extrait après gel
du paquet Fable ; ne pas prétendre que cette preuve additionnelle y figurait.

## Délais disponibles et limites

`supplement.py` additionne les arcs INTERCONNECT et IOPATH exacts du SDF
existant entre Q et DI. Ce sont des sommes de propagation, **pas des slacks**.

| Chemin | Min | Typ | Max |
|---|---:|---:|---:|
| snapshot32/Q → DI0 | 1,655 ns | 2,855 ns | 4,061 ns |
| snapshot65/Q → DI1 | 1,903 ns | 3,131 ns | 4,359 ns |

Elles n'incluent ni clk→Q, ni setup/hold, ni skew, incertitude ou preuve de
contrainte complète. Le fichier STA existant ne publie ici qu'un chemin HOLD
`rd_bin[4] → SDPB` à +0,231 ns. L'absence d'un autre chemin dans ce rapport
limité n'établit pas sa fermeture. Les routes directes vers le WRE de validité
du slot1 ne présentent pas à elles seules une preuve de défaut.

## Prochain essai proposé, pas préparé ni autorisé par cette analyse

Sur R19 uniquement : ARM=1, attente hôte bornée, DISARM=6, puis SNAPSHOT=2
deux fois. Conserver toutes les banques et les résultats incorrects ; le
champ version0 garde le diagnostic global FAIL. Identité, busy, compteur
d'acquittement et écho commande doivent rester stricts. Toute anomalie de ces
gardes interrompt l'essai et restaure R19.

Cela permettrait de vérifier des mots non constants : ticks au mot3 et état
armed au mot31, puis le tick final +1 prévu par le RTL et sa stabilité après
arrêt. Cela ne mesure pas la fréquence réelle. Si ces mots sont corrects et
seul le mot1 reste nul, l'hypothèse d'un défaut global de capture/reset
s'affaiblit encore. **Cet essai ne séparera pas à lui seul la case1 de la FIFO
de la case1 ou de la validité de la banque**, car leurs indices sont fixes.

Une commande SNAPSHOT avec le champ adresse autorisé, par exemple 0x5502,
peut enrichir le motif connu du mot2 sans changer target tant que ARM est0.
Elle teste d'autres bits du chemin commun, mais ne déplace pas le mot version.
Ne pas la présenter comme une preuve suffisante pour accuser ou innocenter
la FIFO.

## Reproductibilité

Les scripts et résultats sont locaux. `result.json` lie les netlists, SDF,
STA, bitstream et capture exacte par SHA-256. Les primitives figées et les
tests fonctionnels précédents rendaient version1 sans reproduire l'erreur
matérielle ; ils n'avaient pas d'annotation SDF. Aucune source partagée ou
référence Pro Dock n'a été modifiée.
