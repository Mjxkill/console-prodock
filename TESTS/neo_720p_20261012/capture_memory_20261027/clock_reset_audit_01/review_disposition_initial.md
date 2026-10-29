# Disposition contradictoire des trois revues

27 octobre 2026. Les trois modèles ont reçu indépendamment le même paquet, sans réponses croisées, sans outils, sans accès matériel. Leurs avis ne constituent ni un test exécuté ni une autorisation de patch.

## Défaut du paquet corrigé

Le préparateur a projeté quelques clés JSON inexistantes avec `dict.get`, affichant `null` alors que les fichiers originaux possèdent d'autres clés et des preuves positives. Ce défaut de présentation a entraîné des conclusions incorrectes chez Claude/Fable et DeepSeek. Les originaux n'ont pas été modifiés. L'errata contient les vrais schémas, les logs A/B/A, les hachages et la preuve d'invariance. Il doit accompagner toute citation des premiers avis.

Paquet initial : `TESTS/assisted_reviews_20261026/neo_clock_reset_packet_r1.txt`, SHA256 `7b76d6a311883cbe0cb5d697e118aa917d10e7122b9a6d43f17d4a638fd9b8b0`.
Errata : `neo_clock_reset_errata_packet_r2.txt`, SHA256 `82975fcea1b45340a133ba426d29cd63ac4822da171c12f93a30dc811d3cac10`.

## Points retenus

- Le STA global est FAIL sur les deux versions ; aucun consensus verbal ne le transforme en PASS.
- Les contraintes sont identiques entre R19/R21. Leur identité ne prouve pas leur complétude.
- Les cellules fonctionnelles, ports et INIT sont conservés, mais cela ne constitue pas une qualification temporelle ou de démarrage.
- L'A/B/A à 100 kHz JTAG est étayé par les logs originaux : R19 accessible, R21 DMI en échec, R19 de nouveau accessible. La caméra avant DMI montre aussi la différence d'affichage.
- Le SDF exporté contient des arcs du macro AE350 ; il ne faut pas le décrire comme intégralement non modélisé. Il ne contient cependant pas les contrôles POR_N/HW_RSTN recherchés. L'absence dans cet export ne prouve pas l'absence dans la bibliothèque interne.
- Le SDC ne ferme pas explicitement l'interface JTAG, alors que des arcs TMS/TDI/DBG_TCK existent dans le modèle.
- Aucune causalité LW → panne CPU n'est établie. Une route LW est légitime.
- Cible B/C et boîtier 676/484 sont des différences réelles ; aucune preuve ne permet d'en déduire un erratum ou une mauvaise sélection de cible Neo.

## Propositions rejetées ou limitées

| Avis | Disposition et preuve contraire |
|---|---|
| Beam r1 : ajouter false_path sur init_sync/CLEAR | Rejeté. Source et destination bus80 ; recovery +8,851 ns et removal +1,416 ns sont effectivement calculés. Supprimer ces checks diminuerait la preuve. Beam r2 retire cette proposition. |
| Beam r2 : +8,851 ns est une marge setup ; augmenter le délai ferait échouer removal | Incorrect. Le premier check est recovery. À horloge de destination fixée, augmenter le délai de données aide le contrôle removal mais réduit la marge recovery. Ne pas réutiliser sa recommandation quantitative. |
| Fable r1 : aucun reset ne doit être sur LW, puis contraindre prst LOCAL_CLOCK | Exigence non fournie et non démontrée. Pas de spécification violée ni de cône causal vers DMI. Aucun patch appliqué. |
| Fable r1 : absence Fmax CORE implique absence de toute analyse CORE et groupe asynchrone inerte | Trop fort. Le modèle contient des arcs CORE. Le message Fmax ne constitue pas un inventaire de tous les checks internes/externes ni de la résolution des exceptions. |
| Fable r1 : macro AHB éventuellement entièrement non évalué | L'extrait était sélectionné. Le bloc complet contient de nombreux arcs AHB (679 mentions relevées par parent). Il faut examiner les arcs réels, pas déduire leur absence de l'extrait. |
| Fable/DeepSeek r1 : preuves A/B/A et invariance vides à cause de champs null | Rejeté : erreur de projection du paquet, voir errata et fichiers originaux. DeepSeek r2 corrige explicitement ce point. |
| DeepSeek r1 : suffixe rx_sync_0_s1 suspect, exception sur mauvais étage | Résolution netlist parent `root_constraints_01/sync_cells.json` : D=uart_rx_d, Q=rx_sync[0], donc bon premier étage. Le suffixe s0/s1 n'est pas l'indice d'étage. Les exceptions dp/dm visent aussi correctement leurs premiers étages. |
| DeepSeek r1 : total DDRsys dégradé suggère calibration DDR en échec | Le groupe inclut surtout des chemins GPU. Ce total ne localise pas une panne de calibration. Une mesure DDRready ou des chemins de calibration spécifiques est nécessaire. |
| DeepSeek r1 : simulation SDF positive réfute universellement un bug RTL/CDC | Faux : un banc fini, sans modèle comportemental du CPU dur, ne couvre ni toutes les séquences ni la métastabilité analogique. |
| DeepSeek r2 : exiger un check pour chaque pin asynchrone sans exception et un chemin Fmax CORE | Critère trop fort. Les premières bascules de synchronisation justifient certaines exceptions ; le cœur dur peut ne pas fournir de chemin interne à fermer dans le fabric. Il faut une matrice du contrat des interfaces, des exceptions justifiées et des exigences du fabricant. |
| DeepSeek r2 : bits constants 60/62/63 partageant le driver held_63_s3 suspects | Aliases de synthèse constants déjà vérifiés dans la preuve postroute ; le partage n'est pas un défaut en soi. La preuve des bits et de leurs valeurs doit rester liée au résultat, pas être remplacée par un test d'unicité des drivers. |

## Conclusion technique conservée

La cause matérielle du refus de démarrage R21 reste non établie. Le résultat utile des revues est une matrice de couverture précise, pas une nouvelle modification de routage. Les exigences de démarrage du macro, la fermeture de l'interface JTAG et les violations fonctionnelles déjà mesurées doivent être traitées séparément.

L'absence d'une preuve de reset du macro ne permet pas de déclarer automatiquement une contrainte manquante dans le SDC : il faut d'abord connaître l'exigence de durée/ordre/horloge et déterminer si elle relève du RTL, du modèle STA, de la configuration ou de contraintes temporelles. Les 20 ms historiques sont un exemple SDK, pas un minimum fabricant établi.

Une seconde revue Fable sur l'errata et la matrice est en cours au moment de cette disposition initiale. Ses résultats seront ajoutés séparément sans réécrire les premières réponses.
