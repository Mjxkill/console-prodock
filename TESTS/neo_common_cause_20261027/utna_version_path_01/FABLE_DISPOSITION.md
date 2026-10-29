# Contre-relecture de Fable

Avis reçu de Claude Code/Fable dans
`TESTS/assisted_reviews_20261026/neo_utna_version_routed_fable_r1/answer.txt`.
Le paquet transmis SHA `3c44f7d529b0915ee21398128c0a9d2fbad5d3aa4a14560b82330319792d16cb`
contenait la capture réelle et les cellules/arcs ciblés. Le modèle n'a utilisé
aucun outil ou matériel. Son avis reste distinct des preuves locales.

| Proposition | Vérification et décision |
|---|---|
| FF constant partagé entre ID et version | Confirmé par les LUT INIT, six cellules et 34 cofactors exhaustifs. |
| DI0 indépendante du seul bit send_index0 aux indices0/1 | Confirmé dans le réseau booléen compilé. |
| « Exonéré même contre un transitoire » | Trop général : la stabilité des autres sélecteurs, CE, reset et configuration réelle n'a pas été mesurée. On exclut le FF constamment0 et le seul changement normal 0→1 du bit0 d'index, sous les préconditions démontrées. |
| « Décalage ou pop manqué exclus » | Réduit à l'exclusion d'un décalage uniforme simple. Le compteur32 et deux mots corrects ne prouvent pas chaque transfert, ni une absence de fautes compensées. |
| Panne FIFO et masque validité indiscernables sur cette capture | Confirmé. Une faute injectée sur la seule validité lane1 reproduit `[ID,0,2]` et les autres mots nuls, sans injecter de faute FIFO. Ce n'est pas la cause matérielle identifiée. |
| La sélection initiale ne couvrait pas toute la validité du mot1 | Exact. `bank_validity_supplement.txt` complète les quatre RAM, MUX2 et contrôles de groupe (56 cellules). Ce supplément n'était pas dans son paquet. |
| Rapports STA insuffisants pour déclarer ou accuser le timing | Accepté. Les sommes Q→DI ne sont pas des slacks. |
| Hypothèse « première entrée lue trop tôt » | Plausibilité physique non établie. Le RTL exact utilise deux synchroniseurs Gray puis un registre de pointeur décodé avant le pop ; le modèle fonctionnel ne montre pas une lecture anticipée. Une autre phase seule ne suffit pas à affirmer un défaut. |
| Deuxième remplissage sans reprogrammation | Utile pour distinguer premier passage et persistance. La séquence activité préparée conserve les versions des quatre captures avant son unique restauration. |
| ARM puis capture des mots variables | Retenu dans la collecte ARM→DISARM→SNAPSHOT→SNAPSHOT, avec contrôles stricts et FAIL version0 conservé. |
| Reset_n sans reconfiguration | Non préparé, non exécuté. Il faudrait identifier le mécanisme exact et vérifier ses effets sur le contenu BSRAM et les deux domaines. Pas de reset hors garde ajouté. |

La séquence suivante est préparée dans `../utna_activity_prepared_01/` et attend
la revue root. Son critère reste version1. La version0 permet seulement
de terminer la collecte annoncée avant de rendre un résultat FAIL et de
restaurer R19. Toute autre rupture de contrat interrompt immédiatement.

Aucun correctif source, bitstream, contrainte ou modification Pro Dock n'est
déduit automatiquement de cet avis.
