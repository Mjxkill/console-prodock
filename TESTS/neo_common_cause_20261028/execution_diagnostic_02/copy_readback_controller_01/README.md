# Raccord contrôleur lecteur COPY — hors carte

Le seul contrôleur modifié est `root_microdma_01.py`. Sa version précédente
est conservée dans `controller_before.py`; les preuves historiques ne changent
pas. Les profils firmware1/2/3/4 et leurs SHA restent identiques.

`--cpu-readback` accepte maintenant les profils2 (CLEAR) et4 (COPY), avec
`--capture-gpu` obligatoire. La table lie chemin, SHA du lecteur588B et SHA
du décodeur. COPY utilise `decode_bound` avec les deux SHA appropriés.
Les Tcl des quatre profils **sans** relecture sont comparés octet pour octet
au contrôleur précédent, après normalisation du seul dossier de sortie.

Avant le lecteur, le contrôleur vérifie le journal MD12 et CPU au parking,
efface uniquement256B ILM à a0006400 et relit64mots nuls. Il charge/vérifie
le code588B à a0005000, reprend explicitement ce point d'entrée, puis arrête
le CPU et sauvegarde le journal même si le PC n'est pas revenu au parking.
Un mauvais retour interrompt la suite et rend l'observation non qualifiée.

Le décodeur final exige quatre marqueurs uniques et ordonnés dans le journal
de cette exécution : clear vérifié, démarrage demandé, retour ROM vérifié,
collecte terminée. Sans cette séquence, `readback_valid=False` et classe
`unobserved`, même si le contenu ressemble à un ancien journal valide.
Cette garde complète les SHA ; elle n'est pas une preuve cryptographique
d'exécution ni une lecture physique du bitstream.

`test_controller.py --out-name <dossier-neuf>` exécute neuf groupes de tests :
vraies préparations CLI sans `--run`, vrais guards Tcl avec commandes mémoire/
PC inertes, séquencement, refus avant écriture, refus du clear ou de verify,
préservation du dump partiel, SHA et marqueurs de fraîcheur. 9/9 PASS dans
`tests_02`. Le premier passage `tests_01` conserve un faux échec du test
d'ordre : il cherchait la sous-chaîne VERIFIED aussi présente dans
ZERO_VERIFIED. La correction porte seulement sur le test (lignes exactes).

Aucun JTAG, programmateur ou port USB n'a été ouvert. Verrou matériel,
watchdog, capture NGDB et restauration R19 restent ceux du contrôleur parent.
Une relecture correcte n'efface pas l'échec/rejet du premier programme GPU.
